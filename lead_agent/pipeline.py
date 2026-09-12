"""
Orchestrates a full agent run:

  generate queries -> search -> dedupe domains -> scrape -> extract -> validate

Implemented as a generator that yields log/progress events, so a UI (e.g.
Streamlit) can stream status updates instead of blocking silently for the
full run.

Event shapes yielded:
  {"type": "log", "message": str}
  {"type": "lead", "record": dict}          # a qualifying lead was found
  {"type": "progress", "scanned": int, "total": int}
  {"type": "done", "leads": list[dict]}
"""

from typing import Dict, Generator

from . import config, extractor, query_generator, scraper, search, validator


def run(
    min_leads: int = None,
    max_domains: int = None,
    max_queries: int = None,
) -> Generator[Dict, None, None]:
    min_leads = min_leads or config.MIN_QUALIFYING_LEADS
    max_domains = max_domains or config.MAX_DOMAINS_TO_SCAN
    max_queries = max_queries or config.MAX_SEARCH_QUERIES

    yield {"type": "log", "message": "Generating discovery queries..."}
    queries = query_generator.generate_queries(max_queries)
    yield {
        "type": "log",
        "message": f"Generated {len(queries)} discovery queries across "
        f"{len(config.SECTORS)} sectors and {len(config.REGIONS)} regions.",
    }

    seen_domains = set()
    leads = []
    scanned = 0

    for qi, q in enumerate(queries, start=1):
        if len(leads) >= min_leads or scanned >= max_domains:
            break

        yield {"type": "log", "message": f"[{qi}/{len(queries)}] Searching: {q}"}
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
            yield {"type": "log", "message": f"  -> Visiting {domain}"}

            page_text = scraper.gather_site_text(url)
            if not page_text or len(page_text) < 200:
                yield {"type": "log", "message": f"     (skipped, little/no content)"}
                continue

            record = extractor.extract_record(page_text, source_url=url)
            if not record:
                yield {"type": "log", "message": "     (extraction failed/blank, skipped)"}
                continue

            qualifying = validator.evaluate_record(record)
            if qualifying:
                leads.append(qualifying)
                yield {"type": "lead", "record": qualifying}
                yield {
                    "type": "log",
                    "message": f"     ✓ Qualifying lead: {qualifying['company_name']} "
                    f"({qualifying['verified_email']})",
                }
            else:
                name = record.get("company_name") or domain
                yield {
                    "type": "log",
                    "message": f"     ✗ {name} did not meet all criteria, skipped",
                }

    yield {
        "type": "log",
        "message": f"Run complete: {len(leads)} qualifying leads from "
        f"{scanned} domains scanned.",
    }
    yield {"type": "done", "leads": leads}
