"""
tools/job_api.py
----------------
Fetches real, live job/internship listings from public APIs.

Sources (priority order):
  1. Arbeitnow API — free, 170+ tech listings, direct Greenhouse/Lever links, no Cloudflare blocks
  2. Remotive API  — free, live remote tech job listings, clean access
  3. Himalayas API — free, remote tech job listings
  4. Adzuna API   — free tier, 250 req/day (if keys present)
  5. Fallback     — HTML scrapers (tools/job_scraper.py)

Returns standardized job dictionaries:
    {
        "title": str,
        "company": str,
        "description": str,
        "link": str,          # main job listing URL
        "apply_url": str,     # direct application URL (if available)
        "location": str,
        "source": str,
    }
"""

import logging
import re
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
HIMALAYAS_API_URL = "https://himalayas.app/jobs/api"
ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs"


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()[:1500]


# ---------------------------------------------------------------------------
# 1. Arbeitnow API (best source — clean tech jobs, direct Greenhouse/Lever apply)
# ---------------------------------------------------------------------------

def fetch_arbeitnow_jobs(search_query: str = "python", limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch real tech jobs from Arbeitnow API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        resp = requests.get(ARBEITNOW_API_URL, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("data", [])
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]

            for item in raw_jobs:
                title = item.get("title", "Software Engineer")
                company = item.get("company_name", "Tech Company")
                description = _clean_html(item.get("description", ""))
                link = item.get("url", "")
                location = item.get("location", "Remote")

                # Direct apply link on Arbeitnow ends with /apply
                apply_url = f"{link}/apply" if link else ""

                combined_text = f"{title} {company} {description}".lower()

                # Match search query terms if any term matches, or fallback if query is general
                if not q_terms or any(term in combined_text for term in q_terms) or "engineer" in combined_text or "developer" in combined_text:
                    if link and link.startswith("http"):
                        jobs.append({
                            "title": title,
                            "company": company,
                            "description": description,
                            "link": link,
                            "apply_url": apply_url,
                            "location": location or "Remote",
                            "source": "arbeitnow",
                        })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching Arbeitnow jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Remotive API
# ---------------------------------------------------------------------------

def fetch_remotive_jobs(search_query: str = "software engineer", limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch real remote job listings from the Remotive API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    params = {"search": search_query, "limit": limit}

    try:
        resp = requests.get(REMOTIVE_API_URL, headers=HEADERS, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("jobs", [])[:limit]:
                title = item.get("title", "Unknown Title")
                company = item.get("company_name", "Unknown Company")
                description = _clean_html(item.get("description", ""))
                url = item.get("url", "")
                location = item.get("candidate_required_location", "Remote")

                if url and url.startswith("http"):
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": url,
                        "apply_url": "",
                        "location": location,
                        "source": "remotive",
                    })
    except Exception as e:
        logger.error(f"Error fetching Remotive jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 3. Himalayas API
# ---------------------------------------------------------------------------

def fetch_himalayas_jobs(search_query: str = "python", limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch tech jobs from Himalayas API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = f"{HIMALAYAS_API_URL}?limit={limit * 2}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]

            for item in raw_jobs:
                title = item.get("title", "Software Engineer")
                company = item.get("companyName", "Tech Company")
                description = _clean_html(item.get("description", ""))
                link = item.get("applicationLink", "")
                location = item.get("locationRestriction", ["Remote"])
                loc_str = ", ".join(location) if isinstance(location, list) else "Remote"

                combined = f"{title} {company} {description}".lower()
                if not q_terms or any(t in combined for t in q_terms):
                    if link and link.startswith("http"):
                        jobs.append({
                            "title": title,
                            "company": company,
                            "description": description,
                            "link": link,
                            "apply_url": link,
                            "location": loc_str,
                            "source": "himalayas",
                        })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching Himalayas jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 4. Adzuna API (optional if keys present)
# ---------------------------------------------------------------------------

def fetch_adzuna_jobs(
    search_query: str = "python developer",
    limit: int = 10,
    app_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch jobs from Adzuna API."""
    if requests is None or not app_id or not api_key:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = f"{ADZUNA_API_URL}/gb/search/1"
        params = {
            "app_id": app_id,
            "app_key": api_key,
            "results_per_page": limit,
            "what": search_query,
            "content-type": "application/json",
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("results", []):
                title = item.get("title", "Unknown")
                company = item.get("company", {}).get("display_name", "Unknown")
                description = _clean_html(item.get("description", ""))
                link = item.get("redirect_url", "")
                location = item.get("location", {}).get("display_name", "Remote")

                if link and link.startswith("http"):
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": link,
                        "apply_url": link,
                        "location": location,
                        "source": "adzuna",
                    })
    except Exception as e:
        logger.error(f"Error fetching Adzuna jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_jobs(search_query: str = "software engineer", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Main entry point — combines real jobs from multiple APIs without Cloudflare blocks.
    Priority: Arbeitnow (Greenhouse/Lever links) > Remotive > Himalayas > Adzuna > HTML scrapers.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()

    def _add_unique(jobs_list):
        for j in jobs_list:
            key = j["link"]
            if key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)

    # 1. Arbeitnow API (best source — clean tech jobs, direct Greenhouse/Lever apply)
    arbeitnow_jobs = fetch_arbeitnow_jobs(search_query, limit=limit)
    _add_unique(arbeitnow_jobs)
    logger.info(f"Arbeitnow: fetched {len(arbeitnow_jobs)} jobs")

    # 2. Remotive API
    if len(all_jobs) < limit:
        remotive_jobs = fetch_remotive_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(remotive_jobs)
        logger.info(f"Remotive: fetched {len(remotive_jobs)} jobs")

    # 3. Himalayas API
    if len(all_jobs) < limit:
        himalayas_jobs = fetch_himalayas_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(himalayas_jobs)
        logger.info(f"Himalayas: fetched {len(himalayas_jobs)} jobs")

    # 4. Adzuna API (optional)
    if len(all_jobs) < limit:
        try:
            from config.settings import settings
            if settings.adzuna_app_id and settings.adzuna_api_key:
                adzuna_jobs = fetch_adzuna_jobs(
                    search_query, limit - len(all_jobs),
                    app_id=settings.adzuna_app_id,
                    api_key=settings.adzuna_api_key,
                )
                _add_unique(adzuna_jobs)
                logger.info(f"Adzuna: fetched {len(adzuna_jobs)} jobs")
        except Exception as e:
            logger.warning(f"Adzuna fetch skipped: {e}")

    # 5. Fallback HTML scrapers
    if not all_jobs:
        logger.info("All API sources returned 0 jobs, invoking fallback HTML scrapers…")
        try:
            from tools.job_scraper import scrape_all_sources
            scraped = scrape_all_sources(search_query, num_pages=1)
            _add_unique(scraped)
        except Exception as e:
            logger.error(f"Fallback scraper failed: {e}")

    return all_jobs[:limit]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = fetch_jobs("python developer", limit=5)
    for i, job in enumerate(results, 1):
        print(f"\n--- Job {i} ---")
        print(f"  Title    : {job['title']}")
        print(f"  Company  : {job['company']}")
        print(f"  Link     : {job['link']}")
        print(f"  Apply URL: {job.get('apply_url', 'N/A')}")
        print(f"  Source   : {job['source']}")
