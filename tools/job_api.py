"""
tools/job_api.py
----------------
Fetches real, live AI listings strictly located in India across the portals listed in
internship_sources_autonomous_agent.csv, in that file's order.

Main portals (get_scraper_platforms, CSV "Main" rows):
  Y Combinator, Startup Jobs, Web Search, Wellfound, Cutshort, LinkedIn, Instahyre,
  Hirist, Naukri.

Fallback portals (get_fallback_platforms, CSV "Fallback" rows, only when still under
target): Hacker News Who is Hiring, Remote OK, Remotive, Himalayas, We Work Remotely,
Built In, Welcome to the Jungle, Underdog.io, NoDesk, Remote Rocketship, InternDoor,
Jobsii, Greenhouse, Lever, Ashby, Workable, Direct Startup Career Pages.

Each fetcher uses the method that actually works for that platform (public API, RSS/JSON
feed, server-rendered page payload, or JSON-LD) and returns [] — never fabricated jobs —
when a platform walls its data behind logins or captchas.
Total hard target: 25 qualified, unique India listings.
"""

import html
import json
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from config.settings import settings

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

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
    """Strip HTML tags, unescape entities (&#x27; etc.), collapse whitespace."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()[:1500]


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

    # ISO-8601 and calendar date strings. No yearless "%b %d": it would
    # manufacture a year-1900 timestamp (never fabricate) and is deprecated
    # in Python 3.15 — such inputs now honestly fall through to None.
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%b %d, %Y"):
        try:
            dt = datetime.strptime(val[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # ISO-8601 without zone markers, e.g. '2026-09-22t06:13:05.896001'
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # RFC 822 (RSS pubDate) e.g. 'mon, 12 oct 2026 03:02:30 +0000'
    try:
        dt = parsedate_to_datetime(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None

_parse_iso = parse_job_date  # Backward compatibility alias


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


def _india_place_from_text(text: str) -> str:
    """
    Returns the first Indian country / state / city mentioned in `text`,
    or an empty string when none is found.

    Used to derive a location from source text that has no structured
    location field (e.g. Hacker News job titles). Only real, platform-
    provided text is inspected — nothing is invented.
    """
    if not text:
        return ""
    m = _INDIA_REGEX.search(text)
    if m:
        return m.group(0)
    for state in INDIAN_STATES:
        if re.search(r"\b" + re.escape(state) + r"\b", text, re.IGNORECASE):
            return state
    for city in INDIAN_CITIES:
        if re.search(r"\b" + re.escape(city) + r"\b", text, re.IGNORECASE):
            return city
    return ""


def is_located_in_india(job: Dict[str, Any]) -> bool:
    """
    Strict guardrail ensuring job is located in India.

    Evidence rules (no shortcuts — the product promise is "verified India"):
      - ACCEPT: the job's location FIELD names an Indian place
        (e.g. 'Bengaluru', 'Pune, India', 'Remote, India', 'India (Remote)').
      - ACCEPT: location field is empty or generic ('', 'Remote', 'WFH',
        'Anywhere') but the job TITLE explicitly names an Indian place
        (e.g. 'AI Intern — Bangalore (Remote)'). Titles are real data
        extracted from the listing on every platform.
      - REJECT: anything else — including unknown locations. A missing
        location is NOT evidence of India.
      - Job DESCRIPTIONS are never used as evidence because several
        scrapers build synthetic description text (see job_api docstrings).

    Rejects:
      - Any job located outside India (US, UK, Canada, Europe, Singapore, etc.)
      - Ambiguous 'Remote', 'Worldwide', 'Global' without explicit India evidence.
    """
    if not job:
        return False

    loc = (job.get("location") or "").lower().strip()
    title = (job.get("title") or "").lower()

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

    # 3. Empty / generic location: only the TITLE can prove India.
    #    (Removed a former source-name bypass — platform name is not location
    #     evidence. Removed the description scan — several scrapers build
    #     synthetic description text.)
    if loc in ["remote", "work from home", "wfh", "anywhere", "open", ""]:
        return bool(_india_place_from_text(title))

    return False

# Backward compatibility alias
is_remote_or_virtual = is_located_in_india


# ---------------------------------------------------------------------------
# Role guardrails (spec: internships only, in the targeted AI families only)
# ---------------------------------------------------------------------------
# Internship declared in the listing TITLE. Word boundaries are mandatory:
# "international" and "internal" must never match.
_INTERNSHIP_TITLE_PATTERN = re.compile(
    r"\b(?:intern(?:ship|ships|s)?|co[\s-]?op|trainee|apprentic(?:e|eship)"
    r"|fellow(?:ship|ships)?|student)\b",
    re.IGNORECASE,
)

# Targeted AI families: AI Automation, AI Engineer, GenAI Developer,
# AI Generalist, AI Consultant — plus the standard titles they ship under
# (LLM / ML / NLP / computer vision / agentic agents).
_AI_ROLE_PATTERN = re.compile(
    r"\bai\b|\bartificial intelligence\b|\bgen[\s-]?ai\b|\bgenerative ai\b"
    r"|\bllms?\b|\blarge language models?\b|\bmachine learning\b|\bml\b"
    r"|\bdeep learning\b|\bnlp\b|\bcomputer vision\b|\bprompt engineer"
    r"|\bagentic\b|\bai agents?\b|\bneural networks?\b",
    re.IGNORECASE,
)

# Generic technical titles: only acceptable when the body proves AI context.
_GENERIC_TECH_TITLE_PATTERN = re.compile(
    r"\b(?:engineer|developer|generalist|consultant|researcher|scientist"
    r"|architect|intern|student)\b",
    re.IGNORECASE,
)


def is_internship_title(title: str) -> bool:
    """
    True only when the title itself declares an internship (or equivalent:
    co-op, trainee, apprenticeship, fellowship). Full-time roles are rejected
    even when their description mentions interns — the product delivers
    internships exclusively.
    """
    return bool(title) and bool(_INTERNSHIP_TITLE_PATTERN.search(title))


def is_ai_role(title: str, description: str = "") -> bool:
    """
    True when the listing belongs to the targeted AI families.

    Evidence rules (specificity is the requirement):
      - ACCEPT: an AI term appears in the TITLE ('AI Engineer Intern',
        'GenAI Developer', 'AI Automation Trainee', 'ML Intern').
      - ACCEPT: a generic technical title (Engineer, Developer, Generalist,
        Consultant, Intern, ...) whose DESCRIPTION proves AI context
        ('Build LLM agents...', 'production machine learning pipelines').
      - REJECT: everything else. 'ai' as a substring ('detail', 'maintain',
        'retail') never matches — the pattern is word-bounded.
    """
    title = title or ""
    if _AI_ROLE_PATTERN.search(title):
        return True
    return bool(_GENERIC_TECH_TITLE_PATTERN.search(title)) and bool(
        _AI_ROLE_PATTERN.search(description or "")
    )


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
                    # No fallback to the search location — a missing element
                    # means unknown, and unknown is not India evidence.
                    job_loc = loc_el.text.strip() if loc_el else ""
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
# CSV row 4 "Web Search" — browser-grade search (Main pass, position 3)
# ---------------------------------------------------------------------------
def _websearch_provider_links(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Organic results from the configured search API; first provider wins:
      1. Google Programmable Search JSON API (settings.google_cse_api_key +
         settings.google_cse_cx) — official Google search, free tier.
      2. Brave Search API (settings.brave_search_api_key) — free tier.
    Keyless engines (Bing RSS/HTML, Google/DDG HTML, Mojeek, SearXNG, ...)
    are bot-walled or serve decoy results — verified live — so they are not
    used. Returns [{"url", "title"}...]; [] when no key or all providers fail.
    """
    if settings.google_cse_api_key and settings.google_cse_cx:
        data = _get_json("https://www.googleapis.com/customsearch/v1", params={
            "key": settings.google_cse_api_key,
            "cx": settings.google_cse_cx,
            "q": query,
            "num": min(max(limit, 1), 10),
        })
        items = (data or {}).get("items") or []
        if items:
            return [{"url": it.get("link", ""), "title": it.get("title", "")}
                    for it in items if it.get("link")]
    if settings.brave_search_api_key:
        data = _get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(max(limit, 1), 20),
                    "search_lang": "en", "country": "in"},
            headers={"X-Subscription-Token": settings.brave_search_api_key,
                     "Accept": "application/json", "Accept-Encoding": "gzip"},
        )
        results = ((data or {}).get("web") or {}).get("results") or []
        if results:
            return [{"url": it.get("url", ""), "title": it.get("title", "")}
                    for it in results if it.get("url")]
    return []


