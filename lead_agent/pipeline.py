"""
Grounded Two-Pass Autonomous Discovery & 6-Gate Deterministic Verification Pipeline.

Architecture:
  Pass 1: Live Multi-Vector Tavily SERP Discovery & Crawling (Real search queries across non-US regions).
  Pass 2: Deep 6-Gate Deterministic Verification (G1 to G6) strictly grounded on fetched web page text.
  Pass 3: Live Adversarial Web Search Audit (Live search for Series B/C rounds, acquisitions, US flips).

Outputs:
  - qualified_leads: Fully verified leads passing all 6 gates + adversarial web audit.
  - rejected_leads: Audit log of all evaluated candidates with explicit rejection reasons.
"""

import datetime
import random
from typing import Dict, Generator, List
from urllib.parse import urlparse

from . import adversarial, config, extractor, query_generator, scraper, search, validator

# ---------------------------------------------------------------------------
# Domains that are aggregator/list/investor/news sites — never a startup HQ.
# The pipeline must skip these: scraping them returns article text, not company facts.
# ---------------------------------------------------------------------------
AGGREGATOR_DOMAINS = {
    # List/directory sites
    "vestbee.com", "growthlist.co", "wellfound.com", "f6s.com", "eu-startups.com",
    "thestartuptrends.com", "startupblink.com", "startupsmagazine.co.uk",
    "startupstories.in", "startuptalky.com", "vccircle.com", "yourstory.com",
    "inc42.com", "businessinsider.com", "businessinsider.in", "forbes.com",
    "fortune.com", "techcrunch.com", "venturebeat.com", "the-next-web.com",
    "thenextweb.com", "wired.com", "techradar.com", "zdnet.com",
    "startus-insights.com", "ellty.com", "softwaresuggest.com", "techcollectivesea.com",
    "startupfundraising.com", "shizune.co", "saastartups.org", "bonfirevc.com",
    "revli.com", "fundedstartupsdaily.com", "projectstartups.com", "frenchtechjournal.com",
    "vcsheet.com", "developmentcorporate.com", "dealmakerssouthafrica.com",
    "siliconcanals.com", "tech.eu", "failory.com", "launchbaseafrica.com",
    "dxbstart.com", "uaepreferred.com", "zepnew.com", "weetracker.com",
    "vcbacked.co", "newmarketpitch.com", "euacc.ai", "marketingreport.one",
    # VC/investor platforms
    "crunchbase.com", "pitchbook.com", "dealroom.co", "angellist.com",
    "seedtable.com", "signal.nfx.com", "tracxn.com", "cb-insights.com",
    "cbinsights.com", "strictlyvc.com",
    # Social / general
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "medium.com", "substack.com", "reddit.com",
    # Press release wires
    "prnewswire.com", "businesswire.com", "globenewswire.com", "accesswire.com",
    "einpresswire.com", "newswire.com",
    # Generic job boards / aggregators
    "glassdoor.com", "indeed.com", "builtin.com",
}


def _is_aggregator(url: str) -> bool:
    """Returns True if the URL belongs to a known aggregator/list/news domain."""
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        # Check exact match or suffix match (e.g. "news.techcrunch.com")
        for agg in AGGREGATOR_DOMAINS:
            if netloc == agg or netloc.endswith("." + agg):
                return True
    except Exception:
        pass
import re
import requests


