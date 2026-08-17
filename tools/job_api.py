"""
tools/job_api.py
----------------
Fetches real, live AI internship listings prioritizing high-growth startups.

Top 3 Sources (priority order):
  1. LinkedIn Startups   - real LinkedIn startup AI internships with direct links
  2. Remotive Startups   - live remote startup tech listings
  3. Himalayas Startups  - remote startup job listings

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
# 1. LinkedIn Jobs API (Startup & Internship Focused)
# ---------------------------------------------------------------------------
def fetch_linkedin_jobs(search_query: str = "AI Intern", location: str = "India", limit: int = 10, posted_within_hours: int = 24, start_offset: int = 0) -> List[Dict[str, Any]]:
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        encoded_loc = urllib.parse.quote(location)
        
        # Time filter: r86400 = past 24 hours
        time_filter = "r86400" if posted_within_hours <= 24 else "r604800"
        # f_TPR: time, f_JT=I: Internship job type, f_E=1: Internship/Entry experience level
        url = f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}&location={encoded_loc}&f_TPR={time_filter}&f_JT=I&f_E=1&start={start_offset}"

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            senior_disqualifiers = ["senior", "lead", "staff", "director", "principal", "vp", "head of", "manager", "5+ years", "8+ years"]

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

                    # Filter out experienced full-time senior roles unless 'intern' is explicitly in title
                    title_lower = title.lower()
                    if "intern" not in title_lower and any(disq in title_lower for disq in senior_disqualifiers):
                        continue

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
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]

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

                combined = f"{title} {company} {description}".lower()
                # Ensure relevance to AI / ML / internship or query terms
                if q_terms and not any(t in combined for t in q_terms) and not any(k in title.lower() for k in ["ai", "machine learning", "ml", "intern", "data"]):
                    continue

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
# ---------------------------------------------------------------------------
# 5. Jobicy Startup API (Direct remote/startup listings)
# ---------------------------------------------------------------------------
JOBICY_API_URL = "https://jobicy.com/api/v2/remote-jobs"

def fetch_jobicy_jobs(search_query: str = "ai", limit: int = 10, posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """Fetches remote startup AI/tech jobs from Jobicy public API."""
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        tag = "ai" if "ai" in search_query.lower() else "artificial-intelligence"
        url = f"{JOBICY_API_URL}?count=50&tag={tag}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=posted_within_hours)

            for item in raw_jobs:
                pub_date = item.get("pubDate")
                if pub_date:
                    try:
                        job_time = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        if job_time < cutoff_time:
                            continue
                    except Exception:
                        pass

                title = item.get("jobTitle", "AI Engineer")
                company = item.get("companyName", "AI Startup")
                description = _clean_html(item.get("jobDescription", ""))
                url = item.get("url", "")
                location = item.get("jobGeo", "Remote")

                combined = f"{title} {company} {description}".lower()
                if not q_terms or any(t in combined for t in q_terms) or "ai" in title.lower() or "intern" in title.lower():
                    if url and url.startswith("http"):
                        jobs.append({
                            "title": title,
                            "company": company,
                            "description": description,
                            "link": url,
                            "apply_url": url,
                            "location": location,
                            "source": "jobicy",
                            "posted_at": pub_date or ""
                        })
                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.warning(f"Error fetching Jobicy jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 6. Adzuna API
# ---------------------------------------------------------------------------
def fetch_adzuna_jobs(search_query: str = "software engineer", limit: int = 10, app_id: str = "", api_key: str = "", posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    if requests is None or not app_id or not api_key:
        return []

    jobs: List[Dict[str, Any]] = []
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
# Main entry point - Priority: 1. LinkedIn Startup, 2. Remotive, 3. Other Startup platforms
# ---------------------------------------------------------------------------
def fetch_jobs(search_query: str = "AI Intern", limit: int = 10, posted_within_hours: int = 24, start_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Main entry point — follows exact platform priority:
      1. LinkedIn Startup AI Internships
      2. Remotive Startup AI Internships
      3. LinkedIn AI Internships (Direct)
      4. Himalayas (Remote Startups)
      5. Jobicy (AI Startups)
      6. Arbeitnow (Tech Startups)
      7. JSearch (Aggregator)
      8. Adzuna & Apollo (Fallbacks)

    Cascades seamlessly across all platforms to guarantee the target result count is always met.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()

    def _add_unique(jobs_list):
        for j in jobs_list:
            key = (j.get("apply_url") or j.get("link") or "").strip().lower()
            if key and key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)

    days_old = max(1, posted_within_hours // 24)

    # ── 1. Priority #1: LinkedIn Startup AI Internships ───────────────
    startup_query = f"{search_query} startup"
    linkedin_startup_jobs = fetch_linkedin_jobs(
        startup_query,
        limit=limit,
        posted_within_hours=posted_within_hours,
        start_offset=start_offset
    )
    _add_unique(linkedin_startup_jobs)

    # ── 2. Priority #2: Remotive Remote Startup Jobs ──────────────────
    if len(all_jobs) < limit:
        remotive_jobs = fetch_remotive_jobs(
            search_query,
            limit=limit - len(all_jobs),
            posted_within_hours=posted_within_hours
        )
        _add_unique(remotive_jobs)

    # ── 3. Priority #3: LinkedIn AI Internships (Direct) ──────────────
    if len(all_jobs) < limit:
        linkedin_direct = fetch_linkedin_jobs(
            search_query,
            limit=limit - len(all_jobs),
            posted_within_hours=posted_within_hours,
            start_offset=start_offset
        )
        _add_unique(linkedin_direct)

    # ── 4. Priority #4: Himalayas Startup Jobs ────────────────────────
    if len(all_jobs) < limit:
        himalayas_jobs = fetch_himalayas_jobs(
            search_query,
            limit=limit - len(all_jobs),
            posted_within_hours=posted_within_hours
        )
        _add_unique(himalayas_jobs)

    # ── 5. Priority #5: Jobicy AI Startup Jobs ────────────────────────
    if len(all_jobs) < limit:
        jobicy_jobs = fetch_jobicy_jobs(
            search_query,
            limit=limit - len(all_jobs),
            posted_within_hours=posted_within_hours
        )
        _add_unique(jobicy_jobs)

    # ── 6. Priority #6: Arbeitnow Startup Jobs ────────────────────────
    if len(all_jobs) < limit:
        arbeitnow_jobs = fetch_arbeitnow_jobs(
            search_query,
            limit=limit - len(all_jobs),
            posted_within_hours=posted_within_hours
        )
        _add_unique(arbeitnow_jobs)

    # ── 7. Priority #7: JSearch Multi-Portal Aggregator ───────────────
    if len(all_jobs) < limit:
        jsearch_jobs = fetch_jsearch_jobs(
            search_query,
            limit=limit - len(all_jobs),
            days_old=days_old
        )
        _add_unique(jsearch_jobs)

    # ── 8. Priority #8: Adzuna API (Optional) ─────────────────────────
    if len(all_jobs) < limit:
        try:
            if settings.adzuna_app_id and settings.adzuna_api_key:
                adzuna_jobs = fetch_adzuna_jobs(
                    search_query,
                    limit=limit - len(all_jobs),
                    app_id=settings.adzuna_app_id,
                    api_key=settings.adzuna_api_key,
                    posted_within_hours=posted_within_hours
                )
                _add_unique(adzuna_jobs)
        except Exception as e:
            logger.warning(f"Adzuna fetch skipped: {e}")

    # ── 9. Priority #9: Apollo Fallback ───────────────────────────────
    if len(all_jobs) < limit:
        apollo_jobs = fetch_apollo_jobs(
            search_query,
            limit=limit - len(all_jobs)
        )
        _add_unique(apollo_jobs)

    return all_jobs[:limit]


def get_scraper_platforms() -> List[Dict[str, Any]]:
    """Returns the ordered list of scrapers for top 3 priority platforms."""
    return [
        {
            "name": "LinkedIn Startups",
            "source": "linkedin",
            "fn": lambda q, lim, hrs, off: fetch_linkedin_jobs(f"{q} startup", limit=lim, posted_within_hours=hrs, start_offset=off)
        },
        {
            "name": "Remotive Startups",
            "source": "remotive",
            "fn": lambda q, lim, hrs, off: fetch_remotive_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Himalayas Startups",
            "source": "himalayas",
            "fn": lambda q, lim, hrs, off: fetch_himalayas_jobs(q, limit=lim, posted_within_hours=hrs)
        }
    ]

