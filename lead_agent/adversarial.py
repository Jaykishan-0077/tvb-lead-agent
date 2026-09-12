"""
Adversarial Verification Agent.

Acts as a dedicated 'red team' verifier designed to aggressively scrutinize
promising leads and attempt to find disqualifying evidence:
- Total historical funding exceeding $5M USD (e.g. stealth Series B/C).
- US tax-flip / relocation / major US corporate entity.
- Outdated executive leadership (former CEO / transitioned founder).
- Non-platform agency or consulting service models.
"""

import json
import os
import re
from typing import Dict, Optional, Tuple

import requests

from . import config, extractor


def _run_adversarial_llm_check(record: Dict) -> Tuple[bool, str]:
    """Runs a dedicated adversarial prompt against the record."""
    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()

    if not any([gemini_key, anthropic_key, openai_key]):
        return (True, "")

    c_name = record.get("company_name", "")
    desc = record.get("description", "")
    fin_amt = record.get("financial_amount_usd", "")
    fin_ev = record.get("financial_evidence", "")
    hq = record.get("hq_country", "")
    ceo = record.get("contact_name", "")
    url = record.get("source_url", "")

    adversarial_prompt = (
        f"You are the Adversarial Lead Verification Auditor for The Venture Build (TVB).\n"
        f"YOUR JOB IS TO TRY TO DISQUALIFY THIS STARTUP. Find any reason it violates TVB criteria.\n\n"
        f"TVB CRITERIA:\n"
        f"1. Total funding or revenue must be STRICTLY between $1M and $5M USD (If the company raised >$5M total, Series B+, or is a unicorn, REJECT).\n"
        f"2. Must be a tech-enabled SaaS/software platform (If pure consulting/agency/outsourcing, REJECT).\n"
        f"3. Must have minimal-to-no US presence (If US HQ, Delaware parent, or primary US entity, REJECT).\n"
        f"4. Executive must be the current, real Founder/CEO (If former CEO or ungrounded, REJECT).\n\n"
        f"CANDIDATE DATA:\n"
        f"- Company: {c_name} ({url})\n"
        f"- Description: {desc}\n"
        f"- Claimed Funding/Revenue: {fin_amt} (Evidence: {fin_ev})\n"
        f"- Claimed HQ: {hq}\n"
        f"- Claimed CEO: {ceo}\n\n"
        f"DECISION FORMAT:\n"
        f"Return STRICT JSON only:\n"
        f"{{\n"
        f"  \"is_disqualified\": true | false,\n"
        f"  \"rejection_reason\": \"FUNDING_ABOVE_LIMIT\" | \"US_PRESENCE_TOO_HIGH\" | \"CEO_NOT_VERIFIED\" | \"TECH_PLATFORM_NOT_VERIFIED\" | \"NONE\",\n"
        f"  \"explanation\": \"...\"\n"
        f"}}"
    )

    raw = None
    try:
        if gemini_key:
            raw = extractor._extract_via_gemini(gemini_key, adversarial_prompt)
        elif anthropic_key:
            raw = extractor._extract_via_anthropic(anthropic_key, adversarial_prompt)
        elif openai_key:
            raw = extractor._extract_via_openai(openai_key, adversarial_prompt)
    except Exception:
        pass

    if raw:
        try:
            clean = extractor._strip_code_fences(raw)
            data = json.loads(clean)
            if data.get("is_disqualified") is True:
                reason = data.get("rejection_reason", "INSUFFICIENT_EVIDENCE")
                return (False, reason)
        except Exception:
            pass

    return (True, "")


def verify_adversarial(record: Dict) -> Tuple[bool, str]:
    """Applies programmatic deterministic heuristics + adversarial LLM audit."""
    if not record:
        return (False, "INSUFFICIENT_EVIDENCE")

    # 1. Deterministic Funding Cap Check
    amt_str = str(record.get("financial_amount_usd") or "0")
    try:
        val = float(re.sub(r"[^\d.]", "", amt_str) or 0)
        if val > config.TARGET_PROFILE["revenue_or_funding_usd_max"]:
            return (False, "FUNDING_ABOVE_LIMIT")
        if val < config.TARGET_PROFILE["revenue_or_funding_usd_min"] and val > 0:
            return (False, "FUNDING_BELOW_LIMIT")
    except Exception:
        pass

    # 2. Deterministic US Presence Check
    hq = str(record.get("hq_country") or "").lower()
    if any(u in hq for u in ("united states", "usa", "delaware", "san francisco", "new york")):
        return (False, "US_PRESENCE_TOO_HIGH")

    # 3. Adversarial Red-Team Reasoning Check
    passed, reason = _run_adversarial_llm_check(record)
    if not passed:
        return (False, reason)

    return (True, "")
