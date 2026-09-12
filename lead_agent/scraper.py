"""
Fetches a company's website plus a handful of likely "about/team/contact"
pages and returns cleaned, size-capped text for the extraction step.
"""

import re
from typing import List

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from . import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TVBLeadAgent/1.0; "
        "+https://theventurebuild.com) research-bot"
    )
}

CANDIDATE_PATHS = [
    "", "/about", "/about-us", "/team", "/our-team", "/leadership",
    "/contact", "/contact-us", "/company",
]

LINK_KEYWORDS = ("about", "team", "leadership", "contact", "founder", "company")


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().lstrip("www.")
    except Exception:
        return url


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch(url: str) -> str:
    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=config.REQUEST_TIMEOUT_SECS
        )
        if resp.status_code >= 400:
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
    base = f"{parsed.scheme}://{parsed.netloc}"

    visited = set()
    chunks = []

    home_html = _fetch(homepage_url)
    if home_html:
        chunks.append(_clean_text(home_html))
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
            chunks.append(_clean_text(html))

    combined = " ".join(chunks)
    return combined[: config.PAGE_TEXT_CHAR_LIMIT]
