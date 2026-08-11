"""
tools/job_api.py
----------------
Fetches real, live job/internship listings from public APIs and platform endpoints.

Sources (priority order):
  1. JSearch API      - free, 500 req/month, aggregates LinkedIn, Indeed, Glassdoor
  2. LinkedIn Jobs    - real, live LinkedIn job listings with direct LinkedIn URLs
  3. Arbeitnow API    - free, 170+ tech listings, direct Greenhouse/Lever links
  4. Remotive API     - free, live remote tech job listings
  5. Himalayas API    - free, remote tech job listings
  6. Adzuna API       - free tier, 250 req/day (if keys present)
  7. Apollo API       - fallback if key present

Returns standardized job dictionaries:
    {
        "title": str,
        "company": str,
        "description": str,
        "link": str,          # main job listing URL
        "apply_url": str,     # direct application URL (if available)
        "location": str,
        "source": str,
        "posted_at": str      # ISO format timestamp or string
    }
"""

import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

from tools.apollo_scraper import fetch_jsearch_jobs, fetch_apollo_jobs
from config.settings import settings

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
# 1. LinkedIn Jobs API
# ---------------------------------------------------------------------------
def fetch_linkedin_jobs(search_query: str = "python developer", location: str = "India", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        encoded_loc = urllib.parse.quote(location)
        
        # Add time filter to LinkedIn (r86400 = past 24 hours, r604800 = past week)
        time_filter = "r86400" if posted_within_hours <= 24 else "r604800"
        url = f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}&location={encoded_loc}&f_TPR={time_filter}&start=0"

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            for card in cards:
                title_el = card.find("h3", class_="base-search-card__title")
                comp_el = card.find("h4", class_="base-search-card__subtitle")
                link_el = card.find("a", class_="base-card__full-link") or card.find("a")
                loc_el = card.find("span", class_="job-search-card__location")
                time_el = card.find("time")

                if title_el and link_el and link_el.get("href"):
                    title = title_el.text.strip()
                    company = comp_el.text.strip() if comp_el else "Unknown Company"
                    job_link = link_el["href"].split("?")[0]
                    job_loc = loc_el.text.strip() if loc_el else location
                    posted_at = time_el["datetime"] if time_el and time_el.get("datetime") else ""

                    description = f"{title} position at {company} in {job_loc}."
                    
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": job_link,
                        "apply_url": job_link,
                        "location": job_loc,
                        "source": "linkedin",
                        "posted_at": posted_at
                    })

                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching LinkedIn jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Arbeitnow API
# ---------------------------------------------------------------------------
def fetch_arbeitnow_jobs(search_query: str = "python", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        resp = requests.get(ARBEITNOW_API_URL, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("data", [])
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=posted_within_hours)

            for item in raw_jobs:
                created_at = item.get("created_at") # Timestamp
                if created_at:
                    try:
                        job_time = datetime.fromtimestamp(created_at, tz=timezone.utc)
                        if job_time < cutoff_time:
                            continue
                    except Exception:
                        pass
                
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
                            "posted_at": datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat() if created_at else ""
                        })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching Arbeitnow jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 3. Remotive API
# ---------------------------------------------------------------------------
def fetch_remotive_jobs(search_query: str = "software engineer", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    params = {"search": search_query, "limit": limit * 2}

    try:
        resp = requests.get(REMOTIVE_API_URL, headers=HEADERS, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=posted_within_hours)
            
            for item in data.get("jobs", []):
                pub_date = item.get("publication_date")
                if pub_date:
                    try:
                        job_time = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        if job_time < cutoff_time:
                            continue
                    except Exception:
                        pass
                        
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
                        "apply_url": url,
                        "location": location,
                        "source": "remotive",
                        "posted_at": pub_date
                    })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching Remotive jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 4. Himalayas API
