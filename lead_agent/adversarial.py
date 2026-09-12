"""
Adversarial Verification Agent.

Acts as a dedicated 'red team' verifier designed to aggressively scrutinize
promising leads and attempt to find disqualifying evidence:
- Total historical funding exceeding $5M USD (e.g. subsequent Series A/B/C rounds or stealth rounds).
- US tax-flip / relocation / San Francisco GTM office / Delaware legal parent.
- Company acquired (e.g. Langfuse acquired by ClickHouse) or defunct.
- Outdated executive leadership (former CEO / transitioned founder / PR agency).
- Non-platform agency or consulting service models.
"""

import json
import os
import re
from typing import Dict, Optional, Tuple

import requests

from . import config, extractor


def _run_adversarial_llm_check(record: Dict) -> Tuple[bool, str]:
    """Runs a dedicated hostile red-team prompt against the candidate lead."""
    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()

    if not any([gemini_key, anthropic_key, openai_key]):
        return (True, "")

    c_name = record.get("company_name", "")
    desc = record.get("description", "")
    fin_amt = record.get("financial_amount_usd", "")
    fin_ev = record.get("financial_evidence", "")
    total_fund = record.get("current_total_funding_usd", "")
    hq = record.get("hq_country", "")
    ceo = record.get("contact_name", "")
    email = record.get("email", "")
    url = record.get("source_url", "")

    adversarial_prompt = (
        f"You are the Hostile Adversarial Lead Verification Auditor for The Venture Build (TVB).\n"
        f"YOUR SINGLE MANDATE IS TO ATTEMPT TO DISQUALIFY THIS STARTUP. Find ANY evidence that violates TVB rules.\n\n"
        f"STRICT TVB QUALIFICATION RULES:\n"
        f"1. TOTAL Current Funding / Revenue Cap: Current total funding raised or current revenue MUST be strictly between $1M and $5M USD.\n"
        f"   - If the company subsequently raised a Series A/B/C, or total funding exceeds $5M USD (e.g., Omni, Dust, Koywe, Payflow, Retorio), REJECT.\n"
        f"   - If total funding is under $1M (e.g., Sanctifly, Fyorin), REJECT.\n"
        f"2. Active Status: Must be an active, independent company. If acquired (e.g. Langfuse acquired by ClickHouse) or shuttered, REJECT.\n"
        f"3. US Presence: Must have minimal-to-no US presence. If US HQ, San Francisco office, Delaware parent, or primary US operations (e.g., Kombai), REJECT.\n"
        f"4. Tech Platform: Must be a proprietary software/SaaS platform. If consulting/agency/service, REJECT.\n"
        f"5. Leadership: Person must be the active, current CEO/Co-founder (e.g., not former CEO, advisor, or wrong founder like LXME/Flowpay discrepancy).\n"
        f"6. Email Attribution: Email must belong to this exact named person, not a generic box.\n\n"
        f"CANDIDATE UNDER SCRUTINY:\n"
        f"- Company: {c_name} (URL: {url})\n"
        f"- Description: {desc}\n"
        f"- Financial Data: {fin_amt} (Total Funding: {total_fund} | Evidence: {fin_ev})\n"
        f"- Claimed HQ: {hq}\n"
        f"- Claimed CEO: {ceo}\n"
        f"- Claimed Email: {email}\n\n"
        f"DECISION FORMAT:\n"
        f"Return STRICT JSON only:\n"
        f"{{\n"
        f"  \"is_disqualified\": true | false,\n"
        f"  \"rejection_reason\": \"TOTAL_FUNDING_ABOVE_LIMIT\" | \"FUNDING_BELOW_LIMIT\" | \"COMPANY_ACQUIRED_OR_CLOSED\" | \"US_PRESENCE_TOO_HIGH\" | \"CEO_NOT_VERIFIED\" | \"TECH_PLATFORM_NOT_VERIFIED\" | \"NONE\",\n"
        f"  \"explanation\": \"Explicit factual evidence disproving qualification...\"\n"
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
                reason = data.get("rejection_reason", "ADVERSARIAL_FAILURE")
                return (False, reason)
        except Exception:
            pass

    return (True, "")


def verify_adversarial(record: Dict) -> Tuple[bool, str]:
    """Applies programmatic deterministic heuristics + adversarial LLM audit."""
    if not record:
        return (False, "INSUFFICIENT_EVIDENCE")

    # 1. Deterministic Total Funding Cap Check
    amt_str = str(record.get("current_total_funding_usd") or record.get("financial_amount_usd") or "0")
    try:
        val = float(re.sub(r"[^\d.]", "", amt_str) or 0)
        if val > config.TARGET_PROFILE["revenue_or_funding_usd_max"]:
            return (False, "TOTAL_FUNDING_ABOVE_LIMIT")
        if val < config.TARGET_PROFILE["revenue_or_funding_usd_min"] and val > 0:
            return (False, "FUNDING_BELOW_LIMIT")
    except Exception:
        pass

    # 2. Deterministic US Presence Check
    hq = str(record.get("hq_country") or "").lower()
    desc = str(record.get("description") or "").lower()
    if any(u in hq for u in ("united states", "usa", "delaware", "san francisco", "new york", "austin, tx")):
        return (False, "US_PRESENCE_TOO_HIGH")
    if "san francisco" in desc or "delaware c-corp" in desc:
        return (False, "US_PRESENCE_TOO_HIGH")

    # 3. Deterministic Acquired / Defunct Check
    if any(s in desc for s in ("acquired by", "merged with", "closed down", "defunct", "ceased operations")):
        return (False, "COMPANY_ACQUIRED_OR_CLOSED")

    # 4. Adversarial Red-Team Reasoning Check
    passed, reason = _run_adversarial_llm_check(record)
    if not passed:
        return (False, reason)

    return (True, "")
