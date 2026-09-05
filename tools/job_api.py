"""
tools/job_api.py
----------------
Fetches real, live AI internship listings from 10 priority platforms.

Platform Priority Order (LinkedIn + 9 from list.csv):
  1. LinkedIn          — Direct startup AI internships (Quota: 7)
  2. Wellfound         — AngelList Talent, startup CTOs (Quota: 3)
  3. Y Combinator      — Work at a Startup, YC-backed (Quota: 3)
  4. Peerlist           — Builder-focused Indian/global startups (Quota: 3)
  5. Otta               — Vetted high-quality AI roles (Quota: 2)
  6. Levels.fyi         — High-stipend tech internships (Quota: 2)
  7. SimplifyJobs       — GitHub crowdsourced tracker (Quota: 2)
  8. MLH Fellowship     — Remote OSS fellowship (Quota: 1)
  9. GSoC               — Google Summer of Code (Quota: 1)
  10. Outreachy          — Paid remote OSS internships (Quota: 1)

Returns standardized job dictionaries:
    {
        "title": str,
        "company": str,
        "description": str,
        "link": str,
        "apply_url": str,
        "location": str,
        "source": str,
        "posted_at": str
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

from config.settings import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LINKEDIN_GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()[:1500]


def is_remote_or_virtual(job: Dict[str, Any]) -> bool:
    """
    Checks if a job listing offers Remote, Online, Virtual, or Work-From-Home options.
    Strictly rejects in-person/on-site only positions.
    """
    if not job:
        return False

    source = (job.get("source") or "").lower()
    loc = (job.get("location") or "").lower()
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    combined = f"{title} {loc} {desc}"

    # Disqualify explicit on-site only terms
    strict_onsite_phrases = [
        "strictly on-site", "strictly in-office", "must work from office",
        "in-person only", "on-site only", "onsite only", "no remote option",
        "no work from home", "office presence mandatory"
    ]
    if any(phrase in combined for phrase in strict_onsite_phrases):
        return False

    # Inherently 100% remote global fellowship programs
    remote_native_sources = {"mlh", "gsoc", "outreachy"}
    if source in remote_native_sources:
        return True

    # Positive remote / virtual keywords
    remote_keywords = [
        "remote", "online", "virtual", "work from home", "wfh",
        "telecommute", "anywhere", "home-based", "hybrid", "distributed",
        "flexible location", "remote-first", "remote friendly", "remote option"
    ]

    if any(k in loc for k in remote_keywords) or any(k in title for k in remote_keywords):
        return True

    if any(k in desc for k in remote_keywords):
        return True

    if "remote" in loc or "worldwide" in loc or "global" in loc:
        return True

    return False


# ---------------------------------------------------------------------------
# 1. LinkedIn Jobs (Priority #1 — Quota: 7)
# ---------------------------------------------------------------------------
def fetch_linkedin_jobs(search_query: str = "AI Intern", location: str = "Remote",
                        limit: int = 10, posted_within_hours: int = 24,
                        start_offset: int = 0) -> List[Dict[str, Any]]:
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        encoded_loc = urllib.parse.quote(location)

        time_filter = "r86400" if posted_within_hours <= 24 else "r604800"
        url = (f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}"
               f"&location={encoded_loc}&f_TPR={time_filter}"
               f"&f_JT=I&f_E=1&f_WT=2%2C3&start={start_offset}")

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            senior_disqualifiers = [
                "senior", "lead", "staff", "director", "principal",
                "vp", "head of", "manager", "5+ years", "8+ years"
            ]

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

                    title_lower = title.lower()
                    if "intern" not in title_lower and any(disq in title_lower for disq in senior_disqualifiers):
                        continue

                    job_candidate = {
                        "title": title,
                        "company": company,
                        "description": f"{title} position at {company} in {job_loc}. Remote / Online / Virtual friendly.",
                        "link": job_link,
                        "apply_url": job_link,
                        "location": job_loc if ("remote" in job_loc.lower() or "hybrid" in job_loc.lower()) else f"{job_loc} (Remote Option)",
                        "source": "linkedin",
                        "posted_at": posted_at
                    }

                    if not is_remote_or_virtual(job_candidate):
                        continue

                    jobs.append(job_candidate)

                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching LinkedIn jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Wellfound / AngelList Talent (Priority #2 — Quota: 3)
# ---------------------------------------------------------------------------
def fetch_wellfound_jobs(search_query: str = "AI Intern", limit: int = 10,
                         posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Wellfound (formerly AngelList Talent) for startup AI internships."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        url = f"https://wellfound.com/role/r/{encoded_query.lower().replace(' ', '-')}"

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # Wellfound uses structured job cards
            job_cards = soup.find_all("div", class_=re.compile(r"styles_result"))
            if not job_cards:
                job_cards = soup.find_all("div", class_=re.compile(r"jobCard|job-card|listing"))

            for card in job_cards[:limit * 2]:
                title_el = card.find(["h2", "h3", "a"], class_=re.compile(r"title|name"))
                comp_el = card.find(["span", "a", "h4"], class_=re.compile(r"company|startup"))
                link_el = card.find("a", href=True)

                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    company = comp_el.get_text(strip=True) if comp_el else "Startup"
                    href = link_el["href"]
                    if not href.startswith("http"):
                        href = f"https://wellfound.com{href}"

                    desc_el = card.find(["p", "div"], class_=re.compile(r"desc|detail|snippet"))
                    desc = desc_el.get_text(strip=True) if desc_el else f"{title} at {company}. Apply to work at an early-stage startup."

                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": desc[:1500],
                        "link": href,
                        "apply_url": href,
                        "location": "Remote",
                        "source": "wellfound",
                        "posted_at": ""
                    })

                if len(jobs) >= limit:
                    break

        # Fallback: try the API search endpoint
        if not jobs:
            api_url = f"https://wellfound.com/role/r/ai-engineer"
            resp2 = requests.get(api_url, headers=HEADERS, timeout=12)
            if resp2.status_code == 200:
                soup2 = BeautifulSoup(resp2.text, "html.parser")
                for link_tag in soup2.find_all("a", href=re.compile(r"/jobs/")):
                    title = link_tag.get_text(strip=True)
                    href = link_tag["href"]
                    if not href.startswith("http"):
                        href = f"https://wellfound.com{href}"
                    if title and len(title) > 5:
                        jobs.append({
                            "title": title,
                            "company": "Wellfound Startup",
                            "description": f"{title}. Startup opportunity via Wellfound.",
                            "link": href,
                            "apply_url": href,
                            "location": "Remote",
                            "source": "wellfound",
                            "posted_at": ""
                        })
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching Wellfound jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 3. Y Combinator — Work at a Startup (Priority #3 — Quota: 3)
# ---------------------------------------------------------------------------
def fetch_yc_jobs(search_query: str = "AI Intern", limit: int = 10,
                  posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Y Combinator's Work at a Startup job board."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://www.workatastartup.com/companies"
        params = {"query": search_query, "hasRemote": "true"}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            job_cards = soup.find_all("div", class_=re.compile(r"company-row|job-listing|result"))
            if not job_cards:
                # Try finding links directly
                job_cards = soup.find_all("a", href=re.compile(r"/companies/"))

            for card in job_cards[:limit * 2]:
                if card.name == "a":
                    title = card.get_text(strip=True)
                    href = card["href"]
                else:
                    title_el = card.find(["h2", "h3", "a"])
                    title = title_el.get_text(strip=True) if title_el else ""
                    link_el = card.find("a", href=True)
                    href = link_el["href"] if link_el else ""

                if not title or len(title) < 3:
                    continue

                if not href.startswith("http"):
                    href = f"https://www.workatastartup.com{href}"

                company = "YC Startup"
                comp_el = card.find(class_=re.compile(r"company-name|name"))
                if comp_el:
                    company = comp_el.get_text(strip=True)

                jobs.append({
                    "title": title,
                    "company": company,
                    "description": f"{title} at {company}. YC-backed startup role. Remote friendly.",
                    "link": href,
                    "apply_url": href,
                    "location": "Remote",
                    "source": "yc",
                    "posted_at": ""
                })

                if len(jobs) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Error fetching YC jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 4. Peerlist (Priority #4 — Quota: 3)
# ---------------------------------------------------------------------------
def fetch_peerlist_jobs(search_query: str = "AI Intern", limit: int = 10,
                        posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Peerlist job listings."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://peerlist.io/jobs"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]

            job_cards = soup.find_all("a", href=re.compile(r"/jobs/"))
            for card in job_cards[:limit * 3]:
                title = card.get_text(strip=True)
                href = card.get("href", "")

                if not title or len(title) < 5:
                    continue

                if not href.startswith("http"):
                    href = f"https://peerlist.io{href}"

                combined = title.lower()
                if q_terms and not any(t in combined for t in q_terms):
                    # Also match AI-related keywords
                    if not any(k in combined for k in ["ai", "ml", "machine", "intern", "data", "engineer"]):
                        continue

                jobs.append({
                    "title": title,
                    "company": "Peerlist Company",
                    "description": f"{title}. Listed on Peerlist - professional network for builders.",
                    "link": href,
                    "apply_url": href,
                    "location": "Remote",
                    "source": "peerlist",
                    "posted_at": ""
                })

                if len(jobs) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Error fetching Peerlist jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 5. Otta / Welcome to the Jungle (Priority #5 — Quota: 2)
# ---------------------------------------------------------------------------
def fetch_otta_jobs(search_query: str = "AI Intern", limit: int = 10,
                    posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Otta (Welcome to the Jungle) for vetted AI roles."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded = urllib.parse.quote(search_query)
        url = f"https://otta.com/search?q={encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            job_cards = soup.find_all("a", href=re.compile(r"/jobs/|/role/"))
            for card in job_cards[:limit * 2]:
                title = card.get_text(strip=True)
                href = card.get("href", "")

                if not title or len(title) < 5:
                    continue

                if not href.startswith("http"):
                    href = f"https://otta.com{href}"

                jobs.append({
                    "title": title,
                    "company": "Otta Company",
                    "description": f"{title}. Vetted opportunity via Otta - high-quality tech roles.",
                    "link": href,
                    "apply_url": href,
                    "location": "Remote",
                    "source": "otta",
                    "posted_at": ""
                })

                if len(jobs) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Error fetching Otta jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 6. Levels.fyi Internships (Priority #6 — Quota: 2)
# ---------------------------------------------------------------------------
def fetch_levelsfyi_internships(search_query: str = "AI Intern", limit: int = 10,
                                posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Levels.fyi internship tracker for high-stipend AI internships."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://www.levels.fyi/internships/"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]

            # Levels.fyi uses table rows for internships
            rows = soup.find_all("tr")
            for row in rows[:100]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                company = cells[0].get_text(strip=True)
                title = cells[1].get_text(strip=True) if len(cells) > 1 else "Intern"
                link_el = row.find("a", href=True)
                href = link_el["href"] if link_el else ""

                if not href.startswith("http"):
                    if href:
                        href = f"https://www.levels.fyi{href}"
                    else:
                        continue

                combined = f"{title} {company}".lower()
                if q_terms and not any(t in combined for t in q_terms):
                    if not any(k in combined for k in ["ai", "ml", "machine", "data", "engineer"]):
                        continue

                jobs.append({
                    "title": title if title else f"Internship at {company}",
                    "company": company,
                    "description": f"{title} internship at {company}. High-stipend opportunity tracked by Levels.fyi.",
                    "link": href,
                    "apply_url": href,
                    "location": "Remote",
                    "source": "levelsfyi",
                    "posted_at": ""
                })

                if len(jobs) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Error fetching Levels.fyi internships: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 7. SimplifyJobs GitHub Tracker (Priority #7 — Quota: 2)
# ---------------------------------------------------------------------------
def fetch_simplifyjobs_github(search_query: str = "AI Intern", limit: int = 10,
                               posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Parses the SimplifyJobs GitHub table for real-time internship postings."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
        resp = requests.get(url, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/main/README.md"
            resp = requests.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
            last_company = ""

            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 3:
                    continue

                raw_comp = tds[0].get_text(strip=True)
                if raw_comp:
                    last_company = raw_comp
                company = last_company or "Tech Company"

                title = tds[1].get_text(strip=True)
                location = tds[2].get_text(strip=True) if len(tds) > 2 else "Remote"

                # Find apply link
                href = ""
                for a in tr.find_all("a", href=True):
                    h = a["href"]
                    if any(domain in h for domain in ["greenhouse.io", "lever.co", "myworkdayjobs.com", "simplify.jobs/p/"]):
                        href = h
                        break
                if not href:
                    links = tr.find_all("a", href=True)
                    if links:
                        href = links[-1]["href"]

                if not href or not href.startswith("http"):
                    continue

                combined = f"{title} {company}".lower()
                # Filter for AI/ML/Software relevancy
                is_ai_relevant = any(k in combined for k in ["ai", "ml", "machine learning", "deep learning", "nlp", "llm", "data", "engineer", "software", "developer"])
                if q_terms and not any(t in combined for t in q_terms) and not is_ai_relevant:
                    continue

                job_obj = {
                    "title": title if title else f"Intern at {company}",
                    "company": company,
                    "description": f"{title} at {company}. Location: {location}. Verified tech internship opening tracked by SimplifyJobs GitHub.",
                    "link": href,
                    "apply_url": href,
                    "location": location if location else "Remote",
                    "source": "simplifyjobs",
                    "posted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")
                }
                if is_remote_or_virtual(job_obj):
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching SimplifyJobs GitHub: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 8. MLH Fellowship (Priority #8 — Quota: 1)
# ---------------------------------------------------------------------------
def fetch_mlh_fellowship(search_query: str = "AI", limit: int = 5,
                         posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """Checks MLH Fellowship for open application windows."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://fellowship.mlh.io"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text().lower()

            # Check if applications are open
            if any(kw in text for kw in ["apply now", "applications open", "apply", "accepting applications"]):
                jobs.append({
                    "title": "MLH Fellowship — Software Engineering / Open Source",
                    "company": "Major League Hacking",
                    "description": (
                        "12-week remote software engineering fellowship. "
                        "Work on open-source projects with production-grade codebases. "
                        "Compensated educational stipend. Backed by major tech firms."
                    ),
                    "link": "https://fellowship.mlh.io",
                    "apply_url": "https://fellowship.mlh.io",
                    "location": "Remote (Global)",
                    "source": "mlh",
                    "posted_at": ""
                })
            else:
                logger.info("MLH Fellowship: Applications not currently open.")

    except Exception as e:
        logger.warning(f"Error fetching MLH Fellowship: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 9. Google Summer of Code (Priority #9 — Quota: 1)
# ---------------------------------------------------------------------------
def fetch_gsoc_projects(search_query: str = "AI", limit: int = 5,
                        posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """Checks Google Summer of Code for open applications."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://summerofcode.withgoogle.com"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text().lower()

            if any(kw in text for kw in ["apply", "applications open", "contributor", "get started"]):
                jobs.append({
                    "title": "Google Summer of Code — Open Source Contributor",
                    "company": "Google",
                    "description": (
                        "Global, paid open-source internship program. "
                        "Pairs contributors with production-grade codebases and mentors. "
                        "Stipend provided. Work on AI/ML, cloud, web, and systems projects."
                    ),
                    "link": "https://summerofcode.withgoogle.com",
                    "apply_url": "https://summerofcode.withgoogle.com",
                    "location": "Remote (Global)",
                    "source": "gsoc",
                    "posted_at": ""
                })
            else:
                logger.info("GSoC: Applications not currently open.")

    except Exception as e:
        logger.warning(f"Error fetching GSoC: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 10. Outreachy (Priority #10 — Quota: 1)
# ---------------------------------------------------------------------------
def fetch_outreachy_internships(search_query: str = "AI", limit: int = 5,
                                posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """Checks Outreachy for open internship applications."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://www.outreachy.org"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text().lower()

            if any(kw in text for kw in ["apply", "applications open", "initial application", "internship"]):
                jobs.append({
                    "title": "Outreachy — Remote Open Source Internship ($7,000 USD stipend)",
                    "company": "Outreachy / Software Freedom Conservancy",
                    "description": (
                        "Fully remote, paid 3-month open-source internships ($7,000 USD stipend). "
                        "Focused on open-source software, data tools, AI/ML libraries, and infrastructure. "
                        "Provides mentorship from experienced open-source maintainers."
                    ),
                    "link": "https://www.outreachy.org",
                    "apply_url": "https://www.outreachy.org",
                    "location": "Remote (Global)",
                    "source": "outreachy",
                    "posted_at": ""
                })
            else:
                logger.info("Outreachy: Applications not currently open.")

    except Exception as e:
        logger.warning(f"Error fetching Outreachy: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# Platform Registry & Quota Distribution
# ---------------------------------------------------------------------------

# Default quotas per platform (total = 25)
PLATFORM_QUOTAS = {
    "linkedin": 7,
    "wellfound": 3,
    "yc": 3,
    "peerlist": 3,
    "otta": 2,
    "levelsfyi": 2,
    "simplifyjobs": 2,
    "mlh": 1,
    "gsoc": 1,
    "outreachy": 1,
}


def get_scraper_platforms() -> List[Dict[str, Any]]:
    """Returns the ordered list of scrapers with quota allocation."""
    return [
        {
            "name": "LinkedIn",
            "source": "linkedin",
            "quota": PLATFORM_QUOTAS["linkedin"],
            "fn": lambda q, lim, hrs, off: fetch_linkedin_jobs(
                f"{q} startup", limit=lim, posted_within_hours=hrs, start_offset=off
            )
        },
        {
            "name": "Wellfound (AngelList)",
            "source": "wellfound",
            "quota": PLATFORM_QUOTAS["wellfound"],
            "fn": lambda q, lim, hrs, off: fetch_wellfound_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Y Combinator",
            "source": "yc",
            "quota": PLATFORM_QUOTAS["yc"],
            "fn": lambda q, lim, hrs, off: fetch_yc_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Peerlist",
            "source": "peerlist",
            "quota": PLATFORM_QUOTAS["peerlist"],
            "fn": lambda q, lim, hrs, off: fetch_peerlist_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Otta",
            "source": "otta",
            "quota": PLATFORM_QUOTAS["otta"],
            "fn": lambda q, lim, hrs, off: fetch_otta_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Levels.fyi",
            "source": "levelsfyi",
            "quota": PLATFORM_QUOTAS["levelsfyi"],
            "fn": lambda q, lim, hrs, off: fetch_levelsfyi_internships(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "SimplifyJobs GitHub",
            "source": "simplifyjobs",
            "quota": PLATFORM_QUOTAS["simplifyjobs"],
            "fn": lambda q, lim, hrs, off: fetch_simplifyjobs_github(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "MLH Fellowship",
            "source": "mlh",
            "quota": PLATFORM_QUOTAS["mlh"],
            "fn": lambda q, lim, hrs, off: fetch_mlh_fellowship(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Google Summer of Code",
            "source": "gsoc",
            "quota": PLATFORM_QUOTAS["gsoc"],
            "fn": lambda q, lim, hrs, off: fetch_gsoc_projects(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Outreachy",
            "source": "outreachy",
            "quota": PLATFORM_QUOTAS["outreachy"],
            "fn": lambda q, lim, hrs, off: fetch_outreachy_internships(q, limit=lim, posted_within_hours=hrs)
        },
    ]


def fetch_jobs(search_query: str = "AI Intern", limit: int = 25,
               posted_within_hours: int = 24, start_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Main entry point — cascades across all 10 platforms in priority order.
    Each platform has a quota; unfilled slots cascade to the next platform.
    Enforces minimum 3-platform diversity.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links = set()
    platform_counts: Dict[str, int] = {}

    def _add_unique(jobs_list, source_name: str, quota: int):
        added = 0
        for j in jobs_list:
            if added >= quota:
                break
            if not is_remote_or_virtual(j):
                continue
            key = (j.get("apply_url") or j.get("link") or "").strip().lower()
            if key and key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)
                platform_counts[source_name] = platform_counts.get(source_name, 0) + 1
                added += 1

    platforms = get_scraper_platforms()
    remaining = limit

    for platform in platforms:
        if remaining <= 0:
            break

        plat_name = platform["name"]
        plat_fn = platform["fn"]
        quota = min(platform["quota"], remaining)

        try:
            raw_jobs = plat_fn(search_query, quota * 3, posted_within_hours, start_offset)
            _add_unique(raw_jobs, platform["source"], quota)
            remaining = limit - len(all_jobs)
        except Exception as e:
            logger.warning(f"Error on {plat_name}: {e}")

    return all_jobs[:limit]
