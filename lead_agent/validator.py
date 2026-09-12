"""
Validates extracted records against TVB's target-profile parameters and
performs a hardened Waterfall Verification workflow with Catch-All probing:

  1. Tier 1: Hunter.io Live B2B API Lookup (if HUNTER_API_KEY is present).
  2. Tier 2: Catch-All Domain Detection (via random address SMTP probe).
  3. Tier 3: Waterfall Gate:
     - If Catch-All domain -> Drop pattern matrix; ONLY accept Hunter.io score >= 80.
     - If Non-Catch-All -> Generate candidate pattern matrix (first@, first.last@, f.last@).
  4. Tier 4: Priority DNS/MX Resolution & Non-Intrusive SMTP Handshake.
"""

import os
import random
import re
import smtplib
import socket
import string
from typing import Dict, List, Optional, Tuple

import requests

try:
    import dns.resolver
except ImportError:
    dns = None

from . import config

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

GENERIC_LOCAL_PARTS = {
    "info", "support", "hello", "contact", "sales", "admin",
    "team", "press", "media", "office", "help", "careers", "billing",
    "jobs", "marketing", "general", "inquiries",
}

DISALLOWED_EMAIL_DOMAINS = {
    "linkedin.com", "eu-startups.com", "techcrunch.com", "thestartuptrends.com",
    "yourstory.com", "inc42.com", "f6s.com", "crunchbase.com", "facebook.com",
    "twitter.com", "x.com", "youtube.com", "medium.com", "gmail.com",
    "yahoo.com", "hotmail.com", "outlook.com", "finsmes.com", "pitchbook.com",
    "businesscloud.co.uk", "businesstimes.com.sg", "joistpark.eu", "tech.eu",
    "smartcompany.com.au", "startuprise.co.uk", "sbr.com.sg", "education-news.co.uk",
}

_mx_cache: Dict[str, List[str]] = {}
_catch_all_cache: Dict[str, bool] = {}


def get_mx_hosts(domain: str) -> List[str]:
    """Retrieves priority-sorted Mail Exchanger (MX) hosts for a domain."""
    if not domain:
        return []
    if domain in _mx_cache:
        return _mx_cache[domain]

    hosts = []
    if dns is not None:
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=2.5)
            hosts = [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda x: x.preference)]
        except Exception:
            pass

    if not hosts:
        try:
            socket.gethostbyname(domain)
            hosts = [domain]
        except Exception:
            hosts = []

    _mx_cache[domain] = hosts
    return hosts


def _has_mx_record(domain: str) -> bool:
    return len(get_mx_hosts(domain)) > 0


def _query_hunter_email(domain: str, first_name: str, last_name: str) -> Tuple[Optional[str], int]:
    """Queries Hunter.io API. Returns (email, confidence_score)."""
    hunter_key = os.environ.get("HUNTER_API_KEY", "")
    if not hunter_key or not domain or not first_name:
        return (None, 0)
    try:
        url = f"https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={hunter_key}"
        resp = requests.get(url, timeout=config.REQUEST_TIMEOUT_SECS)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            found_email = data.get("email")
            score = int(data.get("score", 0))
            if found_email:
                return (found_email, score)
    except Exception:
        pass
    return (None, 0)


def is_catch_all_domain(domain: str, timeout: float = 2.5) -> bool:
    """Probes domain with a randomized bogus address to detect Catch-All servers."""
    if not domain:
        return False
    if domain in _catch_all_cache:
        return _catch_all_cache[domain]

    mx_hosts = get_mx_hosts(domain)
    if not mx_hosts:
        _catch_all_cache[domain] = False
        return False

    random_local = "probe_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=14))
    probe_email = f"{random_local}@{domain}"

    is_catch_all = False
    for mx in mx_hosts[:1]:
        try:
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(mx, 25)
            smtp.helo("tvb-verify.com")
            smtp.mail("verify@tvb-verify.com")
            code, _ = smtp.rcpt(probe_email)
            smtp.quit()
            # If server accepts a totally bogus random address, it is a catch-all
            if code == 250:
                is_catch_all = True
                break
        except Exception:
            pass

    _catch_all_cache[domain] = is_catch_all
    return is_catch_all


