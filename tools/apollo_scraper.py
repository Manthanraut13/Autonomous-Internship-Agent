"""
tools/apollo_scraper.py
-----------------------
Scrapes job listings using JSearch API (RapidAPI) or Apollo.io API (if available).
JSearch aggregates LinkedIn, Indeed, Glassdoor, etc., and offers a free tier (500 req/mo).
"""

import logging
import urllib.parse
from typing import List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

from config.settings import settings

logger = logging.getLogger(__name__)

def fetch_jsearch_jobs(search_query: str, limit: int = 10, days_old: int = 1) -> List[Dict[str, Any]]:
    """
    Fetches job listings from JSearch API via RapidAPI.
    Filter by 'today' to get recent jobs (last 24 hours).
    """
    if not settings.jsearch_api_key:
        logger.warning("No JSearch API key provided, skipping JSearch scraper.")
        return []

    if not requests:
        logger.error("requests library not installed.")
        return []

    url = "https://jsearch.p.rapidapi.com/search"
    date_posted = "today" if days_old <= 1 else "3days"
    
    querystring = {
        "query": search_query,
        "page": "1",
        "num_pages": "1",
        "date_posted": date_posted
    }

    headers = {
        "X-RapidAPI-Key": settings.jsearch_api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    jobs = []
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data[:limit]:
                title = item.get("job_title", "")
                company = item.get("employer_name", "")
                if not title or not company:
                    continue
                
                job_link = item.get("job_apply_link") or item.get("job_google_link") or ""
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": f"{item.get('job_city', '')}, {item.get('job_country', '')}".strip(", "),
                    "description": item.get("job_description", ""),
                    "link": job_link,
                    "apply_url": item.get("job_apply_link", ""),
                    "source": "jsearch",
                    "posted_at": item.get("job_posted_at_datetime_utc", "")
                })
        else:
            logger.error(f"JSearch API error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Failed to fetch JSearch jobs: {e}")

    return jobs

def fetch_apollo_jobs(search_query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Stub for Apollo.io API (requires paid plan for job search endpoint).
    """
    if not settings.apollo_api_key:
        logger.warning("No Apollo API key provided, skipping Apollo scraper.")
        return []
    
    logger.warning("Apollo API for job postings requires Organization ID enumeration which is not implemented for generic search.")
    return []
