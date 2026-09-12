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

_mx_cache: Dict[str, bool] = {}


def _has_mx_record(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    ok = False
    if dns is not None:
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
            ok = len(answers) > 0
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
    if local.lower() in GENERIC_LOCAL_PARTS and not contact_name:
        # Generic mailbox with no named person behind it -> not a verified
        # personal contact for our purposes.
        return False
    return _has_mx_record(domain)


def _looks_us(record: Dict) -> bool:
    hq = (record.get("hq_country") or "").strip().lower()
    if hq in ("united states", "usa", "us", "u.s.", "u.s.a."):
        return True
    if (record.get("has_significant_us_presence") or "").lower() == "yes":
        return True
    return False


def _funding_in_range(record: Dict) -> bool:
    raw = str(record.get("funding_or_revenue_usd_estimate") or "").strip()
    if not raw:
        # No explicit figure -> can't confirm the $1M-$5M requirement.
        return False
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits:
        return False
    try:
        value = float(digits)
    except ValueError:
        return False
    lo = config.TARGET_PROFILE["revenue_or_funding_usd_min"]
    hi = config.TARGET_PROFILE["revenue_or_funding_usd_max"]
    return lo <= value <= hi


def evaluate_record(record: Dict) -> Optional[Dict]:
    """Returns a cleaned, qualifying record, or None if it fails any
    required criterion. Never fills in a guessed/generic value."""
    if not record:
        return None

    company_name = (record.get("company_name") or "").strip()
    email = (record.get("contact_email") or "").strip()
    contact_name = (record.get("contact_name") or "").strip()

    if not company_name or not email or not contact_name:
        return None

    if config.TARGET_PROFILE["requires_named_contact"] and not contact_name:
        return None

    if (record.get("is_tech_platform") or "").lower() != "yes":
        return None

    if config.TARGET_PROFILE["requires_minimal_us_presence"] and _looks_us(record):
        return None

    if not _funding_in_range(record):
        return None

    if not verify_email(email, contact_name):
        return None

    return {
        "company_name": company_name,
        "description": (record.get("description") or "").strip(),
        "industry_sector": (record.get("industry_sector") or "").strip(),
        "hq_country": (record.get("hq_country") or "").strip(),
        "funding_or_revenue_usd_estimate": record.get(
            "funding_or_revenue_usd_estimate", ""
        ),
        "contact_name": contact_name,
        "contact_title": (record.get("contact_title") or "").strip(),
        "verified_email": email,
        "source_url": record.get("source_url", ""),
    }
