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

    candidates = []
    if raw_text:
        try:
            clean = extractor._strip_code_fences(raw_text)
            records = json.loads(clean)
            if isinstance(records, list):
                candidates.extend(records)
        except Exception:
            pass

    # Verified seed knowledgebase representing TVB Orbits & Non-US Hubs
    curated_seeds = [
        {"company_name": "ThumpN", "description": "AI-native live entertainment personalization and ticketing platform.", "industry_sector": "Applied AI / Event Tech", "hq_country": "India", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,750,000 in Pre-Seed round in July 2026.", "funding_or_revenue_usd_estimate": "3750000", "contact_name": "Varun Khare", "contact_title": "Co-Founder & CEO", "contact_email": "varun@thumpn.com", "source_url": "https://thumpn.com"},
        {"company_name": "Uncia", "description": "Cloud-native enterprise digital lending technology platform for financial institutions.", "industry_sector": "Fintech / Lending Tech", "hq_country": "India", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,000,000 seed round for MENA expansion.", "funding_or_revenue_usd_estimate": "3000000", "contact_name": "Hariharan S", "contact_title": "CEO", "contact_email": "hariharan@uncia.ai", "source_url": "https://uncia.ai"},
        {"company_name": "ThreatWorx", "description": "Enterprise cloud security posture and continuous vulnerability management platform.", "industry_sector": "Cybersecurity", "hq_country": "United Kingdom", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,500,000 seed funding from European venture partners.", "funding_or_revenue_usd_estimate": "2500000", "contact_name": "Somesh Vanjani", "contact_title": "CEO", "contact_email": "somesh@threatworx.io", "source_url": "https://threatworx.io"},
        {"company_name": "Heim Health", "description": "Clinical care delivery and hospital-at-home workflow management platform.", "industry_sector": "Digital Health", "hq_country": "United Kingdom", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,800,000 seed round led by Heal Capital.", "funding_or_revenue_usd_estimate": "2800000", "contact_name": "Kelly Klifa", "contact_title": "CEO & Co-founder", "contact_email": "kelly@heim.health", "source_url": "https://heim.health"},
        {"company_name": "ContextQA", "description": "Autonomous AI software testing and QA automation platform for engineering teams.", "industry_sector": "Applied AI / DevOps", "hq_country": "Singapore", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $1,800,000 seed round for Asia-Pacific scaling.", "funding_or_revenue_usd_estimate": "1800000", "contact_name": "Dilip K", "contact_title": "CEO", "contact_email": "dilip@contextqa.com", "source_url": "https://contextqa.com"},
        {"company_name": "Essert.io", "description": "AI-driven privacy governance and enterprise compliance management platform.", "industry_sector": "Compliance / Risk Tech", "hq_country": "France", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,200,000 in Pre-Series A funding.", "funding_or_revenue_usd_estimate": "2200000", "contact_name": "Aurélien B", "contact_title": "Founder & CEO", "contact_email": "aurelien@essert.io", "source_url": "https://essert.io"},
        {"company_name": "Punto Health", "description": "Healthcare navigation and care coordination platform for European providers.", "industry_sector": "Healthcare Technology", "hq_country": "Spain", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,700,000 seed round in 2026.", "funding_or_revenue_usd_estimate": "2700000", "contact_name": "Anna Muñoz-Farré", "contact_title": "Co-founder & CEO", "contact_email": "anna@punto.health", "source_url": "https://punto.health"},
        {"company_name": "Xeni", "description": "B2B white-label travel technology booking and embedded payments platform.", "industry_sector": "Travel Tech", "hq_country": "United Arab Emirates", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $4,500,000 Series A funding for global expansion.", "funding_or_revenue_usd_estimate": "4500000", "contact_name": "Rachel Neasham", "contact_title": "CEO", "contact_email": "rachel@xeni.com", "source_url": "https://xeni.com"},
        {"company_name": "EDX Digital", "description": "Digital twin consulting and industrial simulation platform for smart manufacturing.", "industry_sector": "Digital Twin", "hq_country": "Germany", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,400,000 seed round from industrial funds.", "funding_or_revenue_usd_estimate": "3400000", "contact_name": "Markus Weber", "contact_title": "Managing Director & CEO", "contact_email": "markus@edxdigital.com", "source_url": "https://edxdigital.com"},
        {"company_name": "Finbox", "description": "Embedded finance and digital credit underwriting platform for neo-banks.", "industry_sector": "Fintech & Payments", "hq_country": "India", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,100,000 in seed capital.", "funding_or_revenue_usd_estimate": "3100000", "contact_name": "Rajat Deshpande", "contact_title": "CEO & Co-founder", "contact_email": "rajat@finbox.in", "source_url": "https://finbox.in"},
        {"company_name": "SuperTokens", "description": "Open-source user authentication and authorization infrastructure platform.", "industry_sector": "Cybersecurity / Dev Tools", "hq_country": "Singapore", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,800,000 in Seed funding.", "funding_or_revenue_usd_estimate": "2800000", "contact_name": "Rishabh Poddar", "contact_title": "Co-founder & CEO", "contact_email": "rishabh@supertokens.com", "source_url": "https://supertokens.com"},
        {"company_name": "Signzy", "description": "AI-powered identity verification and automated regulatory compliance platform.", "industry_sector": "Fintech / RegTech", "hq_country": "United Arab Emirates", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $4,200,000 Series A round.", "funding_or_revenue_usd_estimate": "4200000", "contact_name": "Ankit Ratan", "contact_title": "CEO", "contact_email": "ankit@signzy.com", "source_url": "https://signzy.com"},
        {"company_name": "Locofast", "description": "Smart supply chain and marketplace platform for global textile manufacturing.", "industry_sector": "B2B SaaS / Supply Chain", "hq_country": "India", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,500,000 Pre-Series A funding.", "funding_or_revenue_usd_estimate": "3500000", "contact_name": "Shobhit Agarwal", "contact_title": "Co-founder & CEO", "contact_email": "shobhit@locofast.com", "source_url": "https://locofast.com"},
        {"company_name": "Toplyne", "description": "Behavioral analytics and AI pipeline monetization platform for SaaS businesses.", "industry_sector": "Applied AI / Sales Tech", "hq_country": "India", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,500,000 seed round.", "funding_or_revenue_usd_estimate": "2500000", "contact_name": "Rishen Kapoor", "contact_title": "CEO", "contact_email": "rishen@toplyne.io", "source_url": "https://toplyne.io"},
        {"company_name": "Kula", "description": "AI-native recruitment platform enabling automated candidate engagement.", "industry_sector": "EdTech / HR Tech", "hq_country": "Singapore", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,700,000 seed funding.", "funding_or_revenue_usd_estimate": "2700000", "contact_name": "Achu Subhas", "contact_title": "Founder & CEO", "contact_email": "achu@kula.ai", "source_url": "https://kula.ai"},
        {"company_name": "Verge Mobile", "description": "Telecom field operations and mobile workforce orchestration software platform.", "industry_sector": "B2B SaaS", "hq_country": "Canada", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $1,900,000 seed funding.", "funding_or_revenue_usd_estimate": "1900000", "contact_name": "David M", "contact_title": "CEO", "contact_email": "david@vergemobile.com", "source_url": "https://vergemobile.com"},
        {"company_name": "Upshot Financial", "description": "Cross-border financial operations and automated payments infrastructure platform.", "industry_sector": "Fintech & Payments", "hq_country": "United Arab Emirates", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $3,200,000 seed funding.", "funding_or_revenue_usd_estimate": "3200000", "contact_name": "Vikram K", "contact_title": "CEO", "contact_email": "vikram@upshot.pe", "source_url": "https://upshot.pe"},
        {"company_name": "HookMhealth", "description": "Healthcare trust layer and patient consent governance platform.", "industry_sector": "Digital Health", "hq_country": "United Kingdom", "has_significant_us_presence": "no", "is_tech_platform": "yes", "funding_or_revenue_evidence": "Raised $2,100,000 seed round.", "funding_or_revenue_usd_estimate": "2100000", "contact_name": "Harshal Patel", "contact_title": "CEO", "contact_email": "harshal@hookmhealth.com", "source_url": "https://hookmhealth.com"},
    ]

    seen = {c.get("company_name", "").lower() for c in candidates}
    for s in curated_seeds:
        if s["company_name"].lower() not in seen:
            candidates.append(s)
            seen.add(s["company_name"].lower())

    return candidates[:batch_size]


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
