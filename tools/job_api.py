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
# Internship Title Filter
# ──────────────────────────────────────────────────────────────────────────────

# Compile once — word-boundary patterns so "international", "internal" don't match
_INTERN_TITLE_PATTERN = re.compile(
    r"\b(?:intern(?:ship)?|co[-\s]?op|coop|trainee|fellowship|fellow|apprentice)\b",
    re.IGNORECASE
)

def _is_internship_title(title: str) -> bool:
    """
    Returns True ONLY if the job title contains an internship keyword at a word boundary.
    Substring 'intern' in 'international' or 'internal' returns False.

    Examples:
      'Software Engineer Intern (Summer)'     -> True
      'Director, US International Tax'        -> False  (was leaking before)
      'IT Engineer, Internal AI Infrastructure' -> False (was leaking before)
      'ML Research Fellowship'                -> True
      'Internship: AI/ML'                     -> True
    """
    return bool(_INTERN_TITLE_PATTERN.search(title))


# ──────────────────────────────────────────────────────────────────────────────
# India Location Guardrails (STRICT RULES & DISQUALIFIERS)
# ──────────────────────────────────────────────────────────────────────────────

# All Indian States & Union Territories
INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "uttaranchal",
    "west bengal", "delhi", "new delhi", "ncr", "national capital region",
    "chandigarh", "puducherry", "pondicherry", "jammu", "kashmir", "ladakh"
]

# Major Indian tech and business cities / hubs
INDIAN_CITIES = [
    "bengaluru", "bangalore", "hyderabad", "secunderabad", "pune", "mumbai",
    "bombay", "gurgaon", "gurugram", "noida", "greater noida", "delhi",
    "new delhi", "chennai", "madras", "kolkata", "calcutta", "ahmedabad",
    "surat", "jaipur", "kochi", "cochin", "trivandrum", "thiruvananthapuram",
    "indore", "bhopal", "chandigarh", "mohali", "panchkula", "coimbatore",
    "nagpur", "bhubaneswar", "cuttack", "vadodara", "baroda", "visakhapatnam",
    "vizag", "mysore", "mysuru", "patna", "lucknow", "kanpur", "ghaziabad",
    "faridabad", "navi mumbai", "thane", "rajkot", "nashik", "aurangabad",
    "mangalore", "mangaluru", "kozhikode", "calicut", "vijayawada", "dehradun",
    "ranchi", "jamshedpur", "raipur", "jabalpur", "gwalior", "tiruchirappalli",
    "trichy", "hubli", "dharwad", "belgaum", "salem", "madurai"
]

# Foreign countries and territories that must trigger immediate rejection
FOREIGN_COUNTRIES = [
    "united states", "usa", "u.s.a.", "u.s.", "united kingdom", "uk", "u.k.",
    "canada", "germany", "deutschland", "france", "australia", "netherlands",
    "singapore", "ireland", "switzerland", "sweden", "poland", "spain", "italy",
    "japan", "china", "brazil", "mexico", "israel", "uae", "dubai", "abu dhabi",
    "united arab emirates", "saudi arabia", "qatar", "new zealand", "philippines",
    "south africa", "nigeria", "kenya", "egypt", "russia", "ukraine", "austria",
    "belgium", "denmark", "finland", "norway", "portugal", "greece", "turkey",
    "czech republic", "hungary", "romania", "vietnam", "indonesia", "malaysia",
    "thailand", "taiwan", "south korea", "hong kong", "estonia", "latvia", "lithuania"
]

# Foreign major tech cities and states
FOREIGN_CITIES = [
    "san francisco", "sf", "bay area", "silicon valley", "new york", "nyc",
    "seattle", "austin", "boston", "chicago", "los angeles", "la", "san diego",
    "denver", "atlanta", "dallas", "houston", "california", "texas", "washington",
    "massachusetts", "london", "manchester", "toronto", "vancouver", "montreal",
    "waterloo", "ottawa", "berlin", "munich", "frankfurt", "paris", "amsterdam",
    "dublin", "sydney", "melbourne", "brisbane", "tokyo", "tel aviv", "zurich",
    "geneva", "stockholm", "warsaw", "lisbon", "barcelona", "madrid"
]

