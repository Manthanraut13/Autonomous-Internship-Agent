# AGENT.md — Autonomous Internship Agent

Operational specification and honest project status.

> Note: this file previously contained a fabricated development-status report
> (invented phase dates, placeholder checklists, and test-coverage percentages
> that were never measured). It was replaced with a description of what
> actually exists in this repository.

## What this project is

An automated pipeline that scrapes AI/ML internship openings from the 26
portals listed in `internship_sources_autonomous_agent.csv` (9 Main → 17
Fallback, with an uncapped LinkedIn India deep-widen safety net), keeps only
India-based AI internships (internship-only + AI-family guardrails), scores
them against a candidate resume with a Groq LLM, and delivers matches via a
React dashboard, CSV email, and WhatsApp summary.

- Architecture and usage: `README.md`
- Pipeline detail: `DOCUMENTATION.md`
- Shared pipeline implementation: `tools/pipeline_core.py` — consumed by both
  the CLI (`run_pipeline.py`) and the SSE dashboard stream (`main.py`)

## Testing

- Suite: `tests/` (pytest), 100+ unit/integration tests, fully offline.
- Run: `venv\Scripts\python -m pytest tests/ -v` (or `python -m pytest`).
- Covered: India location guardrail, internship-only + AI-family role
  guardrails, LLM scoring gate (no real job description → delivered
  "unscored, apply link only"), whole-word tech keyword pre-filter,
  Web Search provider chain (Google CSE/Brave + JSON-LD-only harvest),
  login brute-force guard, pipeline-core smoke path (dedup, date gate,
  unscored delivery, dry-run, client-disconnect abort).
- Known gaps: no coverage measurement is run or claimed; scraper HTML parsers,
  email/WhatsApp delivery, and the React frontend have no automated tests.

## Known limitations

- `posted_at` values that are strings or unparseable bypass the 24-hour date
  gate (only verified datetimes are rejected as stale).
- APScheduler and the GitHub Actions cron both run at 9:00 AM/9:00 PM IST
  (cron times are converted to UTC in the workflow; APScheduler pins
  `Asia/Kolkata`).
- The admin login rate limiter is in-memory (correct for the single-process
  app; would need a shared store with multiple workers).
- Admin credentials come only from the environment (`ADMIN_PASSWORD`); never
  commit passwords, and rotate any credential that has ever appeared in git
  history.
- The Web Search portal needs one search key (`GOOGLE_CSE_API_KEY` +
  `GOOGLE_CSE_CX`, or `BRAVE_SEARCH_API_KEY`); without either it returns `[]`
  by design — that is configuration, not a bug.

## Operating rules for agents & contributors

- Never claim behavior, metrics, or coverage that was not measured.
- Run the pytest suite before claiming a fix is complete.
- Pipeline logic changes belong in `tools/pipeline_core.py` (one copy);
  both frontends inherit them automatically.
- Keep the India location guardrail strict; do not add per-source bypasses.
- Jobs without a real job description after enrichment must stay unscored
  (`match_score = NULL`) — never let the LLM score a synthetic one-liner.
