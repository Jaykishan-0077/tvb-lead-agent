"""
Builds high-intent, targeted search queries to discover non-US tech startups
with $1M–$10M in total funding or current revenue.

Strategy:
  1. Concrete Funding News & Press Queries (action verbs + exact dollar amounts $1M–$10M).
  2. Direct Tech TLD Targeting (site:.ai, site:.io, site:.co, site:.app) landing on official sites.
  3. Regional Early-Stage Lead Investor & Accelerator Announcements.
  4. LLM-Brainstormed High-Intent Scouting Queries.
"""

import random
from typing import List

from . import config

try:
    import anthropic
except ImportError:
    anthropic = None

# Negative vectors: block US entities and Delaware corporate shells
NEGATIVE_VECTORS = '-"Delaware" -"Inc" -"United States" -"San Francisco"'

REGIONS = [
    ("UK", "GBP"),
    ("Germany", "EUR"),
    ("France", "EUR"),
    ("Netherlands", "EUR"),
    ("Sweden", "EUR"),
    ("Spain", "EUR"),
    ("India", "USD"),
    ("Singapore", "USD"),
    ("UAE", "USD"),
    ("Saudi Arabia", "USD"),
    ("Kenya", "USD"),
    ("Nigeria", "USD"),
    ("Egypt", "USD"),
    ("South Africa", "USD"),
    ("Brazil", "USD"),
    ("Mexico", "USD"),
    ("Australia", "USD"),
]

SECTORS = [
    "fintech",
    "B2B SaaS",
    "AI platform",
    "healthtech",
    "insurtech",
    "supply chain tech",
    "edtech",
    "climate tech",
    "cybersecurity",
    "digital twin",
    "workforce tech",
    "logistics tech",
    "proptech",
    "embedded finance",
    "enterprise AI",
]

VERBS = ["raised", "secures", "closes", "bags", "announces"]
ROUNDS = ['"seed round"', '"seed funding"', '"pre-series A"', '"Series A"']


def _funding_announcements_queries(n: int) -> List[str]:
    """Generates high-intent queries that match real funding news and press releases."""
    queries = []
    for sector in SECTORS:
        region, currency = random.choice(REGIONS)
        verb = random.choice(VERBS)
        rnd = random.choice(ROUNDS)

        if currency == "GBP":
            tier = '"$2 million" OR "$3 million" OR "£2 million" OR "£3 million" OR "£5 million"'
        elif currency == "EUR":
            tier = '"$2 million" OR "$3 million" OR "$5 million" OR "€2 million" OR "€3 million" OR "€5 million"'
        else:
            tier = '"$1.5 million" OR "$2 million" OR "$3 million" OR "$4 million" OR "$5 million" OR "$7 million" OR "$8 million"'

        q = f'{sector} startup {region} {verb} {tier} {rnd} founder CEO {NEGATIVE_VECTORS}'
        queries.append(q)

        # Alternative variant with quotes on sector
        q2 = f'"{sector}" startup {region} ("raised $2 million" OR "raised $3 million" OR "raised $5 million") seed founder {NEGATIVE_VECTORS}'
        queries.append(q2)

    random.shuffle(queries)
    return queries[:n]


def _tld_targeted_queries(n: int) -> List[str]:
    """Directly targets modern tech startup TLDs (.ai, .io, .co, .app) landing on official homepages."""
    queries = []
    tld_configs = [
        (".ai", ["AI platform", "AI startup", "agentic AI", "machine learning platform"]),
        (".io", ["B2B SaaS", "developer platform", "cloud infrastructure", "logistics tech"]),
        (".app", ["fintech", "digital banking", "insurtech", "edtech platform"]),
        (".co", ["enterprise platform", "B2B marketplace", "healthtech", "supply chain"]),
    ]

    for tld, sectors in tld_configs:
        for sec in sectors:
            region, _ = random.choice(REGIONS)
            q = f'site:{tld} "{sec}" ("seed round" OR "seed funding" OR "backed by") {region} founder {NEGATIVE_VECTORS}'
            queries.append(q)

    random.shuffle(queries)
    return queries[:n]


def _accelerator_investor_queries(n: int) -> List[str]:
    """Targets companies backed by top early-stage seed funds and accelerators."""
    queries = []
    investors = [
        "Speedinvest", "LocalGlobe", "Peak XV", "Antler", "East Ventures",
        "Endiya Partners", "MassMutual Ventures", "Pitchdrive", "Kalaari Capital",
        "Blossom Capital", "Partech", "Founders Factory"
    ]
    for inv in investors:
        region, _ = random.choice(REGIONS)
        tier = '"$2 million" OR "$3 million" OR "$4 million" OR "$5 million" OR "$6 million"'
        q = f'startup {region} "seed round led by {inv}" OR "{inv} leads" {tier} {NEGATIVE_VECTORS}'
        queries.append(q)

    random.shuffle(queries)
    return queries[:n]


def _llm_brainstormed_queries(n: int) -> List[str]:
    prompt = (
        f"You are helping a venture-scouting agent discover startups on the open web.\n"
        f"Generate {n} realistic Google search queries (one per line, no numbering) "
        f"to find non-US tech startups (UK, Europe, India, UAE, Singapore, Africa, LatAm, Australia) "
        f"that have raised between $1M and $10M total funding or seed rounds.\n"
        f"Each query should combine a sector, non-US region, a funding amount (e.g. '$2 million' or '$5 million' or '€3 million'), "
        f"and a role ('CEO' or 'founder').\n"
        f"Include {NEGATIVE_VECTORS} at the end of each query.\n"
        f"Examples:\n"
        f"  healthtech startup India secures \"$2 million\" OR \"$3 million\" seed round founder CEO {NEGATIVE_VECTORS}\n"
        f"  AI startup France \"raised €3 million\" OR \"raised €5 million\" seed CEO {NEGATIVE_VECTORS}\n"
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
    llm_share = min(10, max(3, max_queries // 5))

    queries = []
    # 1. Real funding news & press announcement queries (highest yield)
    queries.extend(_funding_announcements_queries(int(max_queries * 0.6)))

    # 2. Direct TLD targeted queries (.ai, .io, .co, .app)
    queries.extend(_tld_targeted_queries(int(max_queries * 0.25)))

    # 3. Accelerator & lead investor queries
    queries.extend(_accelerator_investor_queries(int(max_queries * 0.15)))

    # 4. LLM brainstorming
    llm_queries = _llm_brainstormed_queries(llm_share)
    if llm_queries:
        queries = llm_queries + queries

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q)

    random.shuffle(unique)
    return unique[:max_queries]
