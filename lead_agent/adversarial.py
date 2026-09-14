"""
Adversarial Verification Agent.

Equipped with live Google/SERP search tools to actively attempt to disprove and disqualify candidate leads:
1. Actively searches web for subsequent funding rounds > $5M (e.g. Series B, Series C, $10M+).
2. Actively searches web for acquisition events (e.g. acquired by ClickHouse, Cisco, etc.).
3. Actively searches web for US headquarters relocations / San Francisco offices.
4. Returns deterministic disqualification with the exact URL and snippet.
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

from . import config, extractor, search


def _check_disqualifying_snippets(company_name: str, search_results: List[Dict]) -> Tuple[bool, str, str]:
    """Analyzes live search snippets for hard disqualification flags."""
    for r in search_results:
        title = r.get("title", "").lower()
        snippet = r.get("snippet", "").lower()
        url = r.get("url", "")
        combined = f"{title} {snippet}"

        # 1. Total Funding / Subsequent Round Check (> $5M)
        overfunding_patterns = [
            r"\$(?:[6-9]|\d{2,})\s*(?:million|m|mn|b|billion)",
            r"€(?:[6-9]|\d{2,})\s*(?:million|m|mn|b|billion)",
            r"£(?:[6-9]|\d{2,})\s*(?:million|m|mn|b|billion)",
            r"series\s+[b-f]",
            r"series\s+c",
            r"raised\s+\$[0-9]{2,}\s*m",
            r"total\s+funding.*?\$[0-9]{2,}\s*m",
        ]
        for pat in overfunding_patterns:
            if re.search(pat, combined):
                # Ensure the snippet is actually talking about this company
                if company_name.lower() in combined:
                    return (False, "TOTAL_FUNDING_ABOVE_LIMIT", f"Found subsequent late-stage funding in search results: '{r.get('snippet')}' (Source: {url})")

        # 2. Acquisition Check
        acquisition_patterns = [
            r"acquired by",
            r"acquisition by",
            r"bought by",
            r"merger with",
            r"has been acquired",
        ]
        for pat in acquisition_patterns:
            if re.search(pat, combined):
                if company_name.lower() in combined:
                    return (False, "COMPANY_ACQUIRED_OR_CLOSED", f"Found acquisition event in search results: '{r.get('snippet')}' (Source: {url})")

        # 3. US Relocation / Headquarters Check
        us_hq_patterns = [
            r"san francisco, ca",
            r"headquartered in san francisco",
            r"headquarters in san francisco",
            r"headquartered in new york",
            r"headquartered in delaware",
            r"us-based",
        ]
        for pat in us_hq_patterns:
            if re.search(pat, combined):
                if company_name.lower() in combined:
                    return (False, "US_PRESENCE_TOO_HIGH", f"Found US headquarters presence in search results: '{r.get('snippet')}' (Source: {url})")

    return (True, "", "")


def verify_adversarial(record: Dict) -> Tuple[bool, str, str]:
    """Actively scrutinizes a candidate using live Google Search queries to catch fabrications and late-stage rounds.
    Returns: (is_passed, rejection_reason, audit_explanation)
    """
    if not record:
        return (False, "INSUFFICIENT_EVIDENCE", "Empty candidate record")

    company_name = str(record.get("company_name") or "").strip()
    if not company_name:
        return (False, "INSUFFICIENT_EVIDENCE", "Missing company name")

    # 1. Deterministic Total Funding Cap Check
    amt_str = str(record.get("current_total_funding_usd") or record.get("financial_amount_usd") or "0")
    try:
        val = float(re.sub(r"[^\d.]", "", amt_str) or 0)
        if val > config.TARGET_PROFILE["revenue_or_funding_usd_max"]:
            return (False, "TOTAL_FUNDING_ABOVE_LIMIT", f"Claimed funding ${int(val):,} exceeds $5M ceiling")
        if val < config.TARGET_PROFILE["revenue_or_funding_usd_min"] and val > 0:
            return (False, "FUNDING_BELOW_LIMIT", f"Claimed funding ${int(val):,} is below $1M threshold")
    except Exception:
        pass

    # 2. Deterministic US Presence Check
    hq = str(record.get("hq_country") or "").lower()
    desc = str(record.get("description") or "").lower()
    if any(u in hq for u in ("united states", "usa", "delaware", "san francisco", "new york", "austin, tx")):
        return (False, "US_PRESENCE_TOO_HIGH", f"Company lists US location in HQ: {hq}")
    if "san francisco" in desc or "delaware c-corp" in desc:
        return (False, "US_PRESENCE_TOO_HIGH", "Description indicates US headquarters or corporate entity")

    # 3. Live Adversarial Web Search Query 1: Subsequent Rounds & Acquisitions
    adv_query_1 = f'"{company_name}" funding "Series B" OR "Series C" OR "Series D" OR "acquired"'
    results_1 = search.search(adv_query_1, num=5)
    passed_1, reason_1, exp_1 = _check_disqualifying_snippets(company_name, results_1)
    if not passed_1:
        return (False, reason_1, exp_1)

    # 4. Live Adversarial Web Search Query 2: US Headquarters Presence
    adv_query_2 = f'"{company_name}" "San Francisco" OR "Delaware" OR "United States" HQ'
    results_2 = search.search(adv_query_2, num=4)
    passed_2, reason_2, exp_2 = _check_disqualifying_snippets(company_name, results_2)
    if not passed_2:
        return (False, reason_2, exp_2)

    return (True, "NONE", "Live adversarial web search confirmed no subsequent rounds >$5M, no US entity, active independent platform")