# ---------------------------------------------------------------------------
def fetch_himalayas_jobs(search_query: str = "python", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
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
            cutoff_time = datetime.now(timezone.utc).timestamp() - (posted_within_hours * 3600)

            for item in raw_jobs:
                pub_date = item.get("published_date", 0) # Unix timestamp
                if pub_date and pub_date < cutoff_time:
                    continue
                    
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
                            "posted_at": datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat() if pub_date else ""
                        })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching Himalayas jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 5. Adzuna API
# ---------------------------------------------------------------------------
def fetch_adzuna_jobs(search_query: str = "software engineer", limit: int = 10, app_id: str = "", api_key: str = "", posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    if requests is None or not app_id or not api_key:
        return []

    jobs: List[Dict[str, Any]] = []
    # max_days filter
    max_days = max(1, posted_within_hours // 24)
    url = f"{ADZUNA_API_URL}/us/search/1"
    
    params = {
        "app_id": app_id,
        "app_key": api_key,
        "results_per_page": limit,
        "what": search_query,
        "content-type": "application/json",
        "max_days_old": max_days
    }
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("results", []):
                title = item.get("title", "Unknown Title")
                company = item.get("company", {}).get("display_name", "Unknown Company")
                description = _clean_html(item.get("description", ""))
                link = item.get("redirect_url", "")
                loc_obj = item.get("location", {})
                loc_str = ", ".join(loc_obj.get("area", ["Remote"]))
                created = item.get("created", "")

                if link:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": link,
                        "apply_url": link,
                        "location": loc_str,
                        "source": "adzuna",
                        "posted_at": created
                    })
    except Exception as e:
        logger.error(f"Error fetching Adzuna jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_jobs(search_query: str = "software engineer", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Main entry point — combines real jobs from multiple platforms.
    Priority: JSearch > LinkedIn > Arbeitnow > Remotive > Himalayas > Adzuna > Apollo
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()

    def _add_unique(jobs_list):
        for j in jobs_list:
            key = j.get("apply_url") or j.get("link")
            if key and key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)

    days_old = max(1, posted_within_hours // 24)

    # 1. JSearch API
    jsearch_jobs = fetch_jsearch_jobs(search_query, limit=limit, days_old=days_old)
    _add_unique(jsearch_jobs)

    # 2. LinkedIn Jobs 
    if len(all_jobs) < limit:
        linkedin_jobs = fetch_linkedin_jobs(search_query, limit=limit - len(all_jobs), posted_within_hours=posted_within_hours)
        _add_unique(linkedin_jobs)

    # 3. Arbeitnow API 
    if len(all_jobs) < limit:
        arbeitnow_jobs = fetch_arbeitnow_jobs(search_query, limit=limit - len(all_jobs), posted_within_hours=posted_within_hours)
        _add_unique(arbeitnow_jobs)

    # 4. Remotive API
    if len(all_jobs) < limit:
        remotive_jobs = fetch_remotive_jobs(search_query, limit=limit - len(all_jobs), posted_within_hours=posted_within_hours)
        _add_unique(remotive_jobs)

    # 5. Himalayas API
    if len(all_jobs) < limit:
        himalayas_jobs = fetch_himalayas_jobs(search_query, limit=limit - len(all_jobs), posted_within_hours=posted_within_hours)
        _add_unique(himalayas_jobs)

    # 6. Adzuna API (optional)
    if len(all_jobs) < limit:
        try:
            if settings.adzuna_app_id and settings.adzuna_api_key:
                adzuna_jobs = fetch_adzuna_jobs(
                    search_query, limit - len(all_jobs),
                    app_id=settings.adzuna_app_id,
                    api_key=settings.adzuna_api_key,
                    posted_within_hours=posted_within_hours
                )
                _add_unique(adzuna_jobs)
        except Exception as e:
            logger.warning(f"Adzuna fetch skipped: {e}")
            
    # 7. Apollo fallback
    if len(all_jobs) < limit:
        apollo_jobs = fetch_apollo_jobs(search_query, limit=limit - len(all_jobs))
        _add_unique(apollo_jobs)

    return all_jobs[:limit]

