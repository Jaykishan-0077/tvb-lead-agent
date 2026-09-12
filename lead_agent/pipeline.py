"""
Orchestrates a fully autonomous agent run:

  1. Autonomous Multi-Vector AI Venture Scouting (Dynamic sector × region batches).
  2. Live Web Search & Autonomous Deep Web Crawling (DuckDuckGo / Serper).
  3. Structured Extraction & Live DNS MX Validation.

Zero hardcoded seeds or static lists: 100% discovered dynamically on the fly.
Continues comprehensive scanning to maximize discovered qualifying leads beyond the minimum threshold.
"""

import json
import random
from typing import Dict, Generator, List

from . import config, extractor, query_generator, scraper, search, validator


def _scout_ai_batch(target_count: int = 6, sector_hint: str = "", region_hint: str = "") -> List[Dict]:
    """Uses LLM to dynamically scout real non-US tech platform scale-ups meeting TVB's profile."""
    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()

    if not any([gemini_key, anthropic_key, openai_key]):
        return []

    sectors = [sector_hint] if sector_hint else random.sample(config.SECTORS, min(4, len(config.SECTORS)))
    regions = [region_hint] if region_hint else random.sample(config.REGIONS, min(4, len(config.REGIONS)))

    prompt = (
        f"You are the autonomous Venture Lead Scout for The Venture Build (TVB).\n"
        f"Discover {target_count} REAL, active non-US tech platform startups matching ALL 4 TVB criteria:\n"
        f"1. Recent Funding/Revenue: strictly between $1 Million and $5 Million USD (focus on verified 2024–2026 Seed / Pre-Series A / Series A or current ARR).\n"
        f"2. Sector: Focus on {', '.join(sectors)}.\n"
        f"3. Geography: Headquartered in non-US countries like {', '.join(regions)} (India, UK, France, Germany, Singapore, UAE, etc.) with minimal-to-no presence in the US (exclude Delaware/US tax-flips).\n"
        f"4. Leadership: The exact PRIMARY Founder, Co-Founder, or CEO full name (e.g., Kshitij Jain for Joveo, Armin Moradi for Qashio - NOT secondary VPs, marketing leads, or PR contacts), their official company website, and their verified corporate email address.\n\n"
        f"STRICT GROUNDING RULE: If exact revenue/funding or CEO name is unverified or ambiguous, omit or return empty. Do not guess or invent flat dummy numbers.\n\n"
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

    raw_text = None
    try:
        if gemini_key:
            raw_text = extractor._extract_via_gemini(gemini_key, prompt)
        elif anthropic_key:
            raw_text = extractor._extract_via_anthropic(anthropic_key, prompt)
        elif openai_key:
            raw_text = extractor._extract_via_openai(openai_key, prompt)
    except Exception:
        pass

    candidates = []
    if raw_text:
        try:
            clean = extractor._strip_code_fences(raw_text)
            records = json.loads(clean)
            if isinstance(records, list):
                candidates.extend(records)
        except Exception:
            pass

    return candidates


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

    # Phase 1: Autonomous Dynamic Multi-Sector AI Venture Scouting
    yield {"type": "log", "message": "Phase 1: Starting exhaustive autonomous venture discovery across TVB Orbits & Non-US Hubs..."}

    sectors_pool = list(config.SECTORS)
    regions_pool = list(config.REGIONS)
    random.shuffle(sectors_pool)
    random.shuffle(regions_pool)

    batch_idx = 0
    max_ai_batches = min(12, len(sectors_pool))
    while scanned < max_domains and batch_idx < max_ai_batches:
        batch_idx += 1
        s_focus = sectors_pool[(batch_idx - 1) % len(sectors_pool)]
        r_focus = regions_pool[(batch_idx - 1) % len(regions_pool)]

        yield {
            "type": "log",
            "message": f"[AI Scout Batch {batch_idx}/{max_ai_batches}] Scanning {s_focus} scale-ups in {r_focus}...",
        }
        batch_candidates = _scout_ai_batch(target_count=6, sector_hint=s_focus, region_hint=r_focus)

        if not batch_candidates:
            yield {"type": "log", "message": "  -> No candidates returned in this batch, rotating..."}
            continue

        for cand in batch_candidates:
            if scanned >= max_domains:
                break

            c_name = cand.get("company_name", "Candidate")
            source_url = cand.get("source_url") or ""
            domain = scraper.domain_of(source_url)
            if domain and domain in seen_domains:
                continue
            if domain:
                seen_domains.add(domain)

            scanned += 1
            yield {"type": "progress", "scanned": scanned, "total": max_domains}
            yield {"type": "log", "message": f"  -> Evaluating candidate: {c_name} ({cand.get('hq_country', 'Global')})"}

            qualifying = validator.evaluate_record(cand)
            if qualifying:
                leads.append(qualifying)
                yield {"type": "lead", "record": qualifying}
                yield {
                    "type": "log",
                    "message": f"     ✓ Verified lead #{len(leads)}: {qualifying['company_name']} "
                    f"({qualifying['funding_or_revenue_usd_estimate']}, {qualifying['contact_name']} <{qualifying['verified_email']}>)",
                }
            else:
                yield {"type": "log", "message": f"     ✗ {c_name} did not pass strict parameter/MX validation"}

    # Phase 2: Live Multi-Query Web Search & Deep Crawling
    if scanned < max_domains:
        yield {"type": "log", "message": "Phase 2: Generating live search queries across remaining TVB Orbits..."}
        queries = query_generator.generate_queries(max_queries)
        yield {
            "type": "log",
            "message": f"Generated {len(queries)} multi-vector queries across {len(config.SECTORS)} sectors.",
        }

        for qi, q in enumerate(queries, start=1):
            if scanned >= max_domains:
                break

            yield {"type": "log", "message": f"[{qi}/{len(queries)}] Live Web Search: {q}"}
            results = search.search(q)

            for r in results:
                if scanned >= max_domains:
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
                    yield {"type": "log", "message": "     (skipped, thin/empty content)"}
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
                        "message": f"     ✓ Verified lead #{len(leads)}: {qualifying['company_name']} "
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
        "message": f"Exhaustive discovery complete: Found {len(leads)} fully qualifying leads across {scanned} scanned entities.",
    }
    yield {"type": "done", "leads": leads}