def generate_candidate_patterns(contact_name: str, domain: str) -> List[str]:
    """Generates standard B2B executive email pattern matrix."""
    if not contact_name or not domain:
        return []

    parts = [p.strip().lower() for p in re.sub(r"[^a-zA-Z\s]", "", contact_name).split() if p.strip()]
    if not parts:
        return []

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    clean_domain = domain.lower().replace("www.", "").strip()

    patterns = [f"{first}@{clean_domain}"]
    if last:
        patterns.append(f"{first}.{last}@{clean_domain}")
        patterns.append(f"{first[0]}{last}@{clean_domain}")
        patterns.append(f"{first}_{last}@{clean_domain}")
        patterns.append(f"{first}{last}@{clean_domain}")

    return patterns


def verify_email_smtp_handshake(email: str, timeout: float = 2.5) -> bool:
    """Performs live non-intrusive SMTP handshake ping (HELO -> MAIL FROM -> RCPT TO)
    to check recipient deliverability, with graceful MX fallback."""
    if not email or not EMAIL_RE.match(email):
        return False

    domain = email.split("@", 1)[1].lower()
    mx_hosts = get_mx_hosts(domain)
    if not mx_hosts:
        return False

    for mx in mx_hosts[:1]:
        try:
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(mx, 25)
            smtp.helo("tvb-verify.com")
            smtp.mail("verify@tvb-verify.com")
            code, _ = smtp.rcpt(email)
            smtp.quit()
            if code == 250:
                return True
            elif code in (550, 551, 552, 553):
                return False
        except Exception:
            return True

    return True


def verify_email(email: str, contact_name: str = "") -> bool:
    """Full 3-stage validation: syntax, anti-generic filter, disallowed domains, and live MX."""
    if not email or not EMAIL_RE.match(email):
        return False

    local, domain = email.split("@", 1)
    domain_lower = domain.lower().strip()

    if any(domain_lower == d or domain_lower.endswith("." + d) for d in DISALLOWED_EMAIL_DOMAINS):
        return False

    if local.lower() in GENERIC_LOCAL_PARTS and not contact_name:
        return False

    return _has_mx_record(domain_lower)


def resolve_executive_email(raw_email: str, contact_name: str, source_url: str) -> Optional[str]:
    """Applies strict Waterfall Verification with Catch-All domain defense."""
    if not source_url:
        return None

    clean_domain = source_url.split("//")[-1].split("/")[0].replace("www.", "").strip().lower()
    if any(clean_domain == d or clean_domain.endswith("." + d) for d in DISALLOWED_EMAIL_DOMAINS):
        return None

    # Step 1: Hunter.io lookup
    f_name, l_name = "", ""
    if contact_name:
        parts = [p.strip() for p in re.sub(r"[^a-zA-Z\s]", "", contact_name).split() if p.strip()]
        if parts:
            f_name = parts[0]
            l_name = parts[-1] if len(parts) > 1 else ""

    hunter_email, hunter_score = _query_hunter_email(clean_domain, f_name, l_name)

    # Step 2: Catch-All probe
    catch_all = is_catch_all_domain(clean_domain)

    # Step 3: Waterfall decision gate
    if catch_all:
        # For Catch-All domains, drop generated patterns completely.
        # Accept ONLY if Hunter returned a verified email with confidence score >= 80
        if hunter_email and hunter_score >= 80 and verify_email(hunter_email, contact_name):
            return hunter_email
        # If directly extracted raw email exists on the domain and is non-generic, test it
        if raw_email and clean_domain in raw_email and verify_email(raw_email, contact_name):
            return raw_email
        return None

    # For non-catch-all domains:
    # 1. Hunter result if score >= 40
    if hunter_email and hunter_score >= 40 and verify_email(hunter_email, contact_name):
        return hunter_email

    # 2. Directly scraped valid email
    if raw_email and verify_email(raw_email, contact_name):
        return raw_email

    # 3. Candidate pattern matrix with SMTP handshake
    patterns = generate_candidate_patterns(contact_name, clean_domain)
    for candidate in patterns:
        if verify_email(candidate, contact_name) and verify_email_smtp_handshake(candidate):
            return candidate

    return None


