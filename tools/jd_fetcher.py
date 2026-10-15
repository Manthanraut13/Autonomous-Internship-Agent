"""
tools/jd_fetcher.py
-------------------
Fetches full job description text from a job posting URL.
Used when scraped description is too short (< 200 chars) for meaningful semantic matching.
"""

import re
import json
import html
import logging
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _html_to_text(fragment: str) -> str:
    """Plain text from an HTML fragment (JSON-LD descriptions ship <p>/<ul>)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment))).strip()


def fetch_full_job_description(url: str, max_chars: int = 2000) -> Optional[str]:
    """
    Fetches the full job description from a URL, best-structured source first:
      1. JobPosting JSON-LD description (Greenhouse, Lever, Ashby, Workable and
         most career pages ship it — the reliable source for the
         server-rendered-short platforms like Instahyre / HN / RSS boards).
      2. og:description meta (client-rendered shells still emit it).
      3. Main-content selector heuristics on the page text (previous behaviour).

    Returns cleaned text or None if fetch fails or no real content exists.
    """
    if not url or not requests or not BeautifulSoup:
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return None

        # 1. Structured JobPosting JSON-LD — read BEFORE any script stripping.
        for raw in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",
                              resp.text, re.S | re.I):
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            for block in (data if isinstance(data, list) else [data]):
                if isinstance(block, dict) and block.get("@type") == "JobPosting":
                    cleaned = _html_to_text(str(block.get("description") or ""))
                    # Structured data is authoritative: keep it from 100 chars
                    # up (below that it is a teaser stub, not a real JD).
                    if len(cleaned) >= 100:
                        return cleaned[:max_chars]

        soup = BeautifulSoup(resp.text, "html.parser")

        # 2. Open Graph description (client-rendered shells still emit it)
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content") and len(og["content"].strip()) >= 200:
            return re.sub(r"\s+", " ", og["content"]).strip()[:max_chars]

        # Remove script, style, nav, header, footer elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # Try to find the main content area
        main_content = None
        content_selectors = [
            "article",
            "[class*='description']",
            "[class*='job-detail']",
            "[class*='job_description']",
            "[class*='posting']",
            "[class*='content']",
            "main",
        ]

        for selector in content_selectors:
            found = soup.select_one(selector)
            if found and len(found.get_text(strip=True)) > 100:
                main_content = found
                break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # Extract and clean text
        raw_text = main_content.get_text(separator=" ", strip=True)
        # Collapse whitespace
        cleaned = re.sub(r"\s+", " ", raw_text).strip()

        if len(cleaned) < 50:
            return None

        return cleaned[:max_chars]

    except Exception as e:
        logger.debug(f"Failed to fetch JD from {url}: {e}")
        return None
