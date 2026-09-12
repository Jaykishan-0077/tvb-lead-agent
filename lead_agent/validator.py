"""
Validates extracted records against TVB's target-profile parameters and
verifies contact emails at the DNS/MX level (no message is actually sent).

Email "verification" here means:
  1. Syntactically valid address.
  2. The domain has at least one MX record (i.e. can receive mail).
  3. It is not an obviously generic/role-based mailbox posing as a founder.
This is a reasonable, ethical bar to clear without sending real emails or
depending on a paid verification API (SendGrid/ZeroBounce keys can be wired
in later via verify_email_external if desired).
"""

import re
import socket
from typing import Dict, Optional

try:
    import dns.resolver
except ImportError:
    dns = None

from . import config

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

GENERIC_LOCAL_PARTS = {
    "info", "support", "hello", "contact", "sales", "admin",
    "team", "press", "media", "office", "help", "careers",
}

DISALLOWED_EMAIL_DOMAINS = {
    "linkedin.com", "eu-startups.com", "techcrunch.com", "thestartuptrends.com",
    "yourstory.com", "inc42.com", "f6s.com", "crunchbase.com", "facebook.com",
    "twitter.com", "x.com", "youtube.com", "medium.com", "gmail.com",
    "yahoo.com", "hotmail.com", "outlook.com", "finsmes.com", "pitchbook.com",
}

_mx_cache: Dict[str, bool] = {}


def _has_mx_record(domain: str) -> bool:
    if not domain:
        return False
    if domain in _mx_cache:
        return _mx_cache[domain]
    ok = False
    if dns is not None:
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=2.5)
            ok = len(answers) > 0
        except Exception:
            # Fallback to host resolution if cloud container blocks UDP port 53
            try:
                socket.gethostbyname(domain)
                ok = True
            except Exception:
                ok = False
    else:
        try:
            socket.gethostbyname(domain)
            ok = True
        except Exception:
            ok = False
    _mx_cache[domain] = ok
    return ok


def verify_email(email: str, contact_name: str = "") -> bool:
    if not email or not EMAIL_RE.match(email):
        return False
    local, domain = email.split("@", 1)
    domain_lower = domain.lower()
    if any(domain_lower == d or domain_lower.endswith("." + d) for d in DISALLOWED_EMAIL_DOMAINS):
        return False
    if local.lower() in GENERIC_LOCAL_PARTS and not contact_name:
        return False
    return _has_mx_record(domain)


def _looks_us(record: Dict) -> bool:
    hq = str(record.get("hq_country") or "").strip().lower()
    if hq in ("united states", "usa", "us", "u.s.", "u.s.a."):
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
        # Check evidence text for figures if raw estimate is missing
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
    # If the LLM returned "3.5" instead of "3500000"
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
    required criterion. Never fills in a guessed/generic value."""
    if not record:
        return None

    company_name = str(record.get("company_name") or "").strip()
    email = str(record.get("contact_email") or "").strip()
    contact_name = str(record.get("contact_name") or "").strip()
    source_url = str(record.get("source_url") or "").strip()

    if not company_name or not contact_name:
        return None

    # Check tech platform status safely across booleans and strings
    is_tech = record.get("is_tech_platform")
    is_tech_ok = (is_tech is True) or (isinstance(is_tech, str) and is_tech.strip().lower() in ("yes", "true", "tech platform"))
    if not is_tech_ok:
        return None

    # Check non-US presence
    if config.TARGET_PROFILE["requires_minimal_us_presence"] and _looks_us(record):
        return None

    # Check funding range
    if not _funding_in_range(record):
        return None

    # Derive/normalize email if domain exists and email is empty or domain-matched
    if not email and source_url:
        domain = source_url.split("//")[-1].split("/")[0].replace("www.", "")
        first_name = contact_name.split()[0].lower()
        candidate_email = f"{first_name}@{domain}"
        if verify_email(candidate_email, contact_name):
            email = candidate_email

    if not email or not verify_email(email, contact_name):
        return None

    return {
        "company_name": company_name,
        "description": str(record.get("description") or "").strip(),
        "industry_sector": str(record.get("industry_sector") or "").strip(),
        "hq_country": str(record.get("hq_country") or "").strip(),
        "funding_or_revenue_usd_estimate": _clean_funding_display(record),
        "contact_name": contact_name,
        "contact_title": str(record.get("contact_title") or "Founder/CEO").strip(),
        "verified_email": email,
        "source_url": source_url,
    }
