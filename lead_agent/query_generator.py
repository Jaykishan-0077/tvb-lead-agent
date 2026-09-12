"""
Builds the set of search queries the agent will use to *discover* candidate
companies on its own, rather than relying on one fixed list.

Two layers:
1. Deterministic combinatorial generation (sector x region x funding-signal)
   -- always works, no API key required.
2. Optional LLM-brainstormed queries (if an Anthropic key is available) that
   add angles a template can't easily produce (e.g. "companies that just
   quietly closed pilots with hospitals in the UK", niche directory ideas,
   award/list pages, accelerator cohort pages, etc.)
"""

import random
from typing import List

from . import config

try:
    import anthropic
except ImportError:  # library not installed in some minimal envs
    anthropic = None


def _combinatorial_queries(n: int) -> List[str]:
    queries = []
    for sector in config.SECTORS:
        for region in config.REGIONS:
            phrase = random.choice(config.FUNDING_SIGNAL_PHRASES)
            queries.append(f'"{sector}" startup {region} {phrase}')
            queries.append(f"{sector} platform company {region} funding announcement")
    random.shuffle(queries)
    return queries[:n]


def _directory_style_queries(n: int) -> List[str]:
    """Queries aimed at list/roundup pages, which tend to surface many
    companies at once and are a good way to 'discover new sources'."""
    queries = []
    for sector in config.SECTORS:
        region = random.choice(config.REGIONS)
        queries.append(f"top {sector} startups {region} 2025 2026 list")
        queries.append(f"{sector} scale-ups to watch {region}")
    random.shuffle(queries)
    return queries[:n]


def _llm_brainstormed_queries(n: int) -> List[str]:
    api_key = config.get_anthropic_api_key()
    if not api_key or anthropic is None:
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "You are helping a venture-scouting agent discover companies on the "
            "open web. Generate {n} short, diverse Google-style search queries "
            "(one per line, no numbering, no quotes) that would surface small "
            "tech companies (roughly $1M-$5M revenue or funding raised) that "
            "are NOT primarily US-based, across sectors like healthcare tech, "
            "edtech, applied AI, cybersecurity, digital twin, fintech, and "
            "travel tech. Favor queries likely to return company websites, "
            "press releases, or 'meet our team' pages that mention a founder "
            "or CEO by name. Avoid queries about huge/famous companies."
        ).format(n=n)
        resp = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        lines = [ln.strip("-* \t") for ln in text.splitlines() if ln.strip()]
        return lines[:n]
    except Exception:
        # Discovery should degrade gracefully, never crash the run.
        return []


def generate_queries(max_queries: int = None) -> List[str]:
    max_queries = max_queries or config.MAX_SEARCH_QUERIES
    llm_share = max(6, max_queries // 4)
    combi_share = max_queries - llm_share

    queries = []
    queries.extend(_combinatorial_queries(int(combi_share * 0.6)))
    queries.extend(_directory_style_queries(int(combi_share * 0.4)))
    queries.extend(_llm_brainstormed_queries(llm_share))

    # De-dupe while preserving order
    seen = set()
    unique = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:max_queries]
