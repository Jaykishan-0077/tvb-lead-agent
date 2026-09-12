"""
Fetches a company's website plus a handful of likely "about/team/contact"
pages and returns cleaned, size-capped text for the extraction step.

Hardened with Phase 2 Anti-Bot & Silent Error Interception:
- Modern browser session headers.
- Silent firewall detection (Cloudflare / Datadome / CAPTCHA / 403 / 429).
- Parked/dead domain pre-filtering so LLM is never fed raw error pages.
"""

import re
import socket
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

CANDIDATE_PATHS = [
    "", "/about", "/about-us", "/team", "/our-team", "/leadership",
    "/contact", "/contact-us", "/company",
]

LINK_KEYWORDS = ("about", "team", "leadership", "contact", "founder", "company")

BLOCKED_FIREWALL_SIGNATURES = [
    "attention required! | cloudflare",
    "just a moment...",
    "cf-browser-verification",
    "access denied",
    "security check to continue",
    "please verify you are a human",
    "datadome",
    "ray id:",
    "domain is parked",
    "buy this domain",
    "this domain name is for sale",
    "parkingcrew",
]


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().lstrip("www.")
    except Exception:
        return url


def is_valid_resolvable_domain(domain: str) -> bool:
    """Pre-flight DNS check to ensure domain is active and not dead."""
    if not domain:
        return False
    try:
        clean_domain = domain.split(":")[0].strip()
        socket.gethostbyname(clean_domain)
        return True
    except Exception:
        return False


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "object"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_firewall_or_error_page(text: str) -> bool:
    """Detects if response text is a Cloudflare/Datadome block or parked placeholder."""
    if not text or len(text) < 120:
        return True
    lower = text.lower()
    return any(sig in lower for sig in BLOCKED_FIREWALL_SIGNATURES)


def _fetch(url: str) -> str:
    """Fetches web page with anti-bot impersonation and silent error interception."""
    try:
        # 1. Try TLS-impersonating curl_cffi if available
        if cffi_requests is not None:
            try:
                resp = cffi_requests.get(url, impersonate="chrome", timeout=config.REQUEST_TIMEOUT_SECS)
                if resp.status_code in (401, 403, 429, 500, 502, 503, 504):
                    return ""
                if _is_firewall_or_error_page(resp.text):
                    return ""
                return resp.text
            except Exception:
                pass

        # 2. Standard robust requests with modern browser headers
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=config.REQUEST_TIMEOUT_SECS, allow_redirects=True)
        if resp.status_code >= 400:
            return ""
        if _is_firewall_or_error_page(resp.text):
            return ""
        return resp.text
    except Exception:
        return ""


def _discover_internal_links(base_url: str, html: str) -> List[str]:
    links = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            text = (a.get_text() or "").lower()
            href = a["href"]
            if any(k in text for k in LINK_KEYWORDS) or any(
                k in href.lower() for k in LINK_KEYWORDS
            ):
                links.append(urljoin(base_url, href))
    except Exception:
        pass
    return links


def gather_site_text(homepage_url: str) -> str:
    """Fetch the homepage plus a few likely info-rich pages, return combined
    cleaned text capped to PAGE_TEXT_CHAR_LIMIT characters."""
    parsed = urlparse(homepage_url)
    domain = parsed.netloc.lower().replace("www.", "")
    if not is_valid_resolvable_domain(domain):
        return ""

    base = f"{parsed.scheme}://{parsed.netloc}"
    visited = set()
    chunks = []

    home_html = _fetch(homepage_url)
    if home_html:
        clean = _clean_text(home_html)
        if len(clean) >= 150:
            chunks.append(clean)
            visited.add(homepage_url)

    urls_to_try = [urljoin(base, p) for p in CANDIDATE_PATHS]
    if home_html:
        urls_to_try += _discover_internal_links(base, home_html)

    for url in urls_to_try:
        if len(" ".join(chunks)) >= config.PAGE_TEXT_CHAR_LIMIT:
            break
        if url in visited:
            continue
        visited.add(url)
        html = _fetch(url)
        if html:
            clean = _clean_text(html)
            if len(clean) >= 100:
                chunks.append(clean)

    combined = " ".join(chunks)
    return combined[: config.PAGE_TEXT_CHAR_LIMIT]
