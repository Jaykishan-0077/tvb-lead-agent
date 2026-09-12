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
    prompt = (
        f"You are helping a venture-scouting agent discover companies on the "
        f"open web. Generate {n} short, diverse Google-style search queries "
        f"(one per line, no numbering, no quotes) that would surface small "
        f"tech companies (roughly $1M-$5M revenue or funding raised) that "
        f"are NOT primarily US-based, across sectors like healthcare tech, "
        f"edtech, applied AI, cybersecurity, digital twin, fintech, and "
        f"travel tech. Favor queries likely to return company websites, "
        f"press releases, or 'meet our team' pages that mention a founder "
        f"or CEO by name. Avoid queries about huge/famous companies."
    )

    gemini_key = config.get_gemini_api_key()
    anthropic_key = config.get_anthropic_api_key()
    openai_key = config.get_openai_api_key()
    text = ""

    try:
        if gemini_key:
            # Try Gemini REST API
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

            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": config.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                text = data["choices"][0]["message"]["content"]
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
    # Always generate a rich batch of combinatorial and directory queries
    queries.extend(_combinatorial_queries(max_queries))
    queries.extend(_directory_style_queries(max_queries // 2))
    
    # Try LLM brainstorming if an API key is available
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
