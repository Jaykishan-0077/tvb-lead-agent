"""
Orchestrates a full agent run:

  1. Autonomous Venture Scouting across TVB Orbits & Non-US Hubs ($1M-$5M, tech platform, named founder).
  2. Multi-Query Live Web Search & Scraping (DuckDuckGo / Serper).
  3. Structured Extraction & Live DNS MX Validation.

Implemented as a streaming generator that yields real-time log, progress, and lead events.
"""

import json
import random
import requests
from typing import Dict, Generator, List

from . import config, extractor, query_generator, scraper, search, validator


def _scout_ai_candidates(batch_size: int = 15) -> List[Dict]:
    """Uses LLM to scout recently funded non-US tech platform scale-ups meeting TVB's profile."""
    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()

    sectors_sample = random.sample(config.SECTORS, min(6, len(config.SECTORS)))
    regions_sample = random.sample(config.REGIONS, min(6, len(config.REGIONS)))

    prompt = (
        f"You are the autonomous Venture Lead Scout for The Venture Build (TVB).\n"
        f"Identify {batch_size} real, verified non-US tech platform startups matching ALL 4 criteria:\n"
        f"1. Revenue or funding raised: strictly between $1 Million and $5 Million USD (e.g. Seed / Pre-Series A / Series A)\n"
        f"2. Sector: B2B SaaS, Applied AI, Digital Health, EdTech, FinTech, Cybersecurity, Digital Twin, or Travel Tech ({', '.join(sectors_sample)})\n"
        f"3. Geography: Headquartered in non-US regions like {', '.join(regions_sample)} (e.g. India, UK, France, Germany, UAE, Singapore) with zero/minimal US presence.\n"
        f"4. Executive: Known CEO or Co-founder full name, official company website, and their verified company email address (e.g. first@domain.com or first.last@domain.com on their official domain).\n\n"
        f"Return STRICT JSON array of objects with keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"company_name\": \"...\",\n"
        f"    \"description\": \"...\",\n"
        f"    \"industry_sector\": \"...\",\n"
        f"    \"hq_country\": \"...\",\n"
        f"    \"has_significant_us_presence\": \"no\",\n"
        f"    \"is_tech_platform\": \"yes\",\n"
        f"    \"funding_or_revenue_evidence\": \"...\",\n"
        f"    \"funding_or_revenue_usd_estimate\": \"...\",\n"
        f"    \"contact_name\": \"...\",\n"
        f"    \"contact_title\": \"CEO / Co-founder\",\n"
        f"    \"contact_email\": \"...\",\n"
        f"    \"source_url\": \"https://...\"\n"
        f"  }}\n"
        f"]"
    )

    raw_text = ""
    try:
        if gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        elif anthropic_key:
            raw_text = extractor._extract_via_anthropic(anthropic_key, prompt)
        elif openai_key:
            raw_text = extractor._extract_via_openai(openai_key, prompt)
    except Exception:
        pass

    if raw_text:
        try:
            clean = extractor._strip_code_fences(raw_text)
            records = json.loads(clean)
            if isinstance(records, list):
                return records
        except Exception:
            pass
    return []


def run(
    min_leads: int = None,
    max_domains: int = None,
    max_queries: int = None,
) -> Generator[Dict, None, None]:
    min_leads = min_leads or config.MIN_QUALIFYING_LEADS
    max_domains = max_domains or config.MAX_DOMAINS_TO_SCAN
    max_queries = max_queries or config.MAX_SEARCH_QUERIES

    seen_domains = set()
    leads = []
    scanned = 0

    # Phase 1: Autonomous AI Venture Deal Scouting
    yield {"type": "log", "message": "Phase 1: Initializing autonomous venture deal discovery..."}
    ai_candidates = _scout_ai_candidates(batch_size=min(20, min_leads + 5))
    if ai_candidates:
        yield {
            "type": "log",
            "message": f"Scouted {len(ai_candidates)} initial candidate venture deals across non-US regions.",
        }
        for cand in ai_candidates:
            if len(leads) >= min_leads:
                break
            domain = scraper.domain_of(cand.get("source_url") or "")
            if domain:
                seen_domains.add(domain)
            scanned += 1
            yield {"type": "progress", "scanned": scanned, "total": max_domains}
            
            c_name = cand.get("company_name", "Candidate")
            yield {"type": "log", "message": f"  -> Evaluating candidate: {c_name} ({cand.get('hq_country', 'Global')})"}

            # Validate against all 4 parameters & verify email DNS/MX
            qualifying = validator.evaluate_record(cand)
            if qualifying:
                leads.append(qualifying)
                yield {"type": "lead", "record": qualifying}
                yield {
                    "type": "log",
                    "message": f"     ✓ Verified lead: {qualifying['company_name']} "
                    f"({qualifying['funding_or_revenue_usd_estimate']}, {qualifying['contact_name']} <{qualifying['verified_email']}>)",
                }
            else:
                yield {"type": "log", "message": f"     ✗ {c_name} did not pass strict parameter/MX validation"}

    # Phase 2: Live Multi-Query Web Search & Deep Crawling
    if len(leads) < min_leads:
        yield {"type": "log", "message": "Phase 2: Generating live search queries across TVB Orbits..."}
        queries = query_generator.generate_queries(max_queries)
        yield {
            "type": "log",
            "message": f"Generated {len(queries)} multi-vector queries across {len(config.SECTORS)} sectors.",
        }

        for qi, q in enumerate(queries, start=1):
            if len(leads) >= min_leads or scanned >= max_domains:
                break

            yield {"type": "log", "message": f"[{qi}/{len(queries)}] Live Web Search: {q}"}
            results = search.search(q)

            for r in results:
                if len(leads) >= min_leads or scanned >= max_domains:
                    break
                url = r.get("url") or ""
                if not url:
                    continue
                domain = scraper.domain_of(url)
                if not domain or domain in seen_domains:
                    continue
                seen_domains.add(domain)
                scanned += 1

                yield {
                    "type": "progress",
                    "scanned": scanned,
                    "total": max_domains,
                }
                yield {"type": "log", "message": f"  -> Scraping: {domain}"}

                page_text = scraper.gather_site_text(url)
                if not page_text or len(page_text) < 150:
                    yield {"type": "log", "message": f"     (skipped, thin/empty content)"}
                    continue

                record = extractor.extract_record(page_text, source_url=url)
                if not record:
                    yield {"type": "log", "message": "     (extraction skipped)"}
                    continue

                qualifying = validator.evaluate_record(record)
                if qualifying:
                    leads.append(qualifying)
                    yield {"type": "lead", "record": qualifying}
                    yield {
                        "type": "log",
                        "message": f"     ✓ Verified lead: {qualifying['company_name']} "
                        f"({qualifying['funding_or_revenue_usd_estimate']}, {qualifying['verified_email']})",
                    }
                else:
                    name = record.get("company_name") or domain
                    yield {
                        "type": "log",
                        "message": f"     ✗ {name} did not meet all TVB parameters, skipped",
                    }

    yield {
        "type": "log",
        "message": f"Discovery complete: Found {len(leads)} fully qualifying leads.",
    }
    yield {"type": "done", "leads": leads}
