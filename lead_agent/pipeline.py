"""
Grounded Two-Pass Autonomous Discovery & 6-Gate Deterministic Verification Pipeline.

Architecture:
  Pass 1: Live Multi-Vector Google SERP Discovery & Crawling (Real search queries across non-US regions).
  Pass 2: Deep 6-Gate Deterministic Verification (G1 to G6) strictly grounded on fetched web page text.
  Pass 3: Live Adversarial Web Search Audit (Live Google search for Series B/C rounds, acquisitions, and US flips).

Outputs:
  - qualified_leads: Fully verified leads passing all 6 gates + adversarial web audit.
  - rejected_leads: Audit log of all evaluated candidates with explicit rejection reasons and real citations.
"""

import datetime
import random
from typing import Dict, Generator, List

from . import adversarial, config, extractor, query_generator, scraper, search, validator


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

    yield {"type": "log", "message": "🚀 Initiating Grounded Web Search & 6-Gate Verification Engine (Zero Hallucination Protocol)..."}
    yield {"type": "funnel", "funnel": funnel}

    # Generate targeted search queries with negative vectors
    queries = query_generator.generate_queries(max_queries)
    random.shuffle(queries)

    for qi, q in enumerate(queries, start=1):
        if scanned >= max_domains or len(qualified_leads) >= min_leads:
            break

        yield {"type": "log", "message": f"[{qi}/{len(queries)}] Google SERP Search: {q}"}
        results = search.search(q, num=config.RESULTS_PER_QUERY)

        if not results:
            continue

        for r in results:
            if scanned >= max_domains or len(qualified_leads) >= min_leads:
                break

            url = r.get("url") or ""
            if not url or "linkedin.com" in url or "crunchbase.com" in url or "techcrunch.com" in url:
                continue

            domain = scraper.domain_of(url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            scanned += 1
            funnel["discovered"] += 1
            yield {"type": "progress", "scanned": scanned, "total": max_domains}
            yield {"type": "log", "message": f"  -> Fetching & Crawling: {domain} ({url})"}

            # Fetch live homepage and internal links
            page_text = scraper.gather_site_text(url)
            if not page_text or len(page_text.strip()) < 150:
                rej_lead = {
                    "company_name": domain,
                    "hq_source": url,
                    "active_source": url,
                    "rejection_reason": "COMPANY_INACTIVE",
                    "qualification_status": "REJECTED",
                    "checked_at": datetime.date.today().isoformat(),
                }
                rejected_leads.append(rej_lead)
                yield {"type": "log", "message": f"     ❌ Rejected {domain}: Inaccessible or empty site"}
                continue

            # Grounded extraction strictly from scraped page text
            extracted_record = extractor.extract_record(page_text, source_url=url)
            if not extracted_record:
                rej_lead = {
                    "company_name": domain,
                    "hq_source": url,
                    "active_source": url,
                    "rejection_reason": "INSUFFICIENT_EVIDENCE",
                    "qualification_status": "REJECTED",
                    "checked_at": datetime.date.today().isoformat(),
                }
                rejected_leads.append(rej_lead)
                yield {"type": "log", "message": f"     ❌ Rejected {domain}: Could not extract structured company facts"}
                continue

            c_name = extracted_record.get("company_name") or domain
            yield {"type": "log", "message": f"  -> 6-Gate Audit: {c_name} (HQ: {extracted_record.get('hq_country', 'Unknown')})"}

            # Evaluate 6 Hard Gates with live scraped page text
            qual, rej = validator.evaluate_record(extracted_record, page_text=page_text)
            if qual:
                funnel["fin_pass"] += 1
                funnel["tech_pass"] += 1
                funnel["us_pass"] += 1
                funnel["ceo_pass"] += 1
                funnel["email_pass"] += 1

                # Pass 3: Active Adversarial Web Search Break-Testing
                yield {"type": "log", "message": f"  🛡️ Running Active Adversarial Web Search on {c_name}..."}
                adv_pass, adv_reason, adv_exp = adversarial.verify_adversarial(qual)

                if adv_pass:
                    funnel["adversarial_pass"] += 1
                    funnel["qualified"] += 1
                    qual["adversarial_result"] = f"PASSED: {adv_exp}"
                    qualified_leads.append(qual)
                    yield {"type": "lead", "record": qual}
                    yield {"type": "funnel", "funnel": funnel}
                    yield {
                        "type": "log",
                        "message": f"     ✅ QUALIFIED #{len(qualified_leads)}: {qual['company_name']} "
                        f"({qual['financial_amount_usd']} | {qual['contact_name']} <{qual['email']}>)",
                    }
                else:
                    qual["qualification_status"] = "REJECTED"
                    qual["rejection_reason"] = adv_reason
                    qual["adversarial_result"] = f"FAILED: {adv_exp}"
                    rejected_leads.append(qual)
                    yield {
                        "type": "log",
                        "message": f"     🛡️ Adversarial Search rejected {c_name}: {adv_reason} ({adv_exp})",
                    }
            else:
                if rej:
                    rejected_leads.append(rej)
                    yield {
                        "type": "log",
                        "message": f"     ❌ Rejected {c_name}: {rej.get('rejection_reason')}",
                    }

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
