import json
import os
import re
from typing import Dict, Optional

import requests

from . import config

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None

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
    text = re.sub(r"^```(json)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    return text


def _extract_via_gemini(api_key: str, prompt: str) -> Optional[str]:
    # 1. Try google-genai SDK
    if genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return response.text
        except Exception:
            pass

    # 2. Direct REST API fallback for Gemini
    models_to_try = [config.GEMINI_MODEL, "gemini-flash-latest", "gemini-2.5-flash-lite"]
    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                if "candidates" in data and data["candidates"]:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except Exception:
            continue
    return None


def _extract_via_anthropic(api_key: str, prompt: str) -> Optional[str]:
    if anthropic is None:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
    except Exception:
        return None


def _extract_via_openai(api_key: str, prompt: str) -> Optional[str]:
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None


def extract_record(page_text: str, source_url: str) -> Optional[Dict]:
    if not page_text.strip():
        return None

    prompt = EXTRACTION_INSTRUCTIONS.replace(
        "{page_text}", page_text[: config.PAGE_TEXT_CHAR_LIMIT]
    )
    raw_response = None

    # Determine provider
    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()

    if gemini_key:
        raw_response = _extract_via_gemini(gemini_key, prompt)
    elif anthropic_key:
        raw_response = _extract_via_anthropic(anthropic_key, prompt)
    elif openai_key:
        raw_response = _extract_via_openai(openai_key, prompt)

    if not raw_response:
        return None

    try:
        clean_json = _strip_code_fences(raw_response)
        data = json.loads(clean_json)
        data["source_url"] = source_url
        return data
    except Exception:
        return None
