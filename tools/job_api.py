"""
tools/job_api.py
----------------
Fetches real, live job/internship listings from free public APIs.

Primary sources:
  - Jobicy API (https://jobicy.com/api/v2/remote-jobs)
  - Remotive API (https://remotive.com/api/remote-jobs)
Fallback:
  - HTML Scrapers (tools/job_scraper.py)

Returns standardized job dictionaries with valid, live URLs:
    {
        "title": str,
        "company": str,
        "description": str,
        "link": str,
        "location": str,
        "source": str,
    }
"""

import logging
import re
from typing import List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
JOBICY_API_URL = "https://jobicy.com/api/v2/remote-jobs"


def fetch_jobicy_jobs(search_query: str = "python", limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch real remote tech jobs from Jobicy API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        tag = "python" if "python" in search_query.lower() else ("dev" if "dev" in search_query.lower() else "")
        url = f"{JOBICY_API_URL}?count={limit}"
        if tag:
            url += f"&tag={tag}"

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            for item in raw_jobs[:limit]:
                title = item.get("jobTitle", "Software Engineer")
                company = item.get("companyName", "Tech Company")
                description = item.get("jobDescription", "")
                link = item.get("url", "")
                location = item.get("jobGeo", "Remote")

                clean_desc = re.sub(r"<[^>]+>", " ", description)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()[:1500]

                if link and link.startswith("http"):
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": clean_desc,
                        "link": link,
                        "location": location,
                        "source": "jobicy",
                    })
    except Exception as e:
        logger.error(f"Error fetching Jobicy jobs: {e}")

    return jobs


def fetch_remotive_jobs(search_query: str = "software intern", limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch real remote job listings from the Remotive API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    params = {"search": search_query, "limit": limit}

    try:
        resp = requests.get(REMOTIVE_API_URL, headers=HEADERS, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            for item in raw_jobs[:limit]:
                title = item.get("title", "Unknown Title")
                company = item.get("company_name", "Unknown Company")
                description = item.get("description", "")
                url = item.get("url", "")
                location = item.get("candidate_required_location", "Remote")

                clean_desc = re.sub(r"<[^>]+>", " ", description)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()[:1500]

                if url and url.startswith("http"):
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": clean_desc,
                        "link": url,
                        "location": location,
                        "source": "remotive",
                    })
    except Exception as e:
        logger.error(f"Error fetching Remotive jobs: {e}")

    return jobs


def fetch_jobs(search_query: str = "software engineer", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Main entry point — combines real jobs from Jobicy API and Remotive API with valid live URLs.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()

    # 1. Fetch from Jobicy API
    jobicy_jobs = fetch_jobicy_jobs(search_query, limit=limit)
    for j in jobicy_jobs:
        if j["link"] not in seen_links:
            seen_links.add(j["link"])
            all_jobs.append(j)

    # 2. Fetch from Remotive API
    remotive_jobs = fetch_remotive_jobs(search_query, limit=limit)
    for j in remotive_jobs:
        if j["link"] not in seen_links:
            seen_links.add(j["link"])
            all_jobs.append(j)

    # 3. Fallback to HTML scrapers if API counts are zero
    if not all_jobs:
        logger.info("API sources returned 0 jobs, invoking fallback HTML scrapers…")
        try:
            from tools.job_scraper import scrape_all_sources
            scraped = scrape_all_sources(search_query, num_pages=1)
            for j in scraped:
                if j.get("link") and j["link"] not in seen_links:
                    seen_links.add(j["link"])
                    all_jobs.append(j)
        except Exception as e:
            logger.error(f"Fallback scraper failed: {e}")

    return all_jobs[:limit]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = fetch_jobs("python engineer", limit=5)
    for i, job in enumerate(results, 1):
        print(f"\n--- Job {i} ---")
        print(f"  Title   : {job['title']}")
        print(f"  Company : {job['company']}")
        print(f"  Link    : {job['link']}")
        print(f"  Source  : {job['source']}")