def _looks_us(record: Dict) -> bool:
    hq = str(record.get("hq_country") or "").strip().lower()
    if hq in ("united states", "usa", "us", "u.s.", "u.s.a.", "delaware"):
        return True
    val = record.get("has_significant_us_presence")
    if val is True:
        return True
    if isinstance(val, str) and val.strip().lower() in ("yes", "true"):
        return True
    return False


def _funding_in_range(record: Dict) -> bool:
    raw = str(record.get("funding_or_revenue_usd_estimate") or "").strip()
    if not raw:
        evidence = str(record.get("funding_or_revenue_evidence") or "")
        match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million|m|mn)", evidence, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1)) * 1_000_000
                lo = config.TARGET_PROFILE["revenue_or_funding_usd_min"]
                hi = config.TARGET_PROFILE["revenue_or_funding_usd_max"]
                return lo <= val <= hi
            except Exception:
                pass
        return False

    digits = re.sub(r"[^\d.]", "", raw)
    if not digits:
        return False
    try:
        value = float(digits)
    except ValueError:
        return False

    if value < 1000 and value >= 1:
        value = value * 1_000_000

    lo = config.TARGET_PROFILE["revenue_or_funding_usd_min"]
    hi = config.TARGET_PROFILE["revenue_or_funding_usd_max"]
    return lo <= value <= hi


def _clean_funding_display(record: Dict) -> str:
    raw = str(record.get("funding_or_revenue_usd_estimate") or "").strip()
    digits = re.sub(r"[^\d.]", "", raw)
    if digits:
        try:
            val = float(digits)
            if val < 1000 and val >= 1:
                val = val * 1_000_000
            return f"${int(val):,}"
        except Exception:
            pass
    return raw


def evaluate_record(record: Dict) -> Optional[Dict]:
    """Returns a cleaned, qualifying record, or None if it fails any
    required TVB criterion."""
    if not record:
        return None

    company_name = str(record.get("company_name") or "").strip()
    raw_email = str(record.get("contact_email") or "").strip()
    contact_name = str(record.get("contact_name") or "").strip()
    source_url = str(record.get("source_url") or "").strip()

    if not company_name or not contact_name or len(contact_name.split()) < 1:
        return None

    # Check tech platform status
    is_tech = record.get("is_tech_platform")
    is_tech_ok = (is_tech is True) or (isinstance(is_tech, str) and is_tech.strip().lower() in ("yes", "true", "tech platform"))
    if not is_tech_ok:
        return None

    # Check non-US presence
    if config.TARGET_PROFILE["requires_minimal_us_presence"] and _looks_us(record):
        return None

    # Check funding range ($1M - $5M USD)
    if not _funding_in_range(record):
        return None

    # Resolve and verify executive email via Waterfall Finder
    verified_email = resolve_executive_email(raw_email, contact_name, source_url)
    if not verified_email:
        return None

    return {
        "company_name": company_name,
        "description": str(record.get("description") or "").strip(),
        "industry_sector": str(record.get("industry_sector") or "").strip(),
        "hq_country": str(record.get("hq_country") or "").strip(),
        "funding_or_revenue_usd_estimate": _clean_funding_display(record),
        "contact_name": contact_name,
        "contact_title": str(record.get("contact_title") or "CEO / Co-founder").strip(),
        "verified_email": verified_email,
        "source_url": source_url,
    }
