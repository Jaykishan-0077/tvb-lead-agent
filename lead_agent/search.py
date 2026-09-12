"""
Search layer.

Uses DuckDuckGo (via the `ddgs` package) as the default, key-free search
backend so the reviewer can trigger a run without provisioning a paid search
API. If a Serper.dev API key (SERPER_API_KEY) is present in the environment,
it's used instead/in addition, since Google-backed results are often higher
quality and less rate-limited.
"""

import os
import time
from typing import Dict, List

import requests

from . import config

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - fallback name used by older package
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


def _search_serper(query: str, num: int) -> List[Dict]:
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=config.REQUEST_TIMEOUT_SECS,
        )
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get("organic", [])[:num]:
            out.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
        return out
    except Exception:
        return []


def _search_ddg(query: str, num: int) -> List[Dict]:
    if DDGS is None:
        return []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=num)
        out = []
        for item in results or []:
            out.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("href") or item.get("link", ""),
                    "snippet": item.get("body", ""),
                }
            )
        return out
    except Exception:
        return []


def search(query: str, num: int = None) -> List[Dict]:
    num = num or config.RESULTS_PER_QUERY
    results = _search_serper(query, num)
    if not results:
        results = _search_ddg(query, num)
        time.sleep(0.8)  # be polite to the free backend
    return results