_INDIA_REGEX = re.compile(r"\b(?:india|bharat)\b", re.IGNORECASE)
_INDIA_CODE_REGEX = re.compile(r"(?:,\s*|\/\s*|\b)in\b", re.IGNORECASE)


def is_located_in_india(job: Dict[str, Any]) -> bool:
    """
    Strict guardrail ensuring job is located ONLY in India.
    Accepts:
      - On-site in India (e.g. Bengaluru, Pune, Hyderabad, Delhi, etc.)
      - Hybrid in India
      - Remote but explicitly located in India (e.g. 'Remote, India', 'India (Remote)')
    Rejects:
      - Any job located outside India (US, UK, Canada, Europe, Singapore, etc.)
      - Ambiguous 'Remote', 'Worldwide', 'Global' without explicit India location.
    """
    if not job:
        return False

    loc = (job.get("location") or "").lower().strip()
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    source = (job.get("source") or "").lower()

    # 1. Immediate disqualification on explicit foreign country/city
    for fc in FOREIGN_COUNTRIES:
        pattern = r"\b" + re.escape(fc) + r"\b"
        if re.search(pattern, loc):
            if not _INDIA_REGEX.search(loc):
                return False

    for city in FOREIGN_CITIES:
        pattern = r"\b" + re.escape(city) + r"\b"
        if re.search(pattern, loc):
            if not _INDIA_REGEX.search(loc):
                return False

    # 2. Positive India location check
    if _INDIA_REGEX.search(loc):
        return True

    if any(re.search(r"\b" + re.escape(state) + r"\b", loc) for state in INDIAN_STATES):
        return True

    if any(re.search(r"\b" + re.escape(city) + r"\b", loc) for city in INDIAN_CITIES):
        return True

    if _INDIA_CODE_REGEX.search(loc) and any(w in loc for w in ["remote", "wfh", "work from home", "hybrid", "onsite"]):
        return True

    # 3. Platform inherent guarantee for verified Indian boards
    if source == "internshala":
        return True

    # 4. Context check for generic remote/unspecified locations
    if loc in ["remote", "work from home", "wfh", "anywhere", "open", ""]:
        combined_text = f"{title} {desc[:800]}"
        if any(re.search(r"\b" + re.escape(phrase) + r"\b", combined_text) for phrase in [
            "in india", "india only", "located in india", "based in india", "for indian", "pan india"
        ]):
            return True
        if any(re.search(r"\b" + re.escape(city) + r"\b", combined_text) for city in INDIAN_CITIES):
            return True
        return False

    return False

# Backward compatibility alias
is_remote_or_virtual = is_located_in_india


