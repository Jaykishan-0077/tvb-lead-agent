"""
Builds the set of search queries the agent will use to *discover* candidate
companies on its own, rather than relying on one fixed list.

Enhanced with Phase 1 Negative Search Vectors:
  -"Inc" -"Delaware" -"USA" -"United States" -"Crunchbase" -"LinkedIn"
to eliminate aggregator noise, directory deadlocks, and US tax-flip entities.
"""

import random
from typing import List

from . import config

try:
    import anthropic
except ImportError:
    anthropic = None

NEGATIVE_SEARCH_VECTORS = '-"Inc" -"Delaware" -"USA" -"United States" -"Crunchbase" -"LinkedIn"'


def _combinatorial_queries(n: int) -> List[str]:
    queries = []
    for sector in config.SECTORS:
        for region in config.REGIONS:
            phrase = random.choice(config.FUNDING_SIGNAL_PHRASES)
            queries.append(f'"{sector}" startup {region} {phrase} {NEGATIVE_SEARCH_VECTORS}')
            queries.append(f"{sector} platform company {region} funding announcement {NEGATIVE_SEARCH_VECTORS}")
    random.shuffle(queries)
    return queries[:n]


def _directory_style_queries(n: int) -> List[str]:
    """Queries aimed at list/roundup pages, which tend to surface many
    companies at once and are a good way to 'discover new sources'."""
    queries = []
    for sector in config.SECTORS:
        region = random.choice(config.REGIONS)
        queries.append(f"top {sector} startups {region} 2025 2026 list {NEGATIVE_SEARCH_VECTORS}")
        queries.append(f"{sector} scale-ups to watch {region} {NEGATIVE_SEARCH_VECTORS}")
    random.shuffle(queries)
    return queries[:n]


def _llm_brainstormed_queries(n: int) -> List[str]:
    prompt = (
        f"You are helping a venture-scouting agent discover companies on the open web.\n"
        f"Generate {n} short, diverse Google-style search queries (one per line, no numbering, no quotes) "
        f"that would surface real non-US tech platform companies (roughly $1M-$5M USD revenue or recent funding raised).\n"
        f"Target non-US regions (UK, France, Germany, India, UAE, Singapore, Spain, Switzerland, etc.).\n"
        f"Include negative search terms like {NEGATIVE_SEARCH_VECTORS} to avoid US entities and aggregators.\n"
        f"Favor queries likely to return company official websites or 'about/leadership' pages mentioning a founder/CEO."
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
    # Always generate a rich batch of combinatorial and directory queries with negative vectors
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
