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


def _search_ddg_html(query: str, num: int) -> List[Dict]:
    """Direct HTTP fallback to DuckDuckGo HTML search if DDGS library is absent or blocked."""
    try:
        from bs4 import BeautifulSoup
        import urllib.parse
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        resp = requests.post(
            url,
            headers=headers,
            data={"q": query},
            timeout=config.REQUEST_TIMEOUT_SECS,
        )
        if resp.status_code != 200:
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result in soup.find_all("div", class_="result"):
            a_elem = result.find("a", class_="result__url") or result.find("a", class_="result__snippet")
            title_elem = result.find("a", class_="result__a")
            snippet_elem = result.find("a", class_="result__snippet")
            
            href = a_elem.get("href") if a_elem else (title_elem.get("href") if title_elem else "")
            title = title_elem.get_text().strip() if title_elem else ""
            snippet = snippet_elem.get_text().strip() if snippet_elem else ""
            
            if href and not href.startswith("/"):
                # Clean up duckduckgo redirect urls if present
                if "duckduckgo.com/l/?uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = parsed.get("uddg", [href])[0]
                results.append({"title": title, "url": href, "snippet": snippet})
                if len(results) >= num:
                    break
        return results
    except Exception:
        return []


def search(query: str, num: int = None) -> List[Dict]:
    num = num or config.RESULTS_PER_QUERY
    # 1. Try Serper if key available
    results = _search_serper(query, num)
    
    # 2. Try DDGS library
    if not results:
        results = _search_ddg(query, num)
        
    # 3. Try direct DDG HTML fallback
    if not results:
        results = _search_ddg_html(query, num)
        
    time.sleep(0.5)  # polite backoff
    return results