def resolve_company_official_website(company_name: str, country: str = "") -> str:
    """Discovers the real corporate website for a startup identified via news or press releases."""
    api_key = config.get_tavily_api_key()
    if not api_key or not company_name:
        return ""
    q = f'"{company_name}" {country} startup official website homepage'
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": api_key, "query": q, "max_results": 6, "include_answer": True},
            timeout=config.REQUEST_TIMEOUT_SECS,
        )
        if resp.status_code == 200:
            data = resp.json()
            # 1. Check Tavily Direct Answer
            ans = data.get("answer", "")
            if ans:
                for match in re.finditer(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/[^\s,]*)?", ans):
                    dom = match.group(1).lower().replace("www.", "")
                    if not any(ex in dom for ex in AGGREGATOR_DOMAINS):
                        return f"https://{dom}"

            # 2. Check Results for company name match
            c_clean = "".join(ch for ch in company_name.lower() if ch.isalnum())
            for item in data.get("results", []):
                u = item.get("url", "")
                dom = u.split("//")[-1].split("/")[0].lower().replace("www.", "")
                if any(ex in dom for ex in AGGREGATOR_DOMAINS):
                    continue
                if c_clean in dom.replace("-", "") or dom.split(".")[0] in c_clean:
                    return f"https://{dom}"

            # 3. Fallback: First clean domain in search results
            for item in data.get("results", []):
                u = item.get("url", "")
                dom = u.split("//")[-1].split("/")[0].lower().replace("www.", "")
                if not any(ex in dom for ex in AGGREGATOR_DOMAINS):
                    return f"https://{dom}"
    except Exception:
        pass
    return ""


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

        yield {"type": "log", "message": f"[{qi}/{len(queries)}] Tavily Search: {q}"}
        results = search.search(q, num=config.RESULTS_PER_QUERY)

        if not results:
            yield {"type": "log", "message": f"  ⚠️ No results returned for query #{qi}"}
            continue

        for r in results:
            if scanned >= max_domains or len(qualified_leads) >= min_leads:
                break

            url = r.get("url") or ""
            if not url:
                continue

            # Skip aggregator, investor, and news domains immediately
            if _is_aggregator(url):
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
                yield {"type": "log", "message": f"     ❌ Rejected {domain}: Inaccessible or empty site (status: no page text)"}
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
                yield {"type": "log", "message": f"     ❌ Rejected {domain}: LLM could not extract structured company facts"}
                continue

            c_name = extracted_record.get("company_name") or domain
            hq = extracted_record.get("hq_country") or "Unknown"

            # Check if this URL was a press release / news article rather than the company official website
            c_clean = "".join(ch for ch in c_name.lower() if ch.isalnum())
            cur_dom = domain.lower().replace("www.", "")
            if c_clean and c_clean not in cur_dom and cur_dom.split(".")[0] not in c_clean:
                yield {"type": "log", "message": f"  🔎 Press/News coverage detected for '{c_name}'. Resolving official website..."}
                official_url = resolve_company_official_website(c_name, hq)
                if official_url:
                    off_dom = scraper.domain_of(official_url)
                    yield {"type": "log", "message": f"     🌐 Discovered Official Website: {official_url} ({off_dom})"}
                    extracted_record["financial_source_1"] = url  # preserve news article as financial citation
                    extracted_record["source_url"] = official_url
                    extracted_record["active_source"] = official_url
                    domain = off_dom
                    official_text = scraper.gather_site_text(official_url)
                    if official_text:
                        page_text = official_text + " " + page_text

            yield {"type": "log", "message": f"  -> 6-Gate Audit: {c_name} (HQ: {hq})"}

            # Evaluate 6 Hard Gates with live scraped page text
            qual, rej = validator.evaluate_record(extracted_record, page_text=page_text)
            if qual:
                funnel["fin_pass"] += 1
                funnel["tech_pass"] += 1
                funnel["us_pass"] += 1
                funnel["ceo_pass"] += 1
                funnel["email_pass"] += 1

                # Pass 3: Adversarial Web Search Break-Testing
                yield {"type": "log", "message": f"  🛡️ Running Adversarial Web Audit on {c_name}..."}
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
                        "message": (
                            f"     ✅ QUALIFIED #{len(qualified_leads)}: {qual['company_name']} "
                            f"({qual['financial_amount_usd']} | {qual['contact_name']} <{qual['email']}>)"
                        ),
                    }
                else:
                    qual["qualification_status"] = "REJECTED"
                    qual["rejection_reason"] = adv_reason
                    qual["adversarial_result"] = f"FAILED: {adv_exp}"
                    rejected_leads.append(qual)
                    yield {
                        "type": "log",
                        "message": f"     🛡️ Adversarial rejected {c_name}: {adv_reason} — {adv_exp}",
                    }
            else:
                if rej:
                    reason = rej.get("rejection_reason", "UNKNOWN")
                    rejected_leads.append(rej)
                    yield {
                        "type": "log",
                        "message": f"     ❌ Rejected {c_name}: {reason}",
                    }
                yield {"type": "funnel", "funnel": funnel}

    yield {
        "type": "log",
        "message": f"🎉 Discovery Complete: {len(qualified_leads)} QUALIFIED leads | {len(rejected_leads)} REJECTED logged.",
    }
    yield {
        "type": "done",
        "leads": qualified_leads,
        "rejected_leads": rejected_leads,
        "funnel": funnel,
    }
