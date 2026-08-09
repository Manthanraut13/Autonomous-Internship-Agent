"""
tools/job_api.py
----------------
Fetches real, live job/internship listings from public APIs and platform endpoints.

Sources (priority order):
  1. LinkedIn Jobs API — real, live LinkedIn job listings with direct LinkedIn URLs
  2. Arbeitnow API    — free, 170+ tech listings, direct Greenhouse/Lever links
  3. Remotive API     — free, live remote tech job listings
  4. Himalayas API    — free, remote tech job listings
  5. Adzuna API      — free tier, 250 req/day (if keys present)
  6. Fallback        — HTML scrapers (tools/job_scraper.py)

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
import urllib.parse
from typing import List, Dict, Any, Optional

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

LINKEDIN_GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
HIMALAYAS_API_URL = "https://himalayas.app/jobs/api"
ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs"


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()[:1500]


# ---------------------------------------------------------------------------
# 1. LinkedIn Jobs API (Real, Live LinkedIn Listings)
# ---------------------------------------------------------------------------

def fetch_linkedin_jobs(search_query: str = "python developer", location: str = "India", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches genuine, live LinkedIn job listings using LinkedIn's public guest search API.
    Returns real LinkedIn job URLs and descriptions.
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        encoded_loc = urllib.parse.quote(location)
        url = f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}&location={encoded_loc}&start=0"

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            for card in cards:
                title_el = card.find("h3", class_="base-search-card__title")
                comp_el = card.find("h4", class_="base-search-card__subtitle")
                link_el = card.find("a", class_="base-card__full-link") or card.find("a")
                loc_el = card.find("span", class_="job-search-card__location")

                if title_el and link_el and link_el.get("href"):
                    title = title_el.text.strip()
                    company = comp_el.text.strip() if comp_el else "Unknown Company"
                    job_link = link_el["href"].split("?")[0]  # clean tracking params
                    job_loc = loc_el.text.strip() if loc_el else location

                    # Fetch brief description for LLM matching
                    description = f"{title} position at {company} in {job_loc}."
                    try:
                        detail_resp = requests.get(job_link, headers=HEADERS, timeout=6)
                        if detail_resp.status_code == 200:
                            d_soup = BeautifulSoup(detail_resp.text, "html.parser")
                            desc_el = d_soup.find("div", class_="show-more-less-html__markup") or d_soup.find("section", class_="description")
                            if desc_el:
                                description = _clean_html(desc_el.text)
                    except Exception:
                        pass

                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": job_link,
                        "apply_url": job_link,
                        "location": job_loc,
                        "source": "linkedin",
                    })

                if len(jobs) >= limit:
                    break

            logger.info(f"LinkedIn API: fetched {len(jobs)} live jobs")
    except Exception as e:
        logger.error(f"Error fetching LinkedIn jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Arbeitnow API (clean tech jobs, direct Greenhouse/Lever apply)
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
                apply_url = f"{link}/apply" if link else ""

                combined_text = f"{title} {company} {description}".lower()

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
# 3. Remotive API
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
# 4. Himalayas API
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
# 5. Adzuna API (optional if keys present)
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
    Main entry point — combines real jobs from multiple platforms.
    Priority: LinkedIn > Arbeitnow > Remotive > Himalayas > Adzuna > HTML scrapers.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()

    def _add_unique(jobs_list):
        for j in jobs_list:
            key = j["link"]
            if key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)

    # 1. LinkedIn Jobs (Real, Live LinkedIn listings)
    linkedin_jobs = fetch_linkedin_jobs(search_query, limit=limit)
    _add_unique(linkedin_jobs)

    # 2. Arbeitnow API (Greenhouse/Lever direct apply links)
    if len(all_jobs) < limit:
        arbeitnow_jobs = fetch_arbeitnow_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(arbeitnow_jobs)

    # 3. Remotive API
    if len(all_jobs) < limit:
        remotive_jobs = fetch_remotive_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(remotive_jobs)

    # 4. Himalayas API
    if len(all_jobs) < limit:
        himalayas_jobs = fetch_himalayas_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(himalayas_jobs)

    # 5. Adzuna API (optional)
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
        except Exception as e:
            logger.warning(f"Adzuna fetch skipped: {e}")

    # 6. Fallback HTML scrapers
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
