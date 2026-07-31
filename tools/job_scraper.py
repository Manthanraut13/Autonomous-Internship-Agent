"""
tools/job_scraper.py
--------------------
Scrapes job listings from various sources (Indeed, internship.com).
"""

import time
import random
import logging
from typing import List, Dict, Any

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None


logger = logging.getLogger(__name__)


def scrape_indeed(search_query: str, num_pages: int = 1, location: str = "") -> List[Dict[str, Any]]:
    """
    Scrapes job listings from Indeed.
    """
    if requests is None or BeautifulSoup is None:
        logger.warning("requests or beautifulsoup4 not installed. Returning empty list.")
        return []

    jobs = []
    base_url = "https://www.indeed.com/jobs"
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    for page in range(num_pages):
        # Indeed uses 'start' parameter (0, 10, 20...)
        params = {
            "q": search_query,
            "l": location,
            "start": page * 10
        }
        
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching Indeed page {page}: {e}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        
        # This selector is a common baseline, though Indeed frequently changes it
        job_cards = soup.find_all("div", class_="job_seen_beacon")
        
        for card in job_cards:
            try:
                title_elem = card.find("h2", class_="jobTitle")
                title = title_elem.text.strip() if title_elem else "Unknown Title"
                
                company_elem = card.find("span", {"data-testid": "company-name"})
                company = company_elem.text.strip() if company_elem else "Unknown Company"
                
                location_elem = card.find("div", {"data-testid": "text-location"})
                loc = location_elem.text.strip() if location_elem else "Unknown Location"
                
                desc_elem = card.find("div", class_="job-snippet")
                description = desc_elem.text.strip() if desc_elem else ""

                link_elem = card.find("a", href=True)
                link = f"https://www.indeed.com{link_elem['href']}" if link_elem else ""

                if link:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": link,
                        "location": loc,
                        "source": "indeed"
                    })
            except Exception as e:
                logger.debug(f"Error parsing an Indeed job card: {e}")
                continue
                
        # Random delay between pages to avoid IP blocking
        time.sleep(random.uniform(2.0, 5.0))

    return jobs


def scrape_internship_com(search_query: str, num_pages: int = 1) -> List[Dict[str, Any]]:
    """
    Scrapes internship listings from internship.com (or equivalent generic scraper).
    """
    if requests is None or BeautifulSoup is None:
        logger.warning("requests or beautifulsoup4 not installed. Returning empty list.")
        return []

    jobs = []
    base_url = "https://www.internships.com/search"
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    for page in range(1, num_pages + 1):
        params = {
            "keywords": search_query,
            "page": page
        }
        
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching internship.com page {page}: {e}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        
        job_cards = soup.find_all("div", class_="posting-card")
        
        for card in job_cards:
            try:
                title_elem = card.find("h3", class_="posting-title")
                title = title_elem.text.strip() if title_elem else "Unknown Title"
                
                company_elem = card.find("div", class_="posting-company")
                company = company_elem.text.strip() if company_elem else "Unknown Company"
                
                desc_elem = card.find("div", class_="posting-description")
                description = desc_elem.text.strip() if desc_elem else ""
                
                link_elem = card.find("a", class_="posting-link", href=True)
                link = f"https://www.internships.com{link_elem['href']}" if link_elem and link_elem['href'].startswith('/') else (link_elem['href'] if link_elem else "")

                if link:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": description,
                        "link": link,
                        "location": "",
                        "source": "internship.com"
                    })
            except Exception as e:
                logger.debug(f"Error parsing internship.com card: {e}")
                continue
                
        time.sleep(random.uniform(2.0, 5.0))

    return jobs


def scrape_all_sources(search_query: str, num_pages: int = 1, location: str = "") -> List[Dict[str, Any]]:
    """
    Main function that calls all configured scrapers, combines the results,
    and deduplicates them based on the job link.
    """
    all_jobs = []
    
    # 1. Scrape Indeed
    try:
        indeed_jobs = scrape_indeed(search_query, num_pages, location)
        all_jobs.extend(indeed_jobs)
    except Exception as e:
        logger.error(f"Failed to scrape Indeed: {e}")

    # 2. Scrape Internship.com
    try:
        intern_jobs = scrape_internship_com(search_query, num_pages)
        all_jobs.extend(intern_jobs)
    except Exception as e:
        logger.error(f"Failed to scrape Internship.com: {e}")

    # Deduplicate by link
    seen_links = set()
    unified_list = []
    
    for job in all_jobs:
        link = job.get("link", "")
        if link and link not in seen_links:
            seen_links.add(link)
            unified_list.append(job)

    return unified_list
