"""
Search layer.

Supports:
1. SerpApi (serpapi.com) / Serper (serper.dev) for Google-backed live search.
2. DuckDuckGo (via ddgs package and direct HTML fallback) for 100% free search.
"""

import os
import time
import urllib.parse
from typing import Dict, List

import requests

from . import config

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


def _search_serpapi(query: str, num: int) -> List[Dict]:
    api_key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return []
    try:
        url = f"https://serpapi.com/search.json?q={urllib.parse.quote(query)}&num={num}&api_key={api_key}"
        resp = requests.get(url, timeout=config.REQUEST_TIMEOUT_SECS)
        if resp.status_code == 200:
            data = resp.json()
            out = []
            for item in data.get("organic_results", [])[:num]:
                out.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    }
                )
            return out
    except Exception:
        pass
    return []


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
        if resp.status_code == 200:
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
        pass
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
    # 1. Try SerpApi (serpapi.com)
    results = _search_serpapi(query, num)

    # 2. Try Serper (serper.dev)
    if not results:
        results = _search_serper(query, num)
    
    # 3. Try DDGS library
    if not results:
        results = _search_ddg(query, num)
        
    # 4. Try direct DDG HTML fallback
    if not results:
        results = _search_ddg_html(query, num)
        
    time.sleep(0.3)
    return results
