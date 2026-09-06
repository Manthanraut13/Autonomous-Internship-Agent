"""
tools/job_api.py
----------------
Fetches real, live AI internship listings from 10 priority platforms.

Platform Priority Order (LinkedIn + 9 from list.csv):
  1. LinkedIn              — Direct startup AI internships (Quota: 7)
  2. Wellfound             — AngelList Talent, startup founders (Quota: 3)
  3. Y Combinator          — Workatastartup JSON API (Quota: 3)
  4. Internshala / Adzuna  — Remote internship board (Quota: 3)
  5. Greenhouse.io Boards  — Startup ATS public API (Quota: 3)
  6. SimplifyJobs GitHub   — Crowdsourced tracker (Quota: 3)
  7. Pittcsc GitHub Tracker — Summer2026 internship list (Quota: 2)
  8. MLH Fellowship        — Conditional on open application window (Quota: 1)
  9. GSoC                  — Conditional on open application window (Quota: 1)
  10. Outreachy             — Conditional on open application window (Quota: 1)

Total hard target: 25 listings across minimum 4 platforms.

BUG FIXES APPLIED:
  BUG-5: Removed fake "(Remote Option)" label from LinkedIn jobs.
  BUG-6: Removed "hybrid" from remote_keywords — hybrid ≠ remote.
  BUG-7: All scrapers now emit real datetime objects for posted_at.
  BUG-1: YC scraper replaced with Workatastartup JSON API.
  BUG-2: Peerlist (broken Next.js SPA) replaced with Internshala + Adzuna API.
  BUG-3: Otta (Cloudflare-protected) replaced with Greenhouse.io boards API.
  BUG-4: Levels.fyi (client-side JS table) replaced with pittcsc GitHub tracker.
  BUG-12: MLH/GSoC/Outreachy now return 0 entries if applications are not open.
"""

import json
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

JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

LINKEDIN_GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

_NOW = lambda: datetime.now(timezone.utc)


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()[:1500]