def fetch_websearch_jobs(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """
    CSV 'Web Search' (Main pass, position 3): real web search — Google
    Programmable Search first, Brave Search API as fallback. Every result page
    is opened, and kept ONLY when it exposes a real JobPosting JSON-LD block:
    each delivered listing is a genuine posting at its canonical URL; search
    snippets are never trusted as listings. The pipeline's own gates
    (internship-only, AI-family, India, date window) still apply.

    shortcut: with neither key configured (or on provider failure) the portal
    returns [] and logs once — it cannot discover anything by itself, by design.
    """
    key = "websearch"
    if _recently_empty(key):
        return []
    results = _websearch_provider_links(f"{search_query} internship India",
                                        limit=max(limit, 10))
    if not results:
        if not (settings.google_cse_api_key or settings.brave_search_api_key):
            logger.warning(
                "websearch: no search API key configured — set GOOGLE_CSE_API_KEY + "
                "GOOGLE_CSE_CX (Google Programmable Search) or BRAVE_SEARCH_API_KEY "
                "(Brave Search) to enable the Web Search portal.")
        _mark_empty(key)
        return []
    jobs: List[Dict[str, Any]] = []
    seen: set = set()
    for item in results:
        if len(jobs) >= limit:
            break
        link = (item.get("url") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        page = _get_text(link)
        if not page:
            continue
        block = _parse_jsonld_job(page)
        if not block or not block.get("title"):
            continue  # no structured JobPosting on the page — skip, never fabricate
        org = block.get("hiringOrganization") or {}
        loc = block.get("jobLocation") or {}
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            location = ", ".join(
                str(addr.get(k, "")) for k in ("addressLocality", "addressCountry")
                if isinstance(addr, dict) and addr.get(k)
            )
        else:
            location = str(loc)
        jobs.append({
            "title": block["title"],
            "company": org.get("name") if isinstance(org, dict) else str(org or ""),
            "description": _clean_html(block.get("description") or "")[:1500],
            "link": link, "apply_url": link, "location": location,
            "source": "websearch",
            # date window is enforced pipeline-side by passes_date_gate()
            "posted_at": parse_job_date(block.get("datePosted")),
        })
    return jobs


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
                    loc = ""  # unknown until the card actually shows one — never assume India
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

                # HN job posts carry no structured location. Derive one from
                # the real title text only; empty means unknown → guardrail
                # drops it unless the title names an Indian place.
                job_obj = {
                    "title": title,
                    "company": company,
                    "description": f"{title}. YC-backed startup. Apply at: {url}",
                    "link": url,
                    "apply_url": url,
                    "location": _india_place_from_text(title),
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

                        loc = str(item.get("location") or "")
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
# 3. CSV portal fetchers — see internship_sources_autonomous_agent.csv
#    Each portal uses the method that actually works for that platform:
#    public JSON API, RSS/JSON feed, server-rendered Next.js payload, or
#    structured JSON-LD. Fetchers never raise; failures log and return [].
# ---------------------------------------------------------------------------

# Browser-grade headers for edges that challenge plain server headers (e.g. WTTJ).
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# url -> monotonic ts of the last challenge/empty hit; avoids re-hitting walled pages.
_NEGATIVE_CACHE: Dict[str, float] = {}


def _recently_empty(key: str, ttl_secs: int = 1800) -> bool:
    ts = _NEGATIVE_CACHE.get(key)
    return ts is not None and (time.monotonic() - ts) < ttl_secs


def _mark_empty(key: str) -> None:
    _NEGATIVE_CACHE[key] = time.monotonic()


def _get_json(url: str, params: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None, timeout: int = 12) -> Any:
    """GET a URL and return parsed JSON, or None on any failure. Shared test seam."""
    if requests is None:
        return None
    try:
        resp = requests.get(url, params=params, headers=headers or JSON_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.debug(f"{url} -> HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"JSON fetch failed for {url}: {e}")
    return None


def _get_text(url: str, params: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Optional[str]:
    """GET a URL and return its text, or None on any failure. Shared test seam."""
    if requests is None:
        return None
    try:
        resp = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"{url} -> HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"HTML fetch failed for {url}: {e}")
    return None


def _query_terms(search_query: str) -> List[str]:
    """Lowercased word tokens for free-text boards that lack server-side search."""
    return [t for t in re.findall(r"[a-z0-9]+", search_query.lower()) if len(t) > 1]


def _matches_query(text: str, terms: List[str]) -> bool:
    if not terms:
        return True
    hay = text.lower()
    # Word-start match: term "ai" must not hit "detail"/"maintain"/"email".
    return any(re.search(r"\b" + re.escape(t), hay) for t in terms)


def _split_title_company(title: str) -> tuple:
    """'Senior Dev at Acme (Bengaluru)' -> ('Senior Dev', 'Acme', 'Bengaluru')."""
    location = ""
    paren = re.search(r"\s*\(([^()]+)\)\s*$", title)
    if paren:
        location = paren.group(1).strip()
        title = title[: paren.start()].strip()
    company = ""
    at = re.search(r"^(.*?)\s+at\s+(.+)$", title, re.I)
    if at:
        title, company = at.group(1).strip(), at.group(2).strip()
    return title, company, location


def _parse_rss_items(xml_text: str) -> List[Dict[str, str]]:
    """Parse an RSS <channel> into title/link/description/pubDate dicts (CDATA-safe)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for node in root.iter("item"):
        def field(tag: str) -> str:
            el = node.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        items.append({"title": field("title"), "link": field("link"),
                      "description": field("description"), "pubDate": field("pubDate")})
    return items


def _next_data_jobs(html_text: str) -> List[Dict[str, Any]]:
    """Extract the job array from a Next.js page's __NEXT_DATA__ (Cutshort uses the
    react-query dehydrated state; other pages may nest it under pageProps)."""
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    try:
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        for q in queries:
            page_data = q.get("state", {}).get("data", {}).get("data", {}).get("pageData", {})
            if isinstance(page_data.get("jobs"), list) and page_data["jobs"]:
                return page_data["jobs"]
    except (KeyError, TypeError, AttributeError):
        pass
    return []


def fetch_startupjobs_jobs(search_query: str = "AI Engineer", limit: int = 10,
                           posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Startup Jobs': official keyless RSS feed (50 recent jobs / 14 days).

    shortcut: the RSS feed has no free-text query, so relevance is token-filtered
    client-side; upgrade to the key-bearing REST API (api.startup.jobs/v1/jobs)."""
    xml = _get_text("https://startup.jobs/feeds/jobs")
    if not xml:
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in _parse_rss_items(xml):
        if len(jobs) >= limit:
            break
        if not _matches_query(f"{item['title']} {item['description']}", terms):
            continue
        title, company, _ = _split_title_company(item["title"])
        desc = _clean_html(item["description"])[:1500]
        jobs.append({
            "title": title or item["title"],
            "company": company,
            "description": desc,
            "link": item["link"],
            "apply_url": item["link"],
            # Feed description is platform-authored listing text (not synthetic),
            # so an Indian place named there is real location evidence.
            "location": (_india_place_from_text(desc) or "").title(),
            "source": "startupjobs",
            "posted_at": parse_job_date(item["pubDate"]),
        })
    return jobs


def _cutshort_category_slug(search_query: str) -> str:
    """Pick a live Cutshort category slug for the query from the /jobs tiles."""
    global _CUTSHORT_TILES
    if _CUTSHORT_TILES is None:
        _CUTSHORT_TILES = []
        page = _get_text("https://cutshort.io/jobs")
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', page or "", re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
                page_data = queries[0]["state"]["data"]["data"]["pageData"]
                tiles = (page_data.get("topJobsList") or []) + (page_data.get("jobsList") or [])
                _CUTSHORT_TILES = [t.get("slug", "") for t in tiles if isinstance(t, dict) and t.get("slug")]
            except (KeyError, IndexError, TypeError, ValueError):
                pass
    terms = _query_terms(search_query)
    for slug in _CUTSHORT_TILES:
        if any(t in slug for t in terms):
            return slug
    return _CUTSHORT_FALLBACK_CATEGORY


_CUTSHORT_TILES: Optional[List[str]] = None
_CUTSHORT_FALLBACK_CATEGORY = "remote-machine-learning-ml-jobs"


def fetch_cutshort_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Cutshort': no public job API — parse the Next.js __NEXT_DATA__ payload of a
    category page (the same backend JSON the site itself renders from, no CSS guesswork)."""
    slug = _cutshort_category_slug(search_query)
    page = _get_text(f"https://cutshort.io/jobs/{slug}")
    if not page:
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in _next_data_jobs(page):
        if len(jobs) >= limit:
            break
        title = item.get("headline") or ""
        company = ((item.get("companyDetails") or {}).get("name")
                   or (item.get("companyId") or {}).get("name") or "")
        location = item.get("locationsText") or ""
        if not _matches_query(f"{title} {company} {' '.join(item.get('allSkills') or [])}", terms):
            continue
        link = item.get("publicUrl") or ""
        if not link:
            continue
        desc = _clean_html(item.get("sanitizedComment") or "")[:1500]
        jobs.append({
            "title": title,
            "company": company,
            "description": desc or f"{title} at {company} (Cutshort listing; full description loads from the link).",
            "link": link,
            "apply_url": item.get("authApplyUrl") or link,
            "location": location,
            "source": "cutshort",
            "posted_at": None,  # Cutshort listing payload carries no date field
        })
    return jobs


def fetch_instahyre_jobs(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Instahyre': the site's own public search endpoint (GET /api/v1/job_search/),
    which its frontend calls without auth — approved access, no aggressive scraping."""
    data = _get_json("https://www.instahyre.com/api/v1/job_search/",
                     params={"job_title": search_query},
                     headers={**JSON_HEADERS,
                              "Referer": "https://www.instahyre.com/search-jobs/"})
    objects = (data or {}).get("objects") or []
    jobs: List[Dict[str, Any]] = []
    for item in objects[: limit * 2]:
        title = item.get("title") or ""
        company = (item.get("employer") or {}).get("company_name") or ""
        keywords = item.get("keywords") or []
        link = item.get("public_url") or ""
        if not title or not link:
            continue
        jobs.append({
            "title": title,
            "company": company,
            "description": f"{title} at {company}. Skills: {', '.join(keywords)}.",
            "link": link,
            "apply_url": link,
            "location": item.get("locations") or "",
            "source": "instahyre",
            "posted_at": None,  # search payload carries no date field
        })
        if len(jobs) >= limit:
            break
    return jobs


def fetch_hirist_jobs(search_query: str = "AI Engineer", limit: int = 10,
                      posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Hirist': public search pages render with an empty, captcha-gated job feed and
    api.hirist.tech answers 401 without a recruiter key (both verified). Attempt the public
    search page and return whatever feed it exposes; [] when gated — never fabricated.
    shortcut: no public candidate API; upgrade to api.hirist.tech with a key if issued."""
    if _recently_empty("hirist"):
        return []
    page = _get_text(f"https://www.hirist.tech/search/filter/{urllib.parse.quote(search_query.lower())}.html")
    if not page:
        _mark_empty("hirist")
        return []
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    feed: List[Dict[str, Any]] = []
    if m:
        try:
            data = json.loads(m.group(1))
            job_state = data["props"]["pageProps"]["initialState"]["job"]
            feed = job_state.get("jobfeed") or []
        except (KeyError, TypeError, ValueError):
            feed = []
    if not feed:
        _mark_empty("hirist")  # feed is captcha-gated server-side; don't refetch every query
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in feed[: limit * 2]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("jobTitle") or ""
        company = item.get("company") or (item.get("companyDetails") or {}).get("name") or ""
        location = item.get("location") or item.get("locationsText") or ""
        if not title or not _matches_query(f"{title} {company}", terms):
            continue
        link = item.get("link") or item.get("publicUrl") or f"https://www.hirist.tech/jobs/{item.get('id', '')}"
        jobs.append({
            "title": title, "company": company,
            "description": _clean_html(item.get("description") or "")[:1500] or f"{title} at {company} (Hirist listing).",
            "link": link, "apply_url": link, "location": location,
            "source": "hirist",
            "posted_at": parse_job_date(item.get("publishedAt") or item.get("postedAt")),
        })
        if len(jobs) >= limit:
            break
    return jobs


def fetch_naukri_jobs(search_query: str = "AI Engineer", limit: int = 10,
                      posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Naukri': their search API is reCAPTCHA-walled for automation (v3 -> 406
    'recaptcha required'; v2 answers an empty list from datacenter IPs — both verified).
    Attempt the lightest public endpoint and translate whatever it returns; [] when
    challenged rather than pretending to scrape.
    shortcut: captcha-walled; upgrade on approved/partner API access."""
    if _recently_empty("naukri"):
        return []
    data = _get_json(
        "https://www.naukri.com/jobapi/v2/search",
        params={"noOfResults": min(limit * 2, 20), "keyword": search_query,
                "experience": 0, "pageNo": 1, "urlType": "by_keyword",
                "seoKey": f"{search_query.lower().replace(' ', '-')}-jobs"},
        headers={**JSON_HEADERS, "appid": "109", "systemid": "109",
                 "Referer": "https://www.naukri.com/"},
    )
    items = (data or {}).get("list") or (data or {}).get("jobDetails") or []
    if not items:
        _mark_empty("naukri")  # recaptcha wall / empty answer — do not hammer per query
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in items:
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        company = item.get("companyName") or (item.get("company") or {}).get("name") or ""
        location = item.get("jobLocation") or (item.get("location") or {}).get("name") or ""
        link = item.get("url") or item.get("jobUrl") or ""
        if not title or not _matches_query(f"{title} {company}", terms):
            continue
        if not link:
            link = f"https://www.naukri.com/jobdetails/{item.get('jobId', '')}"
        jobs.append({
            "title": title, "company": company,
            "description": _clean_html(item.get("jobDescription") or item.get("description") or "")[:1500]
                           or f"{title} at {company} (Naukri listing).",
            "link": link, "apply_url": link, "location": location,
            "source": "naukri",
            "posted_at": parse_job_date(item.get("postedDate") or item.get("lastDate")),
        })
    return jobs


def fetch_hn_jobs(search_query: str = "AI Engineer", limit: int = 10,
                  posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Hacker News – Who is Hiring': public Algolia HN API — locate the current
    'Ask HN: Who is hiring' thread, then pull its most recent comments (two-step)."""
    stories = _get_json("https://hn.algolia.com/api/v1/search_by_date",
                        params={"query": '"who is hiring"', "tags": "story", "hitsPerPage": 8})
    thread_id = None
    for hit in (stories or {}).get("hits", []):
        if re.search(r"who is hiring", hit.get("title") or "", re.I):
            thread_id = hit.get("objectID")
            break
    if not thread_id:
        return []
    comments = _get_json("https://hn.algolia.com/api/v1/search_by_date",
                         params={"tags": f"comment,story_{thread_id}", "hitsPerPage": min(limit * 4, 60)})
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for hit in (comments or {}).get("hits", []):
        if len(jobs) >= limit:
            break
        raw = hit.get("comment_text") or ""
        text = _clean_html(raw)[:1500]
        if not text or not _matches_query(text, terms):
            continue
        # 'Who is hiring' comments are pipe-delimited or one paragraph per
        # field (company / role / location) — split on paragraphs first so a
        # marketing first line doesn't become the company name.
        blocks = [b for b in re.split(r"</p>|<br\s*/?>", raw, flags=re.I) if b.strip()]
        first = _clean_html(blocks[0]) if blocks else text[:80]
        if "|" in first:
            parts = [p.strip() for p in first.split("|")]
        elif len(blocks) >= 2:
            parts = [_clean_html(b) for b in blocks[:3]]
        else:
            parts = ["", first]  # one-line comment: role text only, no company evidence
        company = parts[0][:80]
        title = parts[1][:120] if len(parts) > 1 and parts[1] else text[:60]
        location = parts[2][:80] if len(parts) > 2 and parts[2] else ""
        apply_m = re.search(r"https?://[^\s\"'<>]+", raw)
        permalink = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        jobs.append({
            "title": title[:120], "company": company[:80],
            "description": text,
            "link": apply_m.group(0) if apply_m else permalink,
            "apply_url": apply_m.group(0) if apply_m else permalink,
            "location": location,
            "source": "hn",
            "posted_at": parse_job_date(hit.get("created_at")),
        })
    return jobs


def fetch_remoteok_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Remote OK': official public JSON API (remoteok.com/api)."""
    data = _get_json("https://remoteok.com/api")
    if not isinstance(data, list):
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in data:
        if len(jobs) >= limit:
            break
        if not isinstance(item, dict) or not item.get("position"):
            continue  # first element is the API's legal notice
        title = item.get("position") or ""
        if not _matches_query(f"{title} {item.get('company', '')} {' '.join(item.get('tags') or [])}", terms):
            continue
        link = item.get("url") or ""
        if not link:
            continue
        jobs.append({
            "title": title,
            "company": item.get("company") or "",
            "description": _clean_html(item.get("description") or "")[:1500] or f"{title} (Remote OK listing).",
            "link": link, "apply_url": link,
            "location": item.get("location") or "",
            "source": "remoteok",
            "posted_at": parse_job_date(item.get("date")),
        })
    return jobs


def fetch_remotive_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Remotive': official public JSON API with server-side search."""
    data = _get_json("https://remotive.com/api/remote-jobs",
                     params={"search": search_query, "limit": max(limit * 2, 20)})
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("jobs", [])[: limit * 2]:
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        job_id = item.get("id")
        apply_url = item.get("url") or ""
        link = f"https://remotive.com/remote-jobs/{job_id}" if job_id else apply_url
        if not title or not (link or apply_url):
            continue
        jobs.append({
            "title": title,
            "company": item.get("company_name") or "",
            "description": _clean_html(item.get("description") or "")[:1500],
            "link": link or apply_url, "apply_url": apply_url or link,
            "location": item.get("candidate_required_location") or "",
            "source": "remotive",
            "posted_at": parse_job_date(item.get("publication_date")),
        })
    return jobs


def fetch_himalayas_jobs(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Himalayas': official free public JSON API (himalayas.app/jobs/api/search)."""
    data = _get_json("https://himalayas.app/jobs/api/search",
                     params={"q": search_query, "limit": min(max(limit, 10), 20), "sort": "recent"})
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("jobs", []):
        if len(jobs) >= limit:
            break
        raw_loc = item.get("locationRestrictions") or []
        location = ", ".join(
            (l.get("name", "") if isinstance(l, dict) else str(l)) for l in raw_loc
        )
        posted = item.get("pubDate")
        if isinstance(posted, (int, float)):
            posted = datetime.fromtimestamp(posted / 1000 if posted > 10_000_000_000 else posted,
                                            tz=timezone.utc)
        link = item.get("guid") or item.get("applicationLink") or ""
        if not link:
            continue
        jobs.append({
            "title": item.get("title") or "",
            "company": item.get("companyName") or "",
            "description": _clean_html(item.get("description") or item.get("excerpt") or "")[:1500],
            "link": link, "apply_url": item.get("applicationLink") or link,
            "location": location,
            "source": "himalayas",
            "posted_at": posted,
        })
    return jobs


def fetch_wwr_jobs(search_query: str = "AI Engineer", limit: int = 10,
                   posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'We Work Remotely': official RSS feed for the programming category."""
    xml = _get_text("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    if not xml:
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in _parse_rss_items(xml):
        if len(jobs) >= limit:
            break
        if not _matches_query(f"{item['title']} {item['description']}", terms):
            continue
        raw_title = item["title"].strip()
        wwr_company = ""
        # WWR RSS titles are 'Company: Role' — split on the first colon when
        # there is no ' at ' separator for the shared helper to find.
        if ":" in raw_title and " at " not in raw_title.lower():
            wwr_company, _, rest = raw_title.partition(":")
            wwr_company, raw_title = wwr_company.strip(), rest.strip()
        title, company, location = _split_title_company(raw_title)
        company = company or wwr_company
        jobs.append({
            "title": title, "company": company,
            "description": _clean_html(item["description"])[:1500],
            "link": item["link"], "apply_url": item["link"],
            "location": location,
            "source": "wwr",
            "posted_at": parse_job_date(item["pubDate"]),
        })
    return jobs


def fetch_builtin_jobs(search_query: str = "AI Engineer", limit: int = 10,
                       posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Built In': server-rendered search page; parse job cards (href=/job/{slug}/{id}).
    Detects Cloudflare interstitials and backs off instead of refetching every query."""
    key = "builtin"
    if _recently_empty(key):
        return []
    page = _get_text("https://builtin.com/jobs/search", params={"keywords": search_query})
    if not page or "/job/" not in page:
        _mark_empty(key)  # challenge page or no cards — back off for this run
        return []
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(page, "html.parser")
    for anchor in soup.find_all("a", href=re.compile(r"^/job/")):
        if len(jobs) >= limit:
            break
        href = anchor.get("href") or ""
        title = anchor.get_text(" ", strip=True)
        if not title or "/jobs/search" in href:
            continue
        card = anchor.find_parent(class_=re.compile(r"node|card|views|result|listing", re.I))
        card_text = card.get_text(" ", strip=True) if card else ""
        if not _matches_query(f"{title} {card_text}", terms):
            continue
        link = f"https://builtin.com{href}"
        jobs.append({
            "title": title,
            "company": "",  # company lives in the card markup; enrichment loads it from the link
            "description": (card_text or title)[:1500],
            "link": link, "apply_url": link,
            "location": (_india_place_from_text(card_text) or "").title(),
            "source": "builtin",
            "posted_at": None,
        })
    if not jobs:
        _mark_empty(key)
    return jobs


def fetch_wttj_jobs(search_query: str = "AI Engineer", limit: int = 10,
                    posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Welcome to the Jungle': only the search shell is server-rendered (results
    arrive client-side) and bots get a challenge page — verified both ways. Attempt with
    browser-grade headers, parse job links/JSON-LD when present, else [].
    shortcut: results are client-rendered; upgrade to their official Jobs API when
    partner access exists."""
    key = "wttj"
    if _recently_empty(key):
        return []
    page = _get_text("https://www.welcometothejungle.com/en/jobs",
                     params={"query": search_query}, headers=_BROWSER_HEADERS)
    if not page:
        _mark_empty(key)
        return []
    jobs: List[Dict[str, Any]] = []
    # Structured JSON-LD first (works when the edge serves real results).
    for raw in re.findall(r'<script[^>]*type=["\']?application/ld\+json["\']?[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        blocks = data if isinstance(data, list) else [data]
        for block in blocks:
            if not isinstance(block, dict) or block.get("@type") != "JobPosting":
                continue
            link = block.get("url") or ""
            if not link:
                continue
            org = block.get("hiringOrganization") or {}
            loc = block.get("jobLocation") or {}
            if isinstance(loc, dict):
                addr = loc.get("address") or {}
                location = ", ".join(str(addr.get(k, "")) for k in ("addressLocality", "addressCountry") if addr.get(k))
            else:
                location = str(loc)
            jobs.append({
                "title": block.get("title") or "",
                "company": org.get("name") if isinstance(org, dict) else str(org),
                "description": _clean_html(block.get("description") or "")[:1500],
                "link": link, "apply_url": link, "location": location,
                "source": "wttj",
                "posted_at": parse_job_date(block.get("datePosted")),
            })
            if len(jobs) >= limit:
                break
    if not jobs and "/job" not in page:
        _mark_empty(key)  # shell/challenge only — don't refetch per query
    return jobs[:limit]


def fetch_underdog_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Underdog.io': public search endpoint their landing page itself calls
    (jobs-api.underdog.io/api/jobs/search, GET)."""
    data = _get_json("https://jobs-api.underdog.io/api/jobs/search",
                     params={"q": search_query})
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("objJobs", []):
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        cities = item.get("objCities") or []
        location = ", ".join((c.get("name", "") if isinstance(c, dict) else str(c)) for c in cities)
        slug = item.get("webflow_slug") or item.get("slug") or ""
        if not title or not slug:
            continue
        link = f"https://underdog.io/jobs/{slug}"
        jobs.append({
            "title": title,
            "company": "",  # their search API omits company; the detail page has it
            "description": _clean_html(item.get("description") or "")[:1500],
            "link": link, "apply_url": link, "location": location,
            "source": "underdog",
            "posted_at": parse_job_date(item.get("created_at")),
        })
    return jobs


_NODESK_SITEMAP_CACHE: List[str] = []
_NODESK_DETAIL_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}


def _parse_jsonld_job(text: str) -> Optional[Dict[str, Any]]:
    """First JobPosting JSON-LD block in a page (NoDesk emits unquoted script attrs)."""
    for raw in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", text or "", re.S):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for block in (data if isinstance(data, list) else [data]):
            if isinstance(block, dict) and block.get("@type") == "JobPosting":
                return block
    return None


def fetch_nodesk_jobs(search_query: str = "AI Engineer", limit: int = 10,
                      posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'NoDesk': job detail pages are listed in sitemap-jobs.xml and expose standard
    JobPosting JSON-LD. Sitemap + parsed details are cached per process (they are heavy)."""
    global _NODESK_SITEMAP_CACHE
    if not _NODESK_SITEMAP_CACHE:
        sm = _get_text("https://nodesk.co/sitemap-jobs.xml")
        # shortcut: sitemap order is not guaranteed newest-first; upgrade to the site's
        # internal search API if/when one appears.
        _NODESK_SITEMAP_CACHE = re.findall(r"<loc>([^<]+)</loc>", sm or "")[:24]
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for url in _NODESK_SITEMAP_CACHE:
        if len(jobs) >= limit:
            break
        block = _NODESK_DETAIL_CACHE.get(url)
        if block is None and url not in _NODESK_DETAIL_CACHE:
            page = _get_text(url)
            block = _parse_jsonld_job(page or "")
            _NODESK_DETAIL_CACHE[url] = block or False  # False = parsed, empty
        if not block:
            continue
        title = block.get("title") or ""
        desc = _clean_html(block.get("description") or "")[:1500]
        if not _matches_query(f"{title} {desc}", terms):
            continue
        org = block.get("hiringOrganization") or {}
        loc = block.get("jobLocation") or {}
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            location = ", ".join(str(addr.get(k, "")) for k in ("addressLocality", "streetAddress", "addressCountry")
                                 if isinstance(addr, dict) and addr.get(k))
        else:
            location = str(loc)
        link = block.get("url") or url
        jobs.append({
            "title": title,
            "company": org.get("name") if isinstance(org, dict) else str(org or ""),
            "description": desc,
            "link": link, "apply_url": link, "location": location,
            "source": "nodesk",
            "posted_at": parse_job_date(block.get("datePosted")),
        })
    return jobs


_RRS_CATEGORIES = ["software-engineer", "data-analyst"]
_RRS_CATEGORY_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def fetch_remoterocketship_jobs(search_query: str = "AI Engineer", limit: int = 10,
                                posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Remote Rocketship': their job API needs an account key (401 verified), but the
    site itself server-renders category pages with the full job array in __NEXT_DATA__
    (props.pageProps.initialJobOpenings) — parse that instead of hammering the keyed API."""
    terms = _query_terms(search_query)
    categories = list(_RRS_CATEGORIES)
    if any(t in terms for t in ("data", "analyst", "science", "analytics")) and "data-analyst" in categories:
        categories.remove("data-analyst")
        categories.insert(0, "data-analyst")
    jobs: List[Dict[str, Any]] = []
    for cat in categories:
        if len(jobs) >= limit:
            break
        if cat not in _RRS_CATEGORY_CACHE:
            page = _get_text(f"https://www.remoterocketship.com/jobs/{cat}/")
            openings: List[Dict[str, Any]] = []
            m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', page or "", re.S)
            if m:
                try:
                    data = json.loads(m.group(1))
                    openings = data["props"]["pageProps"].get("initialJobOpenings") or []
                except (KeyError, TypeError, ValueError):
                    openings = []
            _RRS_CATEGORY_CACHE[cat] = openings
        for item in _RRS_CATEGORY_CACHE[cat]:
            if len(jobs) >= limit:
                break
            title = item.get("roleTitle") or ""
            summary = item.get("jobDescriptionSummary") or ""
            if not _matches_query(f"{title} {summary} {' '.join(item.get('techStack') or [])}", terms):
                continue
            link = item.get("url") or f"https://www.remoterocketship.com/job/{item.get('slug', '')}/"
            location = item.get("location") or item.get("locationCity") or ""
            company = item.get("company") or ""
            if isinstance(company, dict):  # API nests the company object
                company = company.get("name") or ""
            jobs.append({
                "title": title,
                "company": company,
                "description": _clean_html(summary)[:1500],
                "link": link, "apply_url": link,
                "location": location if isinstance(location, str) else ", ".join(location or []),
                "source": "remoterocketship",
                "posted_at": parse_job_date(item.get("created_at")),
            })
    return jobs


def fetch_interndoor_jobs(search_query: str = "AI Engineer", limit: int = 10,
                          posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'InternDoor': official JSON Feed (interndoor.com/feed.json, 50 recent India
    internship/entry-level postings)."""
    data = _get_json("https://interndoor.com/feed.json")
    terms = _query_terms(search_query)
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("items", []):
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        content = item.get("content_text") or ""
        if not _matches_query(f"{title} {content}", terms):
            continue
        link = item.get("url") or ""
        authors = item.get("authors") or []
        company = ""
        if authors and isinstance(authors[0], dict):
            company = authors[0].get("name") or ""
        if not link:
            continue
        jobs.append({
            "title": title, "company": company,
            "description": content[:1500],
            "link": link, "apply_url": link,
            # Content is platform-authored listing text; extract a named Indian
            # place as location evidence rather than assuming the whole board
            # is India (the audit removed source-name bypasses for this reason).
            "location": (_india_place_from_text(content) or "").title(),
            "source": "interndoor",
            "posted_at": parse_job_date(item.get("date_published")),
        })
    return jobs


def fetch_jobsii_jobs(search_query: str = "AI Engineer", limit: int = 10,
                      posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Jobsii': WordPress REST API for its 'job' custom post type (search param,
    company/location/apply URL in ACF fields) — India AI/ML internships."""
    data = _get_json("https://jobsii.com/wp-json/wp/v2/job",
                     params={"per_page": max(limit * 2, 10), "search": search_query},
                     headers={**JSON_HEADERS})
    jobs: List[Dict[str, Any]] = []
    for item in (data if isinstance(data, list) else []):
        if len(jobs) >= limit:
            break
        title = _clean_html((item.get("title") or {}).get("rendered", ""))[:200]
        acf = item.get("acf") or {}
        link = item.get("link") or ""
        if not title or not link:
            continue
        desc = _clean_html((item.get("content") or {}).get("rendered", ""))[:1500]
        jobs.append({
            "title": title,
            "company": acf.get("company_name") or "",
            "description": desc,
            "link": link,
            "apply_url": acf.get("job_url") or link,
            "location": acf.get("location") or "",
            "source": "jobsii",
            "posted_at": parse_job_date(item.get("date")),
        })
    return jobs


# ── Direct-ATS boards: curated fast path + per-board helpers (discovery reuses these) ──

GREENHOUSE_COMPANIES = [
    "posthog", "browserstack", "hasura", "razorpay", "cred",
    "zerodha", "groww", "swiggy", "zomato", "curefit",
    "openai", "anthropic", "cohere", "scale-ai", "huggingface",
    "together-ai", "perplexity-ai", "replit", "linear",
    "vercel", "supabase", "weaviate", "pinecone", "qdrant"
]

LEVER_BOARDS = {
    "spotify": "Spotify", "palantir": "Palantir", "cloudinary": "Cloudinary",
    "jumpcloud": "JumpCloud", "wealthfront": "Wealthfront", "zoox": "Zoox",
    "veeva": "Veeva", "outreach": "Outreach", "protolabs": "Protolabs",
    "angellist": "AngelList", "greenlight": "Greenlight", "logrocket": "LogRocket",
    "secureframe": "Secureframe", "neon": "Neon", "loadsmart": "LoadSmart",
    "dlocal": "dLocal", "fundrise": "Fundrise", "extremenetworks": "Extreme Networks",
    "entrata": "Entrata",
}  # shortcut: curated US boards; the long tail comes from row-26 directory discovery

ASHBY_BOARDS = {"ramp": "Ramp", "openai": "OpenAI", "notion": "Notion", "vercel": "Vercel"}

_BOARD_CACHE: Dict[str, Any] = {}


def _cached_board(url: str) -> Any:
    """Per-process cache so repeated queries/windows don't refetch the same board."""
    hit = _BOARD_CACHE.get(url)
    if hit and (time.monotonic() - hit[0]) < 600:
        return hit[1]
    data = _get_json(url)
    _BOARD_CACHE[url] = (time.monotonic(), data)
    return data


def _fetch_greenhouse_board(slug: str, terms: List[str], limit: int,
                            cutoff: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """One Greenhouse board (boards-api.greenhouse.io) -> normalized jobs."""
    if limit <= 0:
        return []
    data = _cached_board(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    jobs: List[Dict[str, Any]] = []
    ai_signals = ["ai", "ml", "machine learning", "nlp", "llm", "deep learning",
                  "data scientist", "research", "model", "python", "automation"]
    for item in (data or {}).get("jobs", []):
        if len(jobs) >= limit:
            break
        title = item.get("title", "")
        desc = _clean_html(item.get("content", "") or "")[:1500]
        combined = f"{title.lower()} {desc[:300].lower()}"
        if terms and not any(t in combined for t in terms) and not any(k in combined for k in ai_signals):
            continue
        location = (item.get("location") or {}).get("name", "") or ""
        if not is_located_in_india({"location": location, "description": desc, "title": title,
                                    "source": "greenhouse"}):
            continue
        posted = parse_job_date(item.get("updated_at") or item.get("created_at") or "")
        if cutoff and posted and posted < cutoff:
            continue
        link = item.get("absolute_url") or ""
        if not link:
            continue
        jobs.append({
            "title": title,
            "company": slug.replace("-", " ").title(),
            "description": desc or f"{title} position at {slug}.",
            "link": link, "apply_url": link, "location": location,
            "source": "greenhouse", "posted_at": posted,
        })
    return jobs


def _fetch_lever_board(slug: str, terms: List[str], limit: int,
                       cutoff: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """One Lever board (api.lever.co postings API) -> normalized jobs."""
    if limit <= 0:
        return []
    postings = _cached_board(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(postings, list):
        return []
    jobs: List[Dict[str, Any]] = []
    for item in postings:
        if len(jobs) >= limit:
            break
        title = item.get("text") or ""
        desc = _clean_html(item.get("description") or "")[:1500]
        cats = item.get("categories") or {}
        location = cats.get("location") or ""
        if not _matches_query(f"{title} {desc} {location}", terms):
            continue
        created_ms = item.get("createdAt")
        posted = (datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
                  if isinstance(created_ms, (int, float)) else None)
        if cutoff and posted and posted < cutoff:
            continue
        link = item.get("hostedUrl") or item.get("applyUrl") or ""
        if not link:
            continue
        jobs.append({
            "title": title,
            "company": slug.replace("-", " ").title(),
            "description": desc or f"{title} ({location})",
            "link": link, "apply_url": item.get("applyUrl") or link, "location": location,
            "source": "lever", "posted_at": posted,
        })
    return jobs


def _fetch_ashby_board(slug: str, terms: List[str], limit: int,
                       cutoff: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """One Ashby board (posting-api.ashbyhq.com) -> normalized jobs."""
    if limit <= 0:
        return []
    data = _cached_board(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("jobs", []):
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        desc = _clean_html(item.get("description") or item.get("descriptionPlain") or "")[:1500]
        location = item.get("location") or ""
        if not _matches_query(f"{title} {desc} {location}", terms):
            continue
        posted = parse_job_date(item.get("publishedAt") or item.get("publishedAtIso"))
        if cutoff and posted and posted < cutoff:
            continue
        link = item.get("jobUrl") or item.get("applyUrl") or ""
        if not link:
            continue
        jobs.append({
            "title": title,
            "company": slug.replace("-", " ").title(),
            "description": desc or f"{title} ({location})",
            "link": link, "apply_url": item.get("applyUrl") or link, "location": location,
            "source": "ashby", "posted_at": posted,
        })
    return jobs


def fetch_greenhouse_jobs(search_query: str = "AI Engineer", limit: int = 10,
                          posted_within_hours: int = 168) -> List[Dict[str, Any]]:
    """CSV 'Greenhouse Career Pages': curated public boards (India + AI-heavy companies),
    in the order listed in GREENHOUSE_COMPANIES."""
    terms = _query_terms(search_query)
    cutoff = _NOW() - timedelta(hours=posted_within_hours)
    jobs: List[Dict[str, Any]] = []
    for slug in GREENHOUSE_COMPANIES:
        if len(jobs) >= limit:
            break
        jobs.extend(_fetch_greenhouse_board(slug, terms, limit - len(jobs), cutoff))
    return jobs[:limit]


def fetch_lever_jobs(search_query: str = "AI Engineer", limit: int = 10,
                     posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Lever Career Pages': curated public Lever boards via the postings API."""
    terms = _query_terms(search_query)
    cutoff = _NOW() - timedelta(hours=posted_within_hours)
    jobs: List[Dict[str, Any]] = []
    for slug in LEVER_BOARDS:
        if len(jobs) >= limit:
            break
        jobs.extend(_fetch_lever_board(slug, terms, limit - len(jobs), cutoff))
    return jobs[:limit]


def fetch_ashby_jobs(search_query: str = "AI Engineer", limit: int = 10,
                     posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Ashby Job Boards': curated public Ashby boards via the posting API."""
    terms = _query_terms(search_query)
    cutoff = _NOW() - timedelta(hours=posted_within_hours)
    jobs: List[Dict[str, Any]] = []
    for slug in ASHBY_BOARDS:
        if len(jobs) >= limit:
            break
        jobs.extend(_fetch_ashby_board(slug, terms, limit - len(jobs), cutoff))
    return jobs[:limit]


def fetch_workable_jobs(search_query: str = "AI Engineer", limit: int = 10,
                        posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Workable': official jobs.workable.com aggregator API (server-side query param
    'query'; covers every Workable-hosted company board in one endpoint)."""
    data = _get_json("https://jobs.workable.com/api/v1/jobs",
                     params={"query": search_query},
                     headers={**JSON_HEADERS})
    jobs: List[Dict[str, Any]] = []
    for item in (data or {}).get("jobs", []):
        if len(jobs) >= limit:
            break
        title = item.get("title") or ""
        company = (item.get("company") or {}).get("title") or ""
        loc = item.get("location") or {}
        location = ", ".join(p for p in (loc.get("city"), loc.get("countryName")) if p)
        link = item.get("url") or ""
        if not title or not link:
            continue
        jobs.append({
            "title": title, "company": company,
            "description": _clean_html(item.get("description") or "")[:1500],
            "link": link, "apply_url": link, "location": location,
            "source": "workable",
            "posted_at": parse_job_date(item.get("created") or item.get("updated")),
        })
    return jobs[:limit]


# ── Row 26: Direct Startup Career Pages (search-assisted board discovery) ──────

BOARD_DIRECTORY_BASE = "https://kalebconfer-sys.github.io/job-board-directory"
_DISCOVERY_SOURCES = {
    "greenhouse": ("greenhouse.csv", _fetch_greenhouse_board),
    "lever": ("lever.csv", _fetch_lever_board),
    "ashby": ("ashby.csv", _fetch_ashby_board),
}
_DIRECTORY_CACHE: Dict[str, List[tuple]] = {}
_discovery_offset = {"i": 0}


def _load_directory(platform: str) -> List[tuple]:
    """[(token, company), ...] for one ATS from the free verified board directory."""
    if platform not in _DIRECTORY_CACHE:
        csv_file, _ = _DISCOVERY_SOURCES[platform]
        text = _get_text(f"{BOARD_DIRECTORY_BASE}/{csv_file}")
        rows: List[tuple] = []
        for i, line in enumerate((text or "").splitlines()):
            if i == 0 or not line.strip():
                continue  # header: platform,token,company,board_url,api_url,...
            parts = line.split(",")
            if len(parts) >= 3 and parts[1].strip():
                rows.append((parts[1].strip(), parts[2].strip()))
        _DIRECTORY_CACHE[platform] = rows
    return _DIRECTORY_CACHE[platform]


def fetch_discovery_jobs(search_query: str = "AI Engineer", limit: int = 10,
                         posted_within_hours: int = 24) -> List[Dict[str, Any]]:
    """CSV 'Direct Startup Career Pages': Google scraping is bot-walled and its Custom
    Search API needs a paid key (both verified), so the optimized method is the free
    verified job-board directory (12k+ company career boards mapped to Greenhouse/Lever/
    Ashby public APIs). Rotates its starting offset each call so coverage grows per run;
    the pipeline's dedup drops overlaps with rows 22-24.
    shortcut: directory is a third-party snapshot; refresh source if it disappears."""
    terms = _query_terms(search_query)
    cutoff = _NOW() - timedelta(hours=posted_within_hours)
    jobs: List[Dict[str, Any]] = []
    per_platform = max(3, limit // 2)
    for platform, (_, fetcher) in _DISCOVERY_SOURCES.items():
        if len(jobs) >= limit:
            break
        rows = _load_directory(platform)
        if not rows:
            continue
        start = _discovery_offset["i"] % len(rows)
        for step in range(per_platform):
            if len(jobs) >= limit:
                break
            token, company = rows[(start + step) % len(rows)]
            found = fetcher(token, terms, per_platform, cutoff)
            for job in found:
                if company:
                    job["company"] = company  # directory carries the real company name
                job["source"] = "discovery"  # re-tag: source dropdown/quota key is the CSV row
                jobs.append(job)
                if len(jobs) >= limit:
                    break
        _discovery_offset["i"] += per_platform
    return jobs[:limit]

# ---------------------------------------------------------------------------
# Platform Registry & Quota Distribution — mirrors internship_sources_autonomous_agent.csv
#   get_scraper_platforms()  : CSV "Main" rows, fetched first, in CSV order.
#   get_fallback_platforms() : CSV "Fallback"/"Fallback-Direct ATS"/"Fallback-Discovery"
#                              rows, fetched in order only while still under target.
#   LinkedIn additionally gets an uncapped deep-widen safety net in pipeline_core.
# ---------------------------------------------------------------------------

PLATFORM_QUOTAS = {
    # CSV "Main"
    "yc":               6,
    "startupjobs":      4,
    "websearch":        4,
    "wellfound":        6,
    "cutshort":         4,
    "linkedin":        10,
    "instahyre":        6,
    "hirist":           2,
    "naukri":           2,
    # CSV "Fallback"
    "hn":               4,
    "remoteok":         3,
    "remotive":         3,
    "himalayas":        3,
    "wwr":              2,
    "builtin":          2,
    "wttj":             2,
    "underdog":         2,
    "nodesk":           2,
    "remoterocketship": 2,
    "interndoor":       6,
    "jobsii":           6,
    # CSV "Fallback / Direct ATS"
    "greenhouse":       5,
    "lever":            4,
    "ashby":            4,
    "workable":         3,
    # CSV "Fallback / Discovery"
    "discovery":        4,
}


def get_scraper_platforms() -> List[Dict[str, Any]]:
    """
    Returns the ordered PRIMARY pass: the CSV "Main" portals.
    Fallback portals live in get_fallback_platforms(); LinkedIn's uncapped
    deep-widen safety net is driven directly by pipeline_core.
    """
    return [
        {
            "name": "Y Combinator (YC Jobs)",
            "source": "yc",
            "quota": PLATFORM_QUOTAS["yc"],
            "fn": lambda q, lim, hrs, off: fetch_yc_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Startup Jobs (Official RSS)",
            "source": "startupjobs",
            "quota": PLATFORM_QUOTAS["startupjobs"],
            "fn": lambda q, lim, hrs, off: fetch_startupjobs_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Web Search (Bing)",
            "source": "websearch",
            "quota": PLATFORM_QUOTAS["websearch"],
            "fn": lambda q, lim, hrs, off: fetch_websearch_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Wellfound (AngelList)",
            "source": "wellfound",
            "quota": PLATFORM_QUOTAS["wellfound"],
            "fn": lambda q, lim, hrs, off: fetch_wellfound_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Cutshort (India Startups)",
            "source": "cutshort",
            "quota": PLATFORM_QUOTAS["cutshort"],
            "fn": lambda q, lim, hrs, off: fetch_cutshort_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "LinkedIn Jobs",
            "source": "linkedin",
            "quota": PLATFORM_QUOTAS["linkedin"],
            "fn": lambda q, lim, hrs, off: fetch_linkedin_jobs(
                search_query=q, location="India", limit=lim,
                posted_within_hours=hrs, start_offset=off)
        },
        {
            "name": "Instahyre (India)",
            "source": "instahyre",
            "quota": PLATFORM_QUOTAS["instahyre"],
            "fn": lambda q, lim, hrs, off: fetch_instahyre_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Hirist (India Tech)",
            "source": "hirist",
            "quota": PLATFORM_QUOTAS["hirist"],
            "fn": lambda q, lim, hrs, off: fetch_hirist_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Naukri (India)",
            "source": "naukri",
            "quota": PLATFORM_QUOTAS["naukri"],
            "fn": lambda q, lim, hrs, off: fetch_naukri_jobs(q, limit=lim, posted_within_hours=hrs)
        },
    ]


def get_fallback_platforms() -> List[Dict[str, Any]]:
    """
    Returns the ordered FALLBACK pass: the CSV "Fallback" portals — regular remote
    boards first, then Direct ATS boards, then the discovery row — fetched only
    while the run is still under its target of 25 qualified openings.
    """
    return [
        {
            "name": "Hacker News – Who is Hiring",
            "source": "hn",
            "quota": PLATFORM_QUOTAS["hn"],
            "fn": lambda q, lim, hrs, off: fetch_hn_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Remote OK",
            "source": "remoteok",
            "quota": PLATFORM_QUOTAS["remoteok"],
            "fn": lambda q, lim, hrs, off: fetch_remoteok_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Remotive",
            "source": "remotive",
            "quota": PLATFORM_QUOTAS["remotive"],
            "fn": lambda q, lim, hrs, off: fetch_remotive_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Himalayas",
            "source": "himalayas",
            "quota": PLATFORM_QUOTAS["himalayas"],
            "fn": lambda q, lim, hrs, off: fetch_himalayas_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "We Work Remotely",
            "source": "wwr",
            "quota": PLATFORM_QUOTAS["wwr"],
            "fn": lambda q, lim, hrs, off: fetch_wwr_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Built In",
            "source": "builtin",
            "quota": PLATFORM_QUOTAS["builtin"],
            "fn": lambda q, lim, hrs, off: fetch_builtin_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Welcome to the Jungle",
            "source": "wttj",
            "quota": PLATFORM_QUOTAS["wttj"],
            "fn": lambda q, lim, hrs, off: fetch_wttj_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Underdog.io",
            "source": "underdog",
            "quota": PLATFORM_QUOTAS["underdog"],
            "fn": lambda q, lim, hrs, off: fetch_underdog_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "NoDesk",
            "source": "nodesk",
            "quota": PLATFORM_QUOTAS["nodesk"],
            "fn": lambda q, lim, hrs, off: fetch_nodesk_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Remote Rocketship",
            "source": "remoterocketship",
            "quota": PLATFORM_QUOTAS["remoterocketship"],
            "fn": lambda q, lim, hrs, off: fetch_remoterocketship_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "InternDoor (India)",
            "source": "interndoor",
            "quota": PLATFORM_QUOTAS["interndoor"],
            "fn": lambda q, lim, hrs, off: fetch_interndoor_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Jobsii (India AI/ML)",
            "source": "jobsii",
            "quota": PLATFORM_QUOTAS["jobsii"],
            "fn": lambda q, lim, hrs, off: fetch_jobsii_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Greenhouse Career Pages",
            "source": "greenhouse",
            "quota": PLATFORM_QUOTAS["greenhouse"],
            "fn": lambda q, lim, hrs, off: fetch_greenhouse_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Lever Career Pages",
            "source": "lever",
            "quota": PLATFORM_QUOTAS["lever"],
            "fn": lambda q, lim, hrs, off: fetch_lever_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Ashby Job Boards",
            "source": "ashby",
            "quota": PLATFORM_QUOTAS["ashby"],
            "fn": lambda q, lim, hrs, off: fetch_ashby_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Workable",
            "source": "workable",
            "quota": PLATFORM_QUOTAS["workable"],
            "fn": lambda q, lim, hrs, off: fetch_workable_jobs(q, limit=lim, posted_within_hours=hrs)
        },
        {
            "name": "Direct Startup Career Pages (Discovery)",
            "source": "discovery",
            "quota": PLATFORM_QUOTAS["discovery"],
            "fn": lambda q, lim, hrs, off: fetch_discovery_jobs(q, limit=lim, posted_within_hours=hrs)
        },
    ]