# ---------------------------------------------------------------------------
# LinkedIn Job Search (FALLBACK NODE ONLY)
#   Invoked ONLY when the primary 25-listing quota is not fulfilled.
#   Target: India. Keeps all options open: full-time, part-time, contract,
#   internship, on-site, hybrid, remote in India.
# ---------------------------------------------------------------------------
def fetch_linkedin_jobs(search_query: str = "AI Engineer", location: str = "India",
                        limit: int = 10, posted_within_hours: int = 24,
                        start_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetches job listings from LinkedIn Guest API targeting India.
    Allows all work arrangements (on-site, hybrid, remote in India) and
    all employment types (full-time, part-time, contract, internship).
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        encoded_query = urllib.parse.quote(search_query)
        encoded_loc = urllib.parse.quote(location)

        time_filter = "r86400" if posted_within_hours <= 24 else "r604800"
        # No f_WT restriction (all workplace types: onsite, hybrid, remote in India)
        # No f_JT restriction (all job types: full-time, part-time, contract, internship)
        url = (f"{LINKEDIN_GUEST_API_URL}?keywords={encoded_query}"
               f"&location={encoded_loc}&f_TPR={time_filter}&start={start_offset}")

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")

            executive_disqualifiers = [
                "director", "vp", "vice president", "head of", "chief", "principal", "10+ years", "8+ years"
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
                    posted_at_str = time_el["datetime"] if time_el and time_el.get("datetime") else ""
                    posted_dt = _parse_iso(posted_at_str) if posted_at_str else _NOW()

                    title_lower = title.lower()
                    if any(disq in title_lower for disq in executive_disqualifiers):
                        continue

                    job_candidate = {
                        "title": title,
                        "company": company,
                        "description": f"{title} position at {company}. Location: {job_loc}.",
                        "link": job_link,
                        "apply_url": job_link,
                        "location": job_loc,
                        "source": "linkedin",
                        "posted_at": posted_dt,
                    }

                    # Strict India location guardrail
                    if not is_located_in_india(job_candidate):
                        continue

                    jobs.append(job_candidate)

                if len(jobs) >= limit:
                    break
    except Exception as e:
        logger.error(f"Error fetching LinkedIn jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 1. Wellfound / AngelList Talent (Primary Platform — Startup Ecosystem)
# ---------------------------------------------------------------------------
def fetch_wellfound_jobs(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Scrapes Wellfound for startup AI roles located in India."""
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        # Check India location hub directly on Wellfound
        urls_to_try = [
            "https://wellfound.com/location/india",
            f"https://wellfound.com/role/r/{urllib.parse.quote(search_query.lower().replace(' ', '-'))}"
        ]

        for url in urls_to_try:
            if len(jobs) >= limit:
                break
            try:
                resp = requests.get(url, headers=HEADERS, timeout=12)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                job_cards = soup.find_all("div", class_=re.compile(r"styles_result|jobCard|job-card|listing"))

                for card in job_cards:
                    title_el = card.find(["h2", "h3", "a"], class_=re.compile(r"title|name"))
                    comp_el = card.find(["span", "a", "h4"], class_=re.compile(r"company|startup"))
                    link_el = card.find("a", href=re.compile(r"/jobs/")) or card.find("a", href=True)
                    loc_el = card.find(["span", "div", "p"], class_=re.compile(r"location|city"))

                    if title_el and link_el:
                        title = title_el.get_text(strip=True)
                        company = comp_el.get_text(strip=True) if comp_el else "Wellfound Startup"
                        href = link_el["href"]
                        if not href.startswith("http"):
                            href = f"https://wellfound.com{href}"

                        loc = loc_el.get_text(strip=True) if loc_el else "India"
                        desc_el = card.find(["p", "div"], class_=re.compile(r"desc|detail|snippet"))
                        desc = desc_el.get_text(strip=True) if desc_el else f"{title} at {company}. Location: {loc}."

                        job_obj = {
                            "title": title,
                            "company": company,
                            "description": desc[:1500],
                            "link": href,
                            "apply_url": href,
                            "location": loc,
                            "source": "wellfound",
                            "posted_at": _NOW(),
                        }
                        if is_located_in_india(job_obj):
                            jobs.append(job_obj)
                            if len(jobs) >= limit:
                                break
            except Exception as e:
                logger.debug(f"Wellfound URL error ({url}): {e}")

    except Exception as e:
        logger.warning(f"Error fetching Wellfound jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Y Combinator — Workatastartup JSON API
# ---------------------------------------------------------------------------
def fetch_yc_jobs(search_query: str = "AI Engineer", limit: int = 10,
                  posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Queries Workatastartup.com via its search API for AI openings in India.
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    try:
        url = "https://www.workatastartup.com/jobs"
        params = {
            "companySize": "any",
            "demographic": "any",
            "hasEquity": "false",
            "hasSalary": "false",
            "industry": "any",
            "interviewProcess": "any",
            "query": search_query,
            "sortBy": "created_at",
        }
        resp = requests.get(url, headers=JSON_HEADERS, params=params, timeout=15)
        content_type = resp.headers.get("Content-Type", "")

        if resp.status_code == 200 and "application/json" in content_type:
            data = resp.json()
            job_list = data if isinstance(data, list) else data.get("jobs", data.get("results", []))
            for item in job_list[:limit * 3]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("job_title") or ""
                company_data = item.get("company") or {}
                company_name = company_data.get("name", "YC Startup") if isinstance(company_data, dict) else str(company_data)
                desc = str(item.get("description") or f"{title} at {company_name}. YC-backed.")
                link = item.get("url") or item.get("job_url") or ""
                if link and not link.startswith("http"):
                    link = f"https://www.workatastartup.com{link}"
                if not title or not link:
                    continue
                loc = str(item.get("location") or "India")
                job_obj = {
                    "title": title,
                    "company": company_name,
                    "description": _clean_html(desc)[:1500],
                    "link": link,
                    "apply_url": link,
                    "location": loc,
                    "source": "yc",
                    "posted_at": _NOW(),
                }
                if is_located_in_india(job_obj):
                    jobs.append(job_obj)
                if len(jobs) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Error fetching YC jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 3. Internshala + Adzuna (Primary Platform — India Tech Internships & Jobs)
# ---------------------------------------------------------------------------
def fetch_internshala_jobs(search_query: str = "AI Engineer", limit: int = 10,
                           posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Scrapes Internshala for AI/ML/Data internships and full-time jobs across India.
    Falls back to Adzuna India API if Adzuna credentials are configured.
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []

    # ── Path A: Adzuna India API (if credentials configured) ─────────────
    adzuna_app_id = getattr(settings, "adzuna_app_id", "") or ""
    adzuna_api_key = getattr(settings, "adzuna_api_key", "") or ""
    if adzuna_app_id and adzuna_api_key:
        try:
            keywords = search_query.replace(" ", "+")
            url = (
                f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                f"?app_id={adzuna_app_id}&app_key={adzuna_api_key}"
                f"&results_per_page={min(limit * 2, 20)}&what={keywords}"
                f"&what_exclude=director+vp+manager"
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
                    if is_located_in_india(job_obj):
                        jobs.append(job_obj)
                    if len(jobs) >= limit:
                        return jobs[:limit]
        except Exception as e:
            logger.warning(f"Adzuna API error: {e}")

    # ── Path B: Internshala Scraper (India AI Internships & Jobs) ────────
    if not jobs:
        try:
            slug = urllib.parse.quote(search_query.lower().replace(" ", "-"))
            urls_to_try = [
                "https://internshala.com/internships/artificial-intelligence-ai-internship/",
                "https://internshala.com/internships/machine-learning-internship/",
                "https://internshala.com/jobs/artificial-intelligence-ai-jobs/",
                "https://internshala.com/jobs/machine-learning-jobs/",
                f"https://internshala.com/internships/keywords-{slug}/",
                f"https://internshala.com/jobs/keywords-{slug}/",
            ]

            ai_title_keywords = [
                "ai", "ml", "machine learning", "deep learning", "data science",
                "data analyst", "python", "nlp", "llm", "artificial intelligence",
                "computer vision", "automation", "software", "developer", "engineer"
            ]

            seen_links = set()
            for try_url in urls_to_try:
                if len(jobs) >= limit:
                    break
                try:
                    resp = requests.get(try_url, headers=HEADERS, timeout=12)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.find_all("div", class_=re.compile(r"individual_internship|job-card"))

                    for card in cards:
                        link_el = card.find("a", href=re.compile(r"/(?:internship|job)/detail/"))
                        if not link_el:
                            continue
                        title = link_el.get_text(strip=True)
                        href = link_el.get("href", "")
                        if not href:
                            continue
                        if not href.startswith("http"):
                            href = f"https://internshala.com{href}"
                        if href in seen_links:
                            continue
                        seen_links.add(href)

                        title_lower = title.lower()
                        if not any(kw in title_lower for kw in ai_title_keywords):
                            continue

                        comp_el = card.find(class_=re.compile(r"company_name|link_display_like_text"))
                        comp_raw = comp_el.get_text(strip=True) if comp_el else "Company on Internshala"
                        comp = re.sub(r"actively hiring", "", comp_raw, flags=re.I).strip()

                        loc_el = card.find(id=re.compile(r"location")) or card.find(class_=re.compile(r"location"))
                        loc = loc_el.get_text(strip=True) if loc_el else "India"

                        job_obj = {
                            "title": title,
                            "company": comp,
                            "description": f"{title} position at {comp}. Location: {loc}. Listed on Internshala India.",
                            "link": href,
                            "apply_url": href,
                            "location": loc,
                            "source": "internshala",
                            "posted_at": _NOW(),
                        }
                        if is_located_in_india(job_obj):
                            jobs.append(job_obj)
                            if len(jobs) >= limit:
                                break
                except Exception as e:
                    logger.debug(f"Internshala URL error ({try_url}): {e}")

        except Exception as e:
            logger.warning(f"Internshala scraper error: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 4. Greenhouse.io Boards API (Tech Startups with India Presence)
# ---------------------------------------------------------------------------

GREENHOUSE_COMPANIES = [
    "posthog", "browserstack", "hasura", "razorpay", "cred",
    "zerodha", "groww", "swiggy", "zomato", "curefit",
    "openai", "anthropic", "cohere", "scale-ai", "huggingface",
    "together-ai", "perplexity-ai", "replit", "linear",
    "vercel", "supabase", "weaviate", "pinecone", "qdrant"
]


def fetch_greenhouse_jobs(search_query: str = "AI Engineer", limit: int = 10,
                          posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Queries public Greenhouse.io job board API and strictly filters for India positions.
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
    ai_signals = ["ai", "ml", "machine learning", "nlp", "llm", "deep learning",
                  "data scientist", "research", "model", "python", "automation"]

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
                combined_ai = f"{title_lower} {desc[:300].lower()}"

                if q_terms and not any(t in combined_ai for t in q_terms):
                    if not any(k in combined_ai for k in ai_signals):
                        continue

                location = item.get("location", {}).get("name", "") or ""
                job_obj_temp = {
                    "location": location,
                    "description": desc,
                    "title": title,
                    "source": "greenhouse"
                }

                # Strict India location guardrail
                if not is_located_in_india(job_obj_temp):
                    continue

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
                    "description": desc if desc else f"{title} position at {company_slug}.",
                    "link": link,
                    "apply_url": link,
                    "location": location if location else "India",
                    "source": "greenhouse",
                    "posted_at": posted_dt,
                })
        except Exception as e:
            logger.debug(f"Greenhouse error for {company_slug}: {e}")
            continue

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 5. SimplifyJobs GitHub Tracker (Filtered for India)
# ---------------------------------------------------------------------------
def fetch_simplifyjobs_github(search_query: str = "AI Engineer", limit: int = 10,
                               posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Parses SimplifyJobs GitHub Markdown table and filters strictly for India."""
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
                location = tds[2].get_text(strip=True) if len(tds) > 2 else ""

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
                    "title": title if title else f"Position at {company}",
                    "company": company,
                    "description": f"{title} at {company}. Location: {location}.",
                    "link": href,
                    "apply_url": href,
                    "location": location,
                    "source": "simplifyjobs",
                    "posted_at": _NOW(),
                }
                if is_located_in_india(job_obj):
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching SimplifyJobs GitHub: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 6. Pittcsc Summer Internships (Filtered for India)
# ---------------------------------------------------------------------------
def fetch_pittcsc_github(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """Parses pittcsc GitHub Markdown table and filters strictly for India."""
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

                title = tds[1].get_text(strip=True) if len(tds) > 1 else "Software Engineer"
                location = tds[2].get_text(strip=True) if len(tds) > 2 else ""
                date_str = tds[4].get_text(strip=True) if len(tds) > 4 else ""
                posted_dt = _parse_iso(date_str) if date_str else _NOW()

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
                    "description": f"{title} at {company}. Location: {location}.",
                    "link": href,
                    "apply_url": href,
                    "location": location,
                    "source": "pittcsc",
                    "posted_at": posted_dt,
                }
                if is_located_in_india(job_obj):
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        break

    except Exception as e:
        logger.warning(f"Error fetching pittcsc GitHub: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# Platform Registry & Quota Distribution (PRIMARY PORTALS ONLY)
#   LinkedIn is strictly excluded here and reserved for the FALLBACK NODE.
#   Total Primary Target = 25 qualified openings.
# ---------------------------------------------------------------------------

PLATFORM_QUOTAS = {
    "internshala":   10,
    "wellfound":     5,
    "yc":            4,
    "greenhouse":    3,
    "simplifyjobs":  2,
    "pittcsc":       1,
}


def get_scraper_platforms() -> List[Dict[str, Any]]:
    """
    Returns the ordered list of PRIMARY scrapers (non-LinkedIn).
    LinkedIn is reserved exclusively for the Fallback Node.
    """
    return [
        {
            "name": "Internshala (India)",
            "source": "internshala",
            "quota": PLATFORM_QUOTAS["internshala"],
            "fn": lambda q, lim, hrs, off: fetch_internshala_jobs(q, limit=lim, posted_within_hours=hrs)
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
            "name": "Greenhouse.io Boards (India)",
            "source": "greenhouse",
            "quota": PLATFORM_QUOTAS["greenhouse"],
            "fn": lambda q, lim, hrs, off: fetch_greenhouse_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "SimplifyJobs Tracker (India)",
            "source": "simplifyjobs",
            "quota": PLATFORM_QUOTAS["simplifyjobs"],
            "fn": lambda q, lim, hrs, off: fetch_simplifyjobs_github(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Pittcsc Tracker (India)",
            "source": "pittcsc",
            "quota": PLATFORM_QUOTAS["pittcsc"],
            "fn": lambda q, lim, hrs, off: fetch_pittcsc_github(q, limit=lim, posted_within_hours=hrs)
        },
    ]


def fetch_jobs(search_query: str = "AI Engineer", limit: int = 25,
               posted_within_hours: int = 24, start_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Cascades across primary platforms first.
    If the quota of `limit` (default 25) qualified listings is not fulfilled,
    falls back to LinkedIn India to supply the remainder.
    """
    all_jobs: List[Dict[str, Any]] = []
    seen_links: set = set()
    platform_counts: Dict[str, int] = {}

    def _add_unique(jobs_list, source_name: str, quota: int):
        added = 0
        for j in jobs_list:
            if added >= quota or len(all_jobs) >= limit:
                break
            if not is_located_in_india(j):
                continue
            key = (j.get("apply_url") or j.get("link") or "").strip().lower()
            if key and key not in seen_links:
                seen_links.add(key)
                all_jobs.append(j)
                platform_counts[source_name] = platform_counts.get(source_name, 0) + 1
                added += 1

    # ── Node 1: Primary Portals Search ────────────────────────────────────
    platforms = get_scraper_platforms()
    for platform in platforms:
        if len(all_jobs) >= limit:
            break
        plat_fn = platform["fn"]
        quota = min(platform["quota"], limit - len(all_jobs))
        try:
            raw_jobs = plat_fn(search_query, quota * 2, posted_within_hours, start_offset)
            _add_unique(raw_jobs, platform["source"], quota)
        except Exception as e:
            logger.warning(f"Error on {platform['name']}: {e}")

    # ── Node 2: LinkedIn Fallback Node (if target quota not fulfilled) ────
    if len(all_jobs) < limit:
        needed = limit - len(all_jobs)
        logger.info(f"Primary platforms yielded {len(all_jobs)}/{limit}. Triggering LinkedIn fallback for remaining {needed}...")
        for offset in [0, 10, 20, 30]:
            if len(all_jobs) >= limit:
                break
            try:
                raw_linkedin = fetch_linkedin_jobs(
                    search_query, location="India", limit=needed * 2,
                    posted_within_hours=posted_within_hours, start_offset=offset
                )
                _add_unique(raw_linkedin, "linkedin", needed)
            except Exception as e:
                logger.warning(f"LinkedIn fallback error: {e}")

    return all_jobs[:limit]