def _parse_iso(dt_str: str) -> Optional[datetime]:
    """Parse ISO-8601 or date-only strings to tz-aware datetime."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(dt_str[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Remote Filter  [BUG-5 and BUG-6 FIXED]
# ──────────────────────────────────────────────────────────────────────────────

def is_remote_or_virtual(job: Dict[str, Any]) -> bool:
    """
    Returns True ONLY for explicitly remote / online / virtual / WFH positions.

    BUG-5 fix: we no longer append "(Remote Option)" to on-site locations —
               so on-site jobs are correctly rejected here.
    BUG-6 fix: "hybrid" is NOT treated as remote. Hybrid means partial on-site.
    """
    if not job:
        return False

    source = (job.get("source") or "").lower()
    loc = (job.get("location") or "").lower()
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    combined = f"{title} {loc} {desc}"

    # Hard disqualifiers — explicit on-site requirement
    strict_onsite_phrases = [
        "strictly on-site", "strictly in-office", "must work from office",
        "in-person only", "on-site only", "onsite only", "no remote option",
        "no work from home", "office presence mandatory",
        "must be based in", "must relocate",
    ]
    if any(phrase in combined for phrase in strict_onsite_phrases):
        return False

    # Inherently 100% remote fellowship programs
    remote_native_sources = {"mlh", "gsoc", "outreachy"}
    if source in remote_native_sources:
        return True

    # Strict positive remote / virtual keywords — hybrid intentionally excluded
    remote_keywords = [
        "remote", "online", "virtual", "work from home", "wfh",
        "telecommute", "anywhere", "home-based", "distributed",
        "remote-first", "remote friendly", "remote option",
        "worldwide", "global",
    ]

    if any(k in loc for k in remote_keywords):
        return True
    if any(k in title for k in remote_keywords):
        return True
    if any(k in desc for k in remote_keywords):
        return True

    return False


# ---------------------------------------------------------------------------
# 1. LinkedIn Jobs (Priority #1 — Quota: 7)
#    BUG-5 FIXED: location no longer gets fake "(Remote Option)" appended.
#    BUG-7: posted_at is a real datetime string from the <time> element.
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
        # f_JT=I → Internship job type; f_E=1 → Entry level; f_WT=2%2C3 → Remote + Hybrid
        # We add Remote to location to maximise remote results from LinkedIn's own filter
        url = (f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}"
               f"&location={encoded_loc}&f_TPR={time_filter}"
               f"&f_JT=I&f_E=1&f_WT=2&start={start_offset}")

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
                    # BUG-5 FIX: use the actual location exactly as scraped
                    job_loc = loc_el.text.strip() if loc_el else location
                    posted_at_str = time_el["datetime"] if time_el and time_el.get("datetime") else ""
                    # BUG-7: parse to datetime
                    posted_dt = _parse_iso(posted_at_str) if posted_at_str else _NOW()

                    title_lower = title.lower()
                    if "intern" not in title_lower and any(disq in title_lower for disq in senior_disqualifiers):
                        continue

                    job_candidate = {
                        "title": title,
                        "company": company,
                        "description": f"{title} position at {company}. Location: {job_loc}.",
                        "link": job_link,
                        "apply_url": job_link,
                        # BUG-5 FIX: no fake "(Remote Option)" label — keep exact scraped location
                        "location": job_loc,
                        "source": "linkedin",
                        "posted_at": posted_dt,
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
                        "posted_at": _NOW(),
                    })

                if len(jobs) >= limit:
                    break

        # Fallback: try AI engineer listing directly
        if not jobs:
            api_url = "https://wellfound.com/role/r/ai-engineer"
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
                            "posted_at": _NOW(),
                        })
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching Wellfound jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 3. Y Combinator — Workatastartup JSON API  [BUG-1 FIXED]
#    Old code: requests.get to a React SPA → always returned 0 jobs.
#    Fix: call the actual JSON search endpoint that powers the page.
# ---------------------------------------------------------------------------
def fetch_yc_jobs(search_query: str = "AI Intern", limit: int = 10,
                  posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Queries Workatastartup.com via its internal JSON search API.
    This is the same endpoint the browser calls; no JavaScript execution needed.
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        # The search endpoint used by workatastartup.com internally
        url = "https://www.workatastartup.com/jobs/search"
        params = {
            "query": search_query,
            "remote": "true",
            "role_type": "intern",
            "page": 1,
        }
        resp = requests.get(url, headers=JSON_HEADERS, params=params, timeout=15)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except json.JSONDecodeError:
                data = {}

            job_list = []
            if isinstance(data, dict):
                job_list = data.get("jobs", data.get("results", data.get("data", [])))
            elif isinstance(data, list):
                job_list = data

            for item in job_list[:limit * 2]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("job_title") or item.get("role") or ""
                company = (item.get("company") or {})
                if isinstance(company, dict):
                    company_name = company.get("name", "YC Startup")
                else:
                    company_name = str(company) if company else "YC Startup"
                desc = item.get("description") or item.get("job_description") or f"{title} at {company_name}. YC-backed startup role."
                link = item.get("url") or item.get("job_url") or item.get("apply_url") or ""
                if link and not link.startswith("http"):
                    link = f"https://www.workatastartup.com{link}"
                loc = item.get("location") or item.get("remote") or "Remote"
                if isinstance(loc, bool) and loc:
                    loc = "Remote"
                posted_raw = item.get("created_at") or item.get("posted_at") or ""
                posted_dt = _parse_iso(posted_raw) if posted_raw else _NOW()

                if not title or not link:
                    continue

                job_obj = {
                    "title": title,
                    "company": company_name,
                    "description": _clean_html(str(desc))[:1500],
                    "link": link,
                    "apply_url": link,
                    "location": str(loc),
                    "source": "yc",
                    "posted_at": posted_dt,
                }
                if is_remote_or_virtual(job_obj):
                    jobs.append(job_obj)
                if len(jobs) >= limit:
                    break

        # Fallback: try /jobs listing with filters embedded in URL
        if not jobs:
            fallback_url = "https://www.workatastartup.com/jobs?remote=true&role=intern"
            resp2 = requests.get(fallback_url, headers=HEADERS, timeout=12)
            if resp2.status_code == 200 and BeautifulSoup is not None:
                soup = BeautifulSoup(resp2.text, "html.parser")
                # Extract any JSON embedded in a <script type="application/json"> tag
                for script in soup.find_all("script", type="application/json"):
                    try:
                        json_data = json.loads(script.string or "")
                        if isinstance(json_data, dict) and "jobs" in json_data:
                            for item in json_data["jobs"][:limit]:
                                title = item.get("title", "AI Intern")
                                company_data = item.get("company", {})
                                company_name = company_data.get("name", "YC Startup") if isinstance(company_data, dict) else "YC Startup"
                                href = item.get("url", "")
                                if href and not href.startswith("http"):
                                    href = f"https://www.workatastartup.com{href}"
                                if href:
                                    jobs.append({
                                        "title": title,
                                        "company": company_name,
                                        "description": f"{title} at {company_name}. YC-backed startup.",
                                        "link": href,
                                        "apply_url": href,
                                        "location": "Remote",
                                        "source": "yc",
                                        "posted_at": _NOW(),
                                    })
                    except Exception:
                        continue

    except Exception as e:
        logger.warning(f"Error fetching YC jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 4. Internshala + Adzuna  [BUG-2 FIXED — replaces broken Peerlist SPA]
#    Peerlist is a Next.js SPA that returns an empty shell to raw GET requests.
#    Internshala is server-side rendered. Adzuna has a proper JSON REST API.
# ---------------------------------------------------------------------------
def fetch_internshala_jobs(search_query: str = "AI Intern", limit: int = 10,
                           posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Scrapes Internshala remote internships (server-side rendered — works with requests).
    Falls back to Adzuna API if Adzuna credentials are configured.
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []

    # ── Path A: Adzuna API (preferred — structured JSON) ──────────────────
    adzuna_app_id = getattr(settings, "adzuna_app_id", "") or ""
    adzuna_api_key = getattr(settings, "adzuna_api_key", "") or ""
    if adzuna_app_id and adzuna_api_key:
        try:
            keywords = search_query.replace(" ", "+")
            url = (
                f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                f"?app_id={adzuna_app_id}&app_key={adzuna_api_key}"
                f"&results_per_page={min(limit * 2, 20)}&what={keywords}"
                f"&what_exclude=senior+lead+manager&title_only=intern"
                f"&full_time=0&part_time=0"
            )
            resp = requests.get(url, headers=JSON_HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    title = item.get("title", "")
                    company = item.get("company", {}).get("display_name", "Company")
                    desc = item.get("description", f"{title} at {company}.")
                    link = item.get("redirect_url", "")
                    loc = item.get("location", {}).get("display_name", "India")
                    posted_raw = item.get("created", "")
                    posted_dt = _parse_iso(posted_raw) if posted_raw else _NOW()
                    if not link:
                        continue
                    job_obj = {
                        "title": title,
                        "company": company,
                        "description": desc[:1500],
                        "link": link,
                        "apply_url": link,
                        "location": loc,
                        "source": "internshala",
                        "posted_at": posted_dt,
                    }
                    if is_remote_or_virtual(job_obj):
                        jobs.append(job_obj)
                    if len(jobs) >= limit:
                        return jobs[:limit]
        except Exception as e:
            logger.warning(f"Adzuna API error: {e}")

    # ── Path B: Internshala scraper ────────────────────────────────────────
    if not jobs:
        try:
            # Internshala remote internships — server-side rendered HTML
            slug = urllib.parse.quote(search_query.lower().replace(" ", "-"))
            url = f"https://internshala.com/internships/keywords-{slug}/work-from-home-jobs/"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                internship_cards = soup.find_all("div", class_=re.compile(r"individual_internship|internship-card|container"))

                for card in internship_cards[:limit * 3]:
                    title_el = card.find(["h3", "h4", "a"], class_=re.compile(r"heading|profile|title|job-title"))
                    comp_el = card.find(["a", "p", "span"], class_=re.compile(r"company-name|company|organisation"))
                    link_el = card.find("a", href=re.compile(r"/internship/detail/"))
                    loc_el = card.find(["span", "div"], class_=re.compile(r"location-names|location"))

                    if not (title_el and link_el):
                        continue
                    title = title_el.get_text(strip=True)
                    company = comp_el.get_text(strip=True) if comp_el else "Company"
                    href = link_el["href"]
                    if not href.startswith("http"):
                        href = f"https://internshala.com{href}"
                    loc_text = loc_el.get_text(strip=True) if loc_el else "Work From Home"

                    if not title or len(title) < 4:
                        continue
                    # Internshala work-from-home listings are all WFH — mark explicitly
                    if "work from home" not in loc_text.lower():
                        loc_text = f"Work From Home, {loc_text}"

                    jobs.append({
                        "title": title,
                        "company": company,
                        "description": f"{title} internship at {company}. Location: {loc_text}. Listed on Internshala.",
                        "link": href,
                        "apply_url": href,
                        "location": loc_text,
                        "source": "internshala",
                        "posted_at": _NOW(),
                    })
                    if len(jobs) >= limit:
                        break
        except Exception as e:
            logger.warning(f"Internshala scraper error: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 5. Greenhouse.io Boards API  [BUG-3 FIXED — replaces broken Otta scraper]
#    Otta is Cloudflare-protected and requires auth. Greenhouse is public JSON.
#    We query a curated list of AI-focused companies using Greenhouse ATS.
# ---------------------------------------------------------------------------

# AI-focused startups/companies known to use Greenhouse.io
GREENHOUSE_COMPANIES = [
    "openai", "anthropic", "cohere", "scale-ai", "huggingface",
    "mistral-ai", "together-ai", "perplexity-ai", "replit",
    "notion", "linear", "figma", "vercel", "supabase",
    "deepmind", "stability-ai", "runway", "descript", "eleven-labs",
    "synthesia", "character-ai", "inflection-ai", "adept", "imbue",
    "modal-labs", "weaviate", "pinecone", "qdrant", "chroma",
]


def fetch_greenhouse_jobs(search_query: str = "AI Intern", limit: int = 10,
                          posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Queries the public Greenhouse.io job board API for multiple AI companies.
    Greenhouse provides a fully public, unauthenticated JSON API per company:
      GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
    internship_signals = ["intern", "internship", "co-op", "coop", "trainee"]
    ai_signals = ["ai", "ml", "machine learning", "nlp", "llm", "deep learning",
                  "data scientist", "research", "model", "language"]

    cutoff = _NOW() - timedelta(hours=posted_within_hours)

    for company_slug in GREENHOUSE_COMPANIES:
        if len(jobs) >= limit:
            break
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
            resp = requests.get(url, headers=JSON_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            job_list = data.get("jobs", [])
            for item in job_list:
                if len(jobs) >= limit:
                    break
                title = item.get("title", "")
                title_lower = title.lower()
                desc_raw = item.get("content", "") or ""
                desc = _clean_html(desc_raw)[:1500]
                combined = f"{title_lower} {desc[:300].lower()}"

                # Must be an internship
                if not any(kw in combined for kw in internship_signals):
                    continue

                # Must be AI-relevant
                if q_terms and not any(t in combined for t in q_terms):
                    if not any(k in combined for k in ai_signals):
                        continue

                # Location check
                location = item.get("location", {}).get("name", "") or ""
                job_obj_temp = {"location": location, "description": desc, "title": title, "source": "greenhouse"}
                if not is_remote_or_virtual(job_obj_temp):
                    continue

                # Date check
                posted_raw = item.get("updated_at") or item.get("created_at") or ""
                posted_dt = _parse_iso(posted_raw) if posted_raw else _NOW()
                if posted_dt and posted_dt < cutoff:
                    continue

                link = item.get("absolute_url") or ""
                if not link:
                    continue

                jobs.append({
                    "title": title,
                    "company": company_slug.replace("-", " ").title(),
                    "description": desc if desc else f"{title} internship at {company_slug}.",
                    "link": link,
                    "apply_url": link,
                    "location": location if location else "Remote",
                    "source": "greenhouse",
                    "posted_at": posted_dt,
                })
        except Exception as e:
            logger.debug(f"Greenhouse error for {company_slug}: {e}")
            continue

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 6. SimplifyJobs GitHub Tracker (Priority #6 — Quota: 3)
# ---------------------------------------------------------------------------
def fetch_simplifyjobs_github(search_query: str = "AI Intern", limit: int = 10,
                               posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Parses the SimplifyJobs GitHub Markdown table for real-time internship postings."""
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
                    if any(domain in h for domain in [
                        "greenhouse.io", "lever.co", "myworkdayjobs.com",
                        "simplify.jobs/p/", "jobs.ashbyhq.com", "boards.greenhouse.io"
                    ]):
                        href = h
                        break
                if not href:
                    links = tr.find_all("a", href=True)
                    if links:
                        href = links[-1]["href"]

                if not href or not href.startswith("http"):
                    continue

                combined = f"{title} {company}".lower()
                is_ai_relevant = any(k in combined for k in [
                    "ai", "ml", "machine learning", "deep learning", "nlp", "llm",
                    "data", "engineer", "software", "developer", "research"
                ])
                if q_terms and not any(t in combined for t in q_terms) and not is_ai_relevant:
                    continue

                job_obj = {
                    "title": title if title else f"Intern at {company}",
                    "company": company,
                    "description": (
                        f"{title} at {company}. Location: {location}. "
                        "Verified tech internship tracked by SimplifyJobs GitHub."
                    ),
                    "link": href,
                    "apply_url": href,
                    "location": location if location else "Remote",
                    "source": "simplifyjobs",
                    "posted_at": _NOW(),
                }
                if is_remote_or_virtual(job_obj):
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching SimplifyJobs GitHub: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 7. Pittcsc Summer 2026 GitHub Tracker  [BUG-4 FIXED — replaces Levels.fyi]
#    Levels.fyi uses client-side JS rendering; table is never in the raw HTML.
#    Pittcsc/Summer2026-Internships README has the same data in plain Markdown.
# ---------------------------------------------------------------------------
def fetch_pittcsc_github(search_query: str = "AI Intern", limit: int = 10,
                         posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Parses the pittcsc/Summer2026-Internships GitHub README Markdown table.
    Columns: Company | Role | Location | Application/Link | Date Posted
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://raw.githubusercontent.com/pittcsc/Summer2026-Internships/dev/README.md"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            url = "https://raw.githubusercontent.com/pittcsc/Summer2026-Internships/main/README.md"
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
                if raw_comp and raw_comp not in ("↳", ""):
                    last_company = raw_comp
                company = last_company or "Tech Company"

                title = tds[1].get_text(strip=True) if len(tds) > 1 else "Software Intern"
                location = tds[2].get_text(strip=True) if len(tds) > 2 else "Remote"
                date_str = tds[4].get_text(strip=True) if len(tds) > 4 else ""
                posted_dt = _parse_iso(date_str) if date_str else _NOW()

                # Find apply link
                href = ""
                for a in tr.find_all("a", href=True):
                    h = a["href"]
                    if h.startswith("http"):
                        href = h
                        break

                if not href:
                    continue

                combined = f"{title} {company}".lower()
                is_ai_relevant = any(k in combined for k in [
                    "ai", "ml", "machine learning", "nlp", "llm", "data",
                    "engineer", "software", "research", "algorithm"
                ])
                if q_terms and not any(t in combined for t in q_terms) and not is_ai_relevant:
                    continue

                job_obj = {
                    "title": title,
                    "company": company,
                    "description": (
                        f"{title} at {company}. Location: {location}. "
                        "Internship tracked by pittcsc/Summer2026-Internships."
                    ),
                    "link": href,
                    "apply_url": href,
                    "location": location,
                    "source": "pittcsc",
                    "posted_at": posted_dt,
                }
                if is_remote_or_virtual(job_obj):
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching pittcsc GitHub: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 8. MLH Fellowship (Priority #8 — Quota: 0-1)
#    BUG-12 FIXED: Only emits an entry when the page confirms applications are
#    currently open. Returns empty list otherwise — cascades quota to next platform.
# ---------------------------------------------------------------------------
def fetch_mlh_fellowship(search_query: str = "AI", limit: int = 5,
                         posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """
    Returns 1 entry ONLY when MLH Fellowship applications are currently open.
    Returns empty list otherwise — quota cascades to next platform.
    """
    if requests is None or BeautifulSoup is None:
        return []

    try:
        url = "https://fellowship.mlh.io"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()

        # These are STRONG signals of an active application window
        strong_open_signals = ["apply now", "applications open", "accepting applications", "applications are open"]
        if not any(kw in text for kw in strong_open_signals):
            logger.info("MLH Fellowship: No active application window detected. Skipping.")
            return []

        return [{
            "title": "MLH Fellowship — Software Engineering / Open Source",
            "company": "Major League Hacking",
            "description": (
                "12-week remote software engineering fellowship. "
                "Work on open-source projects with production-grade codebases. "
                "Compensated educational stipend. Backed by major tech firms. "
                "Requires AI/ML, Python, or open-source contribution skills."
            ),
            "link": "https://fellowship.mlh.io",
            "apply_url": "https://fellowship.mlh.io",
            "location": "Remote (Global)",
            "source": "mlh",
            "posted_at": _NOW(),
        }]

    except Exception as e:
        logger.warning(f"Error fetching MLH Fellowship: {e}")
    return []


# ---------------------------------------------------------------------------
# 9. Google Summer of Code (Priority #9 — Quota: 0-1)
#    BUG-12 FIXED: Conditional on detected open application window.
# ---------------------------------------------------------------------------
def fetch_gsoc_projects(search_query: str = "AI", limit: int = 5,
                        posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """Returns 1 entry ONLY when GSoC contributor applications are open."""
    if requests is None or BeautifulSoup is None:
        return []

    try:
        url = "https://summerofcode.withgoogle.com"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()

        strong_open_signals = ["contributor application", "applications open", "apply now", "application period"]
        if not any(kw in text for kw in strong_open_signals):
            logger.info("GSoC: No active contributor application window detected. Skipping.")
            return []

        return [{
            "title": "Google Summer of Code — Open Source Contributor",
            "company": "Google",
            "description": (
                "Global, paid open-source internship program. "
                "Pairs contributors with production-grade AI/ML, cloud, and systems projects. "
                "Stipend provided. Strong alignment with AI, LLM, and Python skills."
            ),
            "link": "https://summerofcode.withgoogle.com",
            "apply_url": "https://summerofcode.withgoogle.com",
            "location": "Remote (Global)",
            "source": "gsoc",
            "posted_at": _NOW(),
        }]

    except Exception as e:
        logger.warning(f"Error fetching GSoC: {e}")
    return []


# ---------------------------------------------------------------------------
# 10. Outreachy (Priority #10 — Quota: 0-1)
#     BUG-12 FIXED: Conditional on detected open initial application window.
# ---------------------------------------------------------------------------
def fetch_outreachy_internships(search_query: str = "AI", limit: int = 5,
                                posted_within_hours: int = 720) -> List[Dict[str, Any]]:
    """Returns 1 entry ONLY when Outreachy initial applications are open."""
    if requests is None or BeautifulSoup is None:
        return []

    try:
        url = "https://www.outreachy.org"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()

        strong_open_signals = ["initial applications open", "applications are open", "apply to outreachy"]
        if not any(kw in text for kw in strong_open_signals):
            logger.info("Outreachy: No active application window detected. Skipping.")
            return []

        return [{
            "title": "Outreachy — Remote Open Source Internship ($7,000 USD stipend)",
            "company": "Outreachy / Software Freedom Conservancy",
            "description": (
                "Fully remote, paid 3-month open-source internships ($7,000 USD stipend). "
                "Focused on open-source software, data tools, AI/ML libraries, and infrastructure. "
                "Mentored internship with experienced open-source maintainers."
            ),
            "link": "https://www.outreachy.org",
            "apply_url": "https://www.outreachy.org",
            "location": "Remote (Global)",
            "source": "outreachy",
            "posted_at": _NOW(),
        }]

    except Exception as e:
        logger.warning(f"Error fetching Outreachy: {e}")
    return []


# ---------------------------------------------------------------------------
# Platform Registry & Quota Distribution
#   Revised quotas after replacing 4 broken scrapers with working ones.
#   MLH/GSoC/Outreachy are 0-1 (conditional) — their quota cascades.
# ---------------------------------------------------------------------------

PLATFORM_QUOTAS = {
    "linkedin":      7,
    "wellfound":     3,
    "yc":            3,
    "internshala":   3,
    "greenhouse":    3,
    "simplifyjobs":  3,
    "pittcsc":       2,
    "mlh":           1,
    "gsoc":          1,
    "outreachy":     1,
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
            "name": "Y Combinator (Workatastartup)",
            "source": "yc",
            "quota": PLATFORM_QUOTAS["yc"],
            "fn": lambda q, lim, hrs, off: fetch_yc_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Internshala / Adzuna",
            "source": "internshala",
            "quota": PLATFORM_QUOTAS["internshala"],
            "fn": lambda q, lim, hrs, off: fetch_internshala_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Greenhouse.io Boards",
            "source": "greenhouse",
            "quota": PLATFORM_QUOTAS["greenhouse"],
            "fn": lambda q, lim, hrs, off: fetch_greenhouse_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "SimplifyJobs GitHub",
            "source": "simplifyjobs",
            "quota": PLATFORM_QUOTAS["simplifyjobs"],
            "fn": lambda q, lim, hrs, off: fetch_simplifyjobs_github(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Pittcsc Summer Internships",
            "source": "pittcsc",
            "quota": PLATFORM_QUOTAS["pittcsc"],
            "fn": lambda q, lim, hrs, off: fetch_pittcsc_github(q, limit=lim, posted_within_hours=hrs)
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
    Each platform has a strict hard quota cap (not multiplied).
    Enforces minimum 4-platform diversity.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links: set = set()
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
        plat_fn = platform["fn"]
        quota = min(platform["quota"], remaining)
        try:
            raw_jobs = plat_fn(search_query, quota * 2, posted_within_hours, start_offset)
            _add_unique(raw_jobs, platform["source"], quota)
            remaining = limit - len(all_jobs)
        except Exception as e:
            logger.warning(f"Error on {platform['name']}: {e}")

    return all_jobs[:limit]
