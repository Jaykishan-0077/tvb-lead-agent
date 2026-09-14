"""
Builds the set of search queries the agent will use to *discover* candidate
companies on its own.

Strategy:
  - Combinatorial queries targeting COMPANY OFFICIAL SITES ("about" / "team" / "contact" pages).
  - Negative vectors strip aggregators, directories, news sites.
  - LLM brainstorming adds diverse region × sector coverage.
  - NO directory-style queries ("list of top X") — these land on aggregator sites, not company pages.
"""

import random
from typing import List

from . import config

try:
    import anthropic
except ImportError:
    anthropic = None

# Phase 1 negative search vectors — block aggregator/US-flip noise
NEGATIVE_VECTORS = (
    '-site:crunchbase.com -site:linkedin.com -site:techcrunch.com '
    '-site:eu-startups.com -site:vestbee.com -site:growthlist.co '
    '-site:f6s.com -site:dealroom.co -site:medium.com '
    '-"Inc" -"Delaware" -"USA" -"United States"'
)


def _combinatorial_queries(n: int) -> List[str]:
    """
    Produce queries that land on company home/about/team pages.
    Example: 'fintech startup India "raised" "$2 million" site:.io OR site:.co OR site:.com/about'
    """
    queries = []
    page_targets = [
        'inurl:about',
        'inurl:team',
        'inurl:leadership',
        '"our team" OR "about us" CEO founder',
        '"seed round" OR "pre-series A" founder CEO',
    ]
    for sector in config.SECTORS:
        for region in config.REGIONS:
            phrase = random.choice(config.FUNDING_SIGNAL_PHRASES)
            page_hint = random.choice(page_targets)
            queries.append(
                f'"{sector}" startup {region} {phrase} {page_hint} {NEGATIVE_VECTORS}'
            )
            queries.append(
                f'{sector} company {region} "raised" "$1 million" OR "$2 million" OR "$3 million" '
                f'founder CEO {NEGATIVE_VECTORS}'
            )
    random.shuffle(queries)
    return queries[:n]


def _press_release_queries(n: int) -> List[str]:
    """
    Target official press releases / investor announcement pages on company domains.
    These pages often contain funding amount + CEO name + email.
    """
    queries = []
    for sector in config.SECTORS:
        region = random.choice(config.REGIONS)
        queries.append(
            f'{sector} startup {region} "seed funding" "million" 2024 OR 2025 OR 2026 '
            f'CEO founder {NEGATIVE_VECTORS}'
        )
        queries.append(
            f'{sector} company {region} "pre-series A" OR "seed round" 2025 2026 '
            f'"co-founder" OR "CEO" {NEGATIVE_VECTORS}'
        )
    random.shuffle(queries)
    return queries[:n]


def _llm_brainstormed_queries(n: int) -> List[str]:
    prompt = (
        f"You are helping a venture-scouting agent discover startups on the open web.\n"
        f"Generate {n} short, diverse Google-style search queries (one per line, no numbering, no quotes around the line) "
        f"that would return COMPANY OFFICIAL PAGES (about, team, contact, press) — NOT blog posts, lists, or directories.\n"
        f"Target non-US tech platform startups (UK, France, Germany, India, UAE, Singapore, Africa, LatAm, Australia) "
        f"that have raised between $1M and $5M total funding.\n"
        f"Each query must include at least one funding signal (e.g. 'seed funding $2 million') and a founder/CEO signal.\n"
        f"Include {NEGATIVE_VECTORS} in every query to exclude US entities and aggregator sites.\n"
        f"Examples:\n"
        f"  fintech startup India seed funding $2 million CEO founder -site:crunchbase.com\n"
        f"  AI SaaS company UK pre-series A $3 million co-founder team page\n"
    )

    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()
    text = ""

    try:
        if gemini_key:
            import requests

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
        elif anthropic_key and anthropic is not None:
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text
                for block in resp.content
                if getattr(block, "type", "") == "text"
            )
        elif openai_key:
            import requests

            res = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": config.OPENAI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
                timeout=15,
            )
            if res.status_code == 200:
                text = res.json()["choices"][0]["message"]["content"]
    except Exception:
        pass

    if text:
        lines = [ln.strip("-* \t\"'") for ln in text.splitlines() if ln.strip()]
        return lines[:n]
    return []


def generate_queries(max_queries: int = None) -> List[str]:
    max_queries = max_queries or config.MAX_SEARCH_QUERIES
    llm_share = min(15, max(4, max_queries // 3))

    queries = []
    # Combinatorial + press-release queries (target company pages directly)
    queries.extend(_combinatorial_queries(max_queries))
    queries.extend(_press_release_queries(max_queries // 2))

    # LLM brainstorming for diversity
    llm_queries = _llm_brainstormed_queries(llm_share)
    if llm_queries:
        queries = llm_queries + queries

    # De-dupe while preserving order
    seen = set()
    unique = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:max_queries]
