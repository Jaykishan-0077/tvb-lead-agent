"""
Two-Pass Autonomous Discovery & 6-Gate Deterministic Verification Pipeline.

Architecture:
  Pass 1: Multi-Vector Discovery targeting verified $1M-$5M total funding & revenue non-US tech platforms.
  Pass 2: Deep 6-Gate Deterministic Verification (G1 to G6) with strict email person attribution and actual date tracking.
  Pass 3: Adversarial Red-Team Verification Break Test.

Outputs:
  - qualified_leads: Fully verified leads passing all 6 gates + adversarial audit.
  - rejected_leads: Audit log of all evaluated candidates with explicit rejection reasons and evidence.
"""

import datetime
import json
import random
from typing import Dict, Generator, List

from . import adversarial, config, extractor, query_generator, scraper, search, validator


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
        f"Discover {target_count} REAL, active non-US tech platform companies matching ALL mandatory TVB criteria:\n"
        f"1. Total Funding / Revenue: Current TOTAL funding raised or verified ARR must be STRICTLY between $1 Million and $5 Million USD.\n"
        f"   - DO NOT include companies that raised subsequent Series B/C rounds exceeding $5M total (e.g., exclude Omni, Koywe, Dust, Payflow, Retorio, Flowpay).\n"
        f"   - DO NOT include companies that raised under $1M total (e.g., exclude Sanctifly, Fyorin).\n"
        f"   - Include the ACTUAL date/year of the funding round (e.g. '2024-03-15' or '2023-11-07'), NOT runtime dates.\n"
        f"2. Sector: Focus on {', '.join(sectors)}.\n"
        f"3. Geography: Headquartered in non-US countries like {', '.join(regions)} (India, UK, Europe, Singapore, UAE, Kenya, Latin America, Australia) with MINIMAL-TO-NO US presence (exclude companies with US headquarters or San Francisco offices like Kombai or Omni).\n"
        f"4. Active & Independent: Company must be active and independent (exclude acquired companies like Langfuse).\n"
        f"5. Leadership: The exact PRIMARY Founder, Co-Founder, or CEO full name (e.g., Felix Macharia for Kotani Pay, Prateek Bhargava for Mindler) and their verified corporate email address.\n\n"
        f"STRICT GROUNDING: Return factual data only. If total funding >$5M, omit the company.\n\n"
        f"Return STRICT JSON array of objects with keys:\n"
        f"[\n"
        f"  {{\n"
        f"    \"company_name\": \"...\",\n"
        f"    \"description\": \"...\",\n"
        f"    \"industry_sector\": \"...\",\n"
        f"    \"hq_country\": \"...\",\n"
        f"    \"has_significant_us_presence\": \"no\",\n"
        f"    \"is_tech_platform\": \"yes\",\n"
        f"    \"financial_type\": \"total_funding\" | \"seed_round\" | \"annual_revenue\",\n"
        f"    \"current_total_funding_usd\": \"...\",\n"
        f"    \"current_revenue_usd\": \"...\",\n"
        f"    \"financial_date\": \"YYYY-MM-DD\",\n"
        f"    \"funding_or_revenue_evidence\": \"...\",\n"
        f"    \"funding_or_revenue_usd_estimate\": \"...\",\n"
        f"    \"financial_source_2\": \"TechCrunch / Dealroom / Tracxn\",\n"
        f"    \"contact_name\": \"...\",\n"
        f"    \"contact_title\": \"Founder & CEO\" | \"Co-Founder & CEO\",\n"
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
    qualified_leads = []
    rejected_leads = []
    scanned = 0

    funnel = {
        "discovered": 0,
        "fin_pass": 0,
        "tech_pass": 0,
        "us_pass": 0,
        "ceo_pass": 0,
        "email_pass": 0,
        "adversarial_pass": 0,
        "qualified": 0,
    }

    yield {"type": "log", "message": "🚀 Initiating Two-Pass 6-Gate Discovery & Verification Engine (Strict TVB Protocol)..."}
    yield {"type": "funnel", "funnel": funnel}

    # ----------------------------------------------------
    # Pass 1 & 2: Dynamic Scouting & 6-Gate Verification
    # ----------------------------------------------------
    sectors_pool = list(config.SECTORS)
    regions_pool = list(config.REGIONS)
    random.shuffle(sectors_pool)
    random.shuffle(regions_pool)

    batch_idx = 0
    max_ai_batches = min(20, len(sectors_pool) * 2)
    while scanned < max_domains and batch_idx < max_ai_batches and len(qualified_leads) < min_leads:
        batch_idx += 1
        s_focus = sectors_pool[(batch_idx - 1) % len(sectors_pool)]
        r_focus = regions_pool[(batch_idx - 1) % len(regions_pool)]

        yield {
            "type": "log",
            "message": f"[Pass 1 Scout Batch {batch_idx}] Scouting {s_focus} in {r_focus}...",
        }
        batch_candidates = _scout_ai_batch(target_count=6, sector_hint=s_focus, region_hint=r_focus)

        if not batch_candidates:
            yield {"type": "log", "message": "  -> No candidates in batch, rotating sector..."}
            continue

        for cand in batch_candidates:
            if scanned >= max_domains or len(qualified_leads) >= 25:
                break

            c_name = cand.get("company_name", "Candidate")
            source_url = cand.get("source_url") or ""
            domain = scraper.domain_of(source_url)
            if domain and domain in seen_domains:
                continue
            if domain:
                seen_domains.add(domain)

            scanned += 1
            funnel["discovered"] += 1
            yield {"type": "progress", "scanned": scanned, "total": max_domains}
            yield {"type": "log", "message": f"  -> 6-Gate Audit: {c_name} ({cand.get('hq_country', 'Global')})"}

            # Evaluate 6 Hard Gates
            qual, rej = validator.evaluate_record(cand)
            if qual:
                funnel["fin_pass"] += 1
                funnel["tech_pass"] += 1
                funnel["us_pass"] += 1
                funnel["ceo_pass"] += 1
                funnel["email_pass"] += 1

                # Pass 3: Adversarial Break-Testing
                adv_pass, adv_reason = adversarial.verify_adversarial(qual)
                if adv_pass:
                    funnel["adversarial_pass"] += 1
                    funnel["qualified"] += 1
                    qualified_leads.append(qual)
                    yield {"type": "lead", "record": qual}
                    yield {"type": "funnel", "funnel": funnel}
                    yield {
                        "type": "log",
                        "message": f"     ✅ QUALIFIED #{len(qualified_leads)}: {qual['company_name']} "
                        f"({qual['financial_amount_usd']} total | {qual['contact_name']} <{qual['email']}>)",
                    }
                else:
                    qual["qualification_status"] = "REJECTED"
                    qual["rejection_reason"] = adv_reason
                    rejected_leads.append(qual)
                    yield {
                        "type": "log",
                        "message": f"     🛡️ Adversarial Verifier rejected {c_name}: {adv_reason}",
                    }
            else:
                if rej:
                    rejected_leads.append(rej)
                    yield {
                        "type": "log",
                        "message": f"     ❌ Rejected {c_name}: {rej.get('rejection_reason')}",
                    }

    # Pass 2 Continued: Live SERP Multi-Query Discovery if needed
    if scanned < max_domains and len(qualified_leads) < min_leads:
        yield {"type": "log", "message": "Pass 2: Executing Live SERP Multi-Vector Deep Discovery..."}
        queries = query_generator.generate_queries(max_queries)

        for qi, q in enumerate(queries, start=1):
            if scanned >= max_domains or len(qualified_leads) >= min_leads:
                break

            yield {"type": "log", "message": f"[{qi}/{len(queries)}] SERP Search: {q}"}
            results = search.search(q)

            for r in results:
                if scanned >= max_domains or len(qualified_leads) >= min_leads:
                    break
                url = r.get("url") or ""
                if not url:
                    continue
                domain = scraper.domain_of(url)
                if not domain or domain in seen_domains:
                    continue
                seen_domains.add(domain)
                scanned += 1
                funnel["discovered"] += 1

                yield {"type": "progress", "scanned": scanned, "total": max_domains}
                yield {"type": "log", "message": f"  -> Scraping & Evaluating: {domain}"}

                page_text = scraper.gather_site_text(url)
                if not page_text or len(page_text) < 150:
                    continue

                record = extractor.extract_record(page_text, source_url=url)
                if not record:
                    continue

                qual, rej = validator.evaluate_record(record)
                if qual:
                    funnel["fin_pass"] += 1
                    funnel["tech_pass"] += 1
                    funnel["us_pass"] += 1
                    funnel["ceo_pass"] += 1
                    funnel["email_pass"] += 1

                    adv_pass, adv_reason = adversarial.verify_adversarial(qual)
                    if adv_pass:
                        funnel["adversarial_pass"] += 1
                        funnel["qualified"] += 1
                        qualified_leads.append(qual)
                        yield {"type": "lead", "record": qual}
                        yield {"type": "funnel", "funnel": funnel}
                        yield {
                            "type": "log",
                            "message": f"     ✅ QUALIFIED #{len(qualified_leads)}: {qual['company_name']} ({qual['email']})",
                        }
                    else:
                        qual["qualification_status"] = "REJECTED"
                        qual["rejection_reason"] = adv_reason
                        rejected_leads.append(qual)
                else:
                    if rej:
                        rejected_leads.append(rej)

    yield {
        "type": "log",
        "message": f"🎉 Discovery Run Completed: {len(qualified_leads)} fully QUALIFIED leads | {len(rejected_leads)} REJECTED candidates logged.",
    }
    yield {
        "type": "done",
        "leads": qualified_leads,
        "rejected_leads": rejected_leads,
        "funnel": funnel,
    }
