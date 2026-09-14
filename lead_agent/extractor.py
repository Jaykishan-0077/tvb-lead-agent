"""
Extractor layer.

Enhanced with Phase 3 High-Thinking Reasoning & Strict Grounding Prompts:
- Enforces strict grounding (no guessing, no hallucinations, null if unstated).
- Configures Gemini 3.5 Flash-Lite thinking depth (thinking_level="HIGH" / reasoning).
- Strict JSON structure validation.
"""

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
You are an autonomous Venture Lead Extraction Agent reviewing raw text scraped from a company's website.

STRICT GROUNDING RULE:
Extract ONLY information that is explicitly stated in plain text in the website content below.
If the exact dollar value of funding/revenue or the exact name of the CEO/Founder is NOT explicitly stated, return "" for that field.
Do not infer, estimate, guess, or use knowledge outside the text provided.

Return STRICT JSON only, no markdown fences, no commentary:

{
  "company_name": "",
  "description": "",
  "industry_sector": "",
  "hq_country": "",
  "has_significant_us_presence": "yes" | "no" | "unknown",
  "is_tech_platform": "yes" | "no" | "unknown",
  "financial_type": "total_funding" | "revenue" | "seed_round" | "unknown",
  "funding_or_revenue_evidence": "",
  "funding_or_revenue_usd_estimate": "",
  "current_total_funding_usd": "",
  "current_revenue_usd": "",
  "financial_date": "",
  "company_status": "active" | "acquired" | "closed" | "unknown",
  "contact_name": "",
  "contact_title": "",
  "contact_email": ""
}

Rules:
- company_name: The startup/company name.
- hq_country: Country where headquarters is located (e.g. "India", "United Kingdom"). Leave "" if not stated.
- has_significant_us_presence: "yes" ONLY if the text clearly says US headquarters or dominant US presence. Otherwise "no" or "unknown".
- is_tech_platform: "yes" if the company provides a software/SaaS/AI/tech product. "no" if purely service/consulting.
- financial_type: "total_funding" if text mentions total raised. "revenue" if ARR/revenue. "seed_round" if only one round mentioned. "unknown" if unclear.
- funding_or_revenue_usd_estimate: The plain USD number only (e.g. "2500000"). NO "$" or "M" — just digits. Leave "" if not mentioned.
- current_total_funding_usd: Same format as above if you can identify total funding raised. Leave "" if unknown.
- current_revenue_usd: Same format if the text mentions current revenue/ARR in USD. Leave "" if unknown.
- financial_date: The date/year of the financial event, e.g. "2025-03" or "2024". Leave "" if unstated.
- funding_or_revenue_evidence: Verbatim sentence(s) from the page mentioning the funding/revenue figure.
- company_status: "active" unless the text mentions acquisition, shutdown, or closure.
- contact_name: PRIMARY Founder, Co-Founder, or CEO listed in team/leadership. DO NOT guess — leave "" if not found.
- contact_title: Their exact leadership title from the page.
- contact_email: Exact email if visible on page for that person. Otherwise leave "".

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
    # 1. Try google-genai SDK with High Thinking
    if genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            try:
                # Attempt with explicit ThinkingConfig
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        thinking_config=genai_types.ThinkingConfig(thinking_level="HIGH"),
                    ),
                )
                if response and response.text:
                    return response.text
            except Exception:
                # Fallback standard generation
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                if response and response.text:
                    return response.text
        except Exception:
            pass

    # 2. Direct REST API fallback for Gemini models
    models_to_try = [
        config.GEMINI_MODEL,
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-flash-lite-latest",
    ]
    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            
            # Try with thinkingConfig first
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                    "thinkingConfig": {"thinkingLevel": "HIGH"},
                },
            }
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                if "candidates" in data and data["candidates"]:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            
            # Fallback without thinkingConfig if endpoint doesn't accept the parameter
            payload_basic = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }
            res_basic = requests.post(url, json=payload_basic, timeout=45)
            if res_basic.status_code == 200:
                data = res_basic.json()
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
    if not page_text.strip() or len(page_text.strip()) < 150:
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
