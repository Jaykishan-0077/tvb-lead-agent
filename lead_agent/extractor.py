"""
Turns raw scraped website text into a structured candidate record using an
LLM, with an explicit instruction to leave any unverified field blank rather
than guess (matches TVB's stated preference).
"""

import json
import re
from typing import Dict, Optional

from . import config

try:
    import anthropic
except ImportError:
    anthropic = None

EXTRACTION_INSTRUCTIONS = """\
You are reviewing raw text scraped from a company's website (home page plus
about/team/contact pages if available). Extract ONLY information that is
explicitly stated or very strongly implied in the text below. Do not invent
or guess. If a field is not clearly supported by the text, return an empty
string for it.

Return STRICT JSON only, no markdown fences, no commentary, matching this
schema exactly:

{
  "company_name": "",
  "description": "",
  "industry_sector": "",
  "hq_country": "",
  "has_significant_us_presence": "yes" | "no" | "unknown",
  "is_tech_platform": "yes" | "no" | "unknown",
  "funding_or_revenue_evidence": "",
  "funding_or_revenue_usd_estimate": "",
  "contact_name": "",
  "contact_title": "",
  "contact_email": ""
}

Rules:
- contact_name/contact_email must be a named CEO or Co-founder specifically,
  not a generic role like "info@" or "support@", unless that generic address
  is explicitly attributed to a named founder in the text.
- funding_or_revenue_usd_estimate should be a plain number in USD if a
  specific figure is mentioned (e.g. "2500000"), otherwise leave blank.
- has_significant_us_presence should be "yes" only if the text clearly
  describes US headquarters, a large US office/team, or the company
  positions itself as a US company.
- Never fabricate an email address. Only report one if it literally appears
  in the text.

WEBSITE TEXT:
\"\"\"
{page_text}
\"\"\"
"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def extract_record(page_text: str, source_url: str) -> Optional[Dict]:
    api_key = config.get_anthropic_api_key()
    if not api_key or anthropic is None or not page_text.strip():
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = EXTRACTION_INSTRUCTIONS.format(page_text=page_text[:6000])
        resp = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        raw = _strip_code_fences(raw)
        data = json.loads(raw)
        data["source_url"] = source_url
        return data
    except Exception:
        return None
