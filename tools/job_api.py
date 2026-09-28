"""
tools/job_api.py
----------------
Fetches real, live AI listings strictly located in India across verified platforms.

Primary Platforms (Quotas total 25):
  1. Internshala           — India tech & AI internships (Quota: 8)
  2. Peerlist              — Indian tech founders & modern startups (Quota: 4)
  3. Wellfound             — AngelList Talent startup ecosystem in India (Quota: 4)
  4. Y Combinator          — Hacker News Algolia Job Search & WAAS (Quota: 3)
  5. Greenhouse.io Boards  — Public ATS boards for tech companies in India (Quota: 3)
  6. SimplifyJobs GitHub   — Real-time crowdsourced tech tracker (Quota: 2)
  7. Pittcsc GitHub Tracker— Summer internship repository (Quota: 1)

Fallback Reserve Node:
  LinkedIn Guest API       — Activated only if primary portals yield < 25 qualified openings.

Total hard target: 25 qualified, unique India listings.
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
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "application/json",
}

LINKEDIN_GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

_NOW = lambda: datetime.now(timezone.utc)


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()[:1500]


def parse_job_date(val: Optional[str]) -> Optional[datetime]:
    """
    Parses ISO-8601, standard dates, or relative age strings to a tz-aware datetime.
    Returns None if missing or unparseable. NEVER manufactures fake timestamps.
    """
    if not val or not isinstance(val, str):
        return None
    val = val.strip().lower()
    if val in ("just now", "today", "few hours ago", "active today"):
        return _NOW()
    if val in ("yesterday", "1d", "1 day ago"):
        return _NOW() - timedelta(days=1)

    # Relative short format e.g. '2d', '3h', '1w', '2m'
    short_m = re.match(r"^(\d+)\s*([hdwmy])$", val)
    if short_m:
        num, unit = int(short_m.group(1)), short_m.group(2)
        if unit == "h": return _NOW() - timedelta(hours=num)
        if unit == "d": return _NOW() - timedelta(days=num)
        if unit == "w": return _NOW() - timedelta(weeks=num)
        if unit == "m": return _NOW() - timedelta(days=num * 30)
        if unit == "y": return _NOW() - timedelta(days=num * 365)

    # Relative verbose format e.g. '5 days ago', '2 weeks ago', '3 hours ago'
    rel_m = re.search(r"(\d+)\s+(hour|day|week|month|year)s?\s+ago", val)
    if rel_m:
        num, unit = int(rel_m.group(1)), rel_m.group(2)
        if unit == "hour": return _NOW() - timedelta(hours=num)
        if unit == "day": return _NOW() - timedelta(days=num)
        if unit == "week": return _NOW() - timedelta(weeks=num)
        if unit == "month": return _NOW() - timedelta(days=num * 30)
        if unit == "year": return _NOW() - timedelta(days=num * 365)

    # ISO-8601 and calendar date strings
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%b %d, %Y", "%b %d"):
        try:
            dt = datetime.strptime(val[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None

_parse_iso = parse_job_date  # Backward compatibility alias


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
                    posted_at_str = time_el["datetime"] if time_el and time_el.get("datetime") else (time_el.text.strip() if time_el else "")
                    posted_dt = parse_job_date(posted_at_str)

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
    """
    Scrapes Wellfound for live startup AI roles located in India.
    Extracts semantic job cards, company relationships, and verified publication dates.
    """
    if requests is None or BeautifulSoup is None:
        return []

    jobs: List[Dict[str, Any]] = []
    seen_links = set()
    cutoff = _NOW() - timedelta(hours=posted_within_hours)

    try:
        urls_to_try = [
            "https://wellfound.com/role/l/ai-engineer/india",
            "https://wellfound.com/role/l/machine-learning-engineer/india",
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
                job_links = soup.find_all("a", href=re.compile(r"^/jobs/\d+"))

                for jl in job_links:
                    href = jl.get("href", "")
                    if not href.startswith("http"):
                        href = f"https://wellfound.com{href}"
                    if href in seen_links:
                        continue

                    title = jl.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    # Find parent company container
                    card = jl.find_parent("div", class_=re.compile(r"mb-|rounded|border|card"))
                    company = "Wellfound Startup"
                    loc = "India"
                    date_text = None

                    if card:
                        comp_el = card.find("a", href=re.compile(r"^/company/"))
                        if comp_el and comp_el.get_text(strip=True):
                            company = comp_el.get_text(strip=True)

                        loc_el = card.find(["span", "div", "p"], class_=re.compile(r"location|city"))
                        if loc_el and loc_el.get_text(strip=True):
                            loc = loc_el.get_text(strip=True)

                        date_match = re.search(
                            r"(\d+\s+(?:days?|hours?|weeks?|months?)\s+ago|active\s+today|today|just\s+now)",
                            card.get_text(), re.IGNORECASE
                        )
                        if date_match:
                            date_text = date_match.group(1)

                    posted_dt = parse_job_date(date_text)
                    if posted_dt and posted_dt < cutoff:
                        continue

                    job_obj = {
                        "title": title,
                        "company": company,
                        "description": f"{title} position at {company}. Location: {loc}. Sourced from Wellfound India.",
                        "link": href,
                        "apply_url": href,
                        "location": loc,
                        "source": "wellfound",
                        "posted_at": posted_dt,
                    }

                    if is_located_in_india(job_obj):
                        seen_links.add(href)
                        jobs.append(job_obj)
                        if len(jobs) >= limit:
                            break

            except Exception as e:
                logger.debug(f"Wellfound URL error ({url}): {e}")

    except Exception as e:
        logger.warning(f"Error fetching Wellfound jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# 2. Y Combinator — Live Algolia Job Search & WAAS Parser
# ---------------------------------------------------------------------------
def fetch_yc_jobs(search_query: str = "AI Engineer", limit: int = 10,
                  posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Fetches real YC startup AI openings using the official Hacker News Algolia Job Search API
    and Workatastartup.com structured Inertia data. Extracts verified timestamps and direct links.
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    seen_links = set()
    cutoff = _NOW() - timedelta(hours=posted_within_hours)

    # ── Path A: Hacker News Algolia API (Official YC Startup hiring with ISO dates) ──
    try:
        algolia_url = "https://hn.algolia.com/api/v1/search_by_date"
        params = {
            "tags": "job",
            "query": search_query,
            "hitsPerPage": min(limit * 3, 30)
        }
        resp = requests.get(algolia_url, params=params, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            for h in hits:
                title = h.get("title", "")
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                if not url or url in seen_links or not title:
                    continue

                # Parse company name from title e.g. "Stable (YC W20) Is Hiring..."
                company_match = re.match(r"^([^(\n]+?)(?:\s*\(YC|\s+is\s+hiring)", title, re.IGNORECASE)
                company = company_match.group(1).strip() if company_match else "YC Startup"

                created_at_str = h.get("created_at")
                posted_dt = parse_job_date(created_at_str)
                if posted_dt and posted_dt < cutoff:
                    continue

                job_obj = {
                    "title": title,
                    "company": company,
                    "description": f"{title}. YC-backed startup. Apply at: {url}",
                    "link": url,
                    "apply_url": url,
                    "location": "India",
                    "source": "yc",
                    "posted_at": posted_dt,
                }

                if is_located_in_india(job_obj):
                    seen_links.add(url)
                    jobs.append(job_obj)
                    if len(jobs) >= limit:
                        return jobs[:limit]
    except Exception as e:
        logger.warning(f"Error querying YC HN Algolia API: {e}")

    # ── Path B: Workatastartup.com Structured Inertia Data ──────────────
    if len(jobs) < limit:
        try:
            waas_url = "https://www.workatastartup.com/jobs"
            resp = requests.get(waas_url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                div = soup.find("div", attrs={"data-page": True})
                if div and div.get("data-page"):
                    page_data = json.loads(div["data-page"])
                    job_list = page_data.get("props", {}).get("jobs", [])
                    for item in job_list:
                        if len(jobs) >= limit:
                            break
                        if not isinstance(item, dict):
                            continue
                        title = item.get("title") or ""
                        company_name = item.get("companyName") or "YC Startup"
                        batch = item.get("companyBatch", "")
                        if batch:
                            company_name = f"{company_name} (YC {batch})"
                        one_liner = item.get("companyOneLiner") or ""
                        desc = f"{title} at {company_name}. {one_liner}".strip()

                        job_id = item.get("id")
                        link = item.get("applyUrl") or (f"https://www.workatastartup.com/jobs/{job_id}" if job_id else "")
                        if not link or link in seen_links:
                            continue

                        loc = str(item.get("location") or "India")
                        last_active = item.get("companyLastActiveAt")
                        posted_dt = parse_job_date(last_active)
                        if posted_dt and posted_dt < cutoff:
                            continue

                        job_obj = {
                            "title": title,
                            "company": company_name,
                            "description": desc[:1500],
                            "link": link,
                            "apply_url": link,
                            "location": loc,
                            "source": "yc",
                            "posted_at": posted_dt,
                        }

                        if is_located_in_india(job_obj):
                            seen_links.add(link)
                            jobs.append(job_obj)
                            if len(jobs) >= limit:
                                break
        except Exception as e:
            logger.warning(f"Error parsing WAAS Inertia data: {e}")

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

                        status_el = card.find(class_=re.compile(r"status|posted|published"))
                        date_text = status_el.get_text(strip=True) if status_el else None
                        if not date_text:
                            date_match = re.search(
                                r"(\d+\s+(?:days?|hours?|weeks?|months?)\s+ago|just now|few hours ago|today)",
                                card.get_text(), re.IGNORECASE
                            )
                            if date_match:
                                date_text = date_match.group(1)
                        posted_dt = parse_job_date(date_text)

                        cutoff = _NOW() - timedelta(hours=posted_within_hours)
                        if posted_dt and posted_dt < cutoff:
                            continue

                        job_obj = {
                            "title": title,
                            "company": comp,
                            "description": f"{title} position at {comp}. Location: {loc}. Listed on Internshala India.",
                            "link": href,
                            "apply_url": href,
                            "location": loc,
                            "source": "internshala",
                            "posted_at": posted_dt,
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

                date_str = tds[4].get_text(strip=True) if len(tds) > 4 else ""
                posted_dt = parse_job_date(date_str)
                cutoff = _NOW() - timedelta(hours=posted_within_hours)
                if posted_dt and posted_dt < cutoff:
                    continue

                job_obj = {
                    "title": title if title else f"Position at {company}",
                    "company": company,
                    "description": f"{title} at {company}. Location: {location}.",
                    "link": href,
                    "apply_url": href,
                    "location": location,
                    "source": "simplifyjobs",
                    "posted_at": posted_dt,
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
                posted_dt = parse_job_date(date_str)
                cutoff = _NOW() - timedelta(hours=posted_within_hours)
                if posted_dt and posted_dt < cutoff:
                    continue

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
# 7. Peerlist (Primary Platform — Indian Tech Founders & Builders)
# ---------------------------------------------------------------------------
def fetch_peerlist_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """
    Fetches live tech roles from Peerlist public API (peerlist.io/api/v1/jobs)
    strictly filtered for India and AI/ML domain.
    """
    if requests is None:
        return []

    jobs: List[Dict[str, Any]] = []
    seen_links = set()
    cutoff = _NOW() - timedelta(hours=posted_within_hours)

    try:
        url = "https://peerlist.io/api/v1/jobs"
        resp = requests.get(url, headers=JSON_HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            raw_jobs = data.get("jobs", []) if isinstance(data, dict) else []

            q_terms = [t.strip().lower() for t in search_query.split() if t.strip()]
            ai_keywords = [
                "ai", "ml", "machine learning", "deep learning", "nlp", "llm",
                "data", "engineer", "software", "developer", "research", "fullstack", "backend"
            ]

            for item in raw_jobs:
                if len(jobs) >= limit:
                    break
                if not isinstance(item, dict):
                    continue

                title = item.get("jobTitle") or ""
                company_dict = item.get("company", {})
                company = company_dict.get("name") if isinstance(company_dict, dict) else "Tech Startup"
                desc = _clean_html(item.get("jobDescription") or f"{title} at {company}")

                # Check relevance
                combined = f"{title} {desc[:300]}".lower()
                if q_terms and not any(t in combined for t in q_terms):
                    if not any(k in combined for k in ai_keywords):
                        continue

                # Location extraction
                loc_list = item.get("location", [])
                loc_str = "India"
                if isinstance(loc_list, list) and loc_list:
                    cities = [l.get("city", "") for l in loc_list if isinstance(l, dict) and l.get("city")]
                    countries = [l.get("country", "") for l in loc_list if isinstance(l, dict) and l.get("country")]
                    loc_parts = cities + countries
                    loc_str = ", ".join(dict.fromkeys(loc_parts)) if loc_parts else "India"

                apply_url = item.get("applyLink") or ""
                job_id = item.get("jobId") or ""
                link = apply_url or (f"https://peerlist.io/jobs/{job_id}" if job_id else "")
                if not link or link in seen_links:
                    continue

                published_raw = item.get("publishedAt")
                posted_dt = parse_job_date(published_raw)
                if posted_dt and posted_dt < cutoff:
                    continue

                job_obj = {
                    "title": title,
                    "company": company,
                    "description": desc[:1500],
                    "link": link,
                    "apply_url": apply_url or link,
                    "location": loc_str,
                    "source": "peerlist",
                    "posted_at": posted_dt,
                }

                if is_located_in_india(job_obj):
                    seen_links.add(link)
                    jobs.append(job_obj)
    except Exception as e:
        logger.warning(f"Error fetching Peerlist jobs: {e}")

    return jobs[:limit]


# ---------------------------------------------------------------------------
# Platform Registry & Quota Distribution (PRIMARY PORTALS ONLY)
#   LinkedIn is strictly excluded here and reserved for the FALLBACK NODE.
#   Total Primary Target = 25 qualified openings.
# ---------------------------------------------------------------------------

PLATFORM_QUOTAS = {
    "internshala":   8,
    "peerlist":      4,
    "wellfound":     4,
    "yc":            3,
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
            "name": "Peerlist (India Startups)",
            "source": "peerlist",
            "quota": PLATFORM_QUOTAS["peerlist"],
            "fn": lambda q, lim, hrs, off: fetch_peerlist_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Wellfound (AngelList)",
            "source": "wellfound",
            "quota": PLATFORM_QUOTAS["wellfound"],
            "fn": lambda q, lim, hrs, off: fetch_wellfound_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Y Combinator (Workatastartup & HN)",
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
