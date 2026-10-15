# TODO — Product changes (Oct 2026)

## 1. AI-specific openings only (AI Automation / AI Engineer / GenAI Developer / AI Generalist / AI Consultant)
- [x] Add `is_ai_role(title, desc)` guardrail in `tools/job_api.py` (word-boundary AI-family pattern; generic titles need AI evidence in the body)
- [x] Enforce it in the shared `_harvest()` stage (applies to Main, Fallback and LinkedIn passes)
- [x] Fix `_matches_query` substring false-positives ("ai" matching "detail"/"maintain") → word boundaries

## 2. Real scoring on every opening (scores were missing)
- [x] Root cause: new platforms return short descriptions and the enricher destroyed
      JSON-LD before parsing → LLM refused to score (<400 chars) → "apply link only"
- [x] `tools/jd_fetcher.py`: extract JobPosting JSON-LD description first (≥100 chars),
      then og:description, then existing content heuristics
- [x] `tools/jd_matcher.py`: total LLM failure returns `score: None` (honest unscored)
      instead of a fabricated `0`

## 3. Internships only — no full-time roles
- [x] Add `is_internship_title()` word-boundary guardrail ("international"/"internal" must not match)
- [x] Enforce in `_harvest()` before enrichment (saves fetches)
- [x] `classify_role_type`: internship now outranks contract ("AI Consultant Intern" is an intern)

## 4. Browser/web-search source, top-3 priority
- [x] Live-verified: every keyless engine (Bing RSS/HTML, Google, DDG, Mojeek,
      Ecosia, Qwant, Yahoo, Yep, SearXNG) is bot-walled or serves decoy results
- [x] `fetch_websearch_jobs()`: Google Programmable Search JSON API primary,
      Brave Search API fallback (user-chosen) → open result page →
      JobPosting JSON-LD only (canonical URL; nothing fabricated; negative cache)
- [x] Registered as Main portal #3 (after Y Combinator, Startup Jobs)
- [x] Spec CSV row + registry order/quota test updated (Main = 9 portals, 26 total)
- [x] settings/.env.example (GOOGLE_CSE_API_KEY/GOOGLE_CSE_CX/BRAVE_SEARCH_API_KEY),
      frontend dropdown + cascade count, docs
- [ ] User action: add ONE key pair to `.env` (Google CSE key+CX, or Brave key) —
      until then the portal honestly returns nothing

## 5. Verification
- [x] New offline tests for gates, websearch provider chain, enricher, matcher honesty
      (`tests/test_role_gates.py`, extended `test_job_sources.py`, `test_jd_matcher_gate.py`)
- [x] Full test suite green (113 passing, 2 pre-existing unrelated warnings)
- [x] Provider endpoints: wired to official API specs; live run needs the user's key (see 4)
- [ ] Commit — awaiting user go-ahead
