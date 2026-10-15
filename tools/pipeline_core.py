"""
Shared pipeline core for the Autonomous Internship Agent.

Single implementation of the scrape → dedup → guardrail → score → deliver
flow, consumed by both frontends:

- run_pipeline.py (CLI) iterates the events and prints them.
- main.py (SSE dashboard) bridges the generator into Server-Sent Events
  from a worker thread.

Previously this logic was copy-pasted in both files and had already drifted:
the CLI enforced per-platform quotas and a hard 24-hour date cutoff while the
dashboard enforced neither, so the same posting could pass one path and fail
the other.
"""

import os
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

import dateutil.parser

from config.settings import settings
from db.database import get_db_context, cleanup_expired_rejected_jobs
from db.models import Job, PipelineRun
from tools.job_api import (get_scraper_platforms, get_fallback_platforms,
                           is_located_in_india, is_internship_title, is_ai_role,
                           fetch_linkedin_jobs)
from tools.semantic_matcher import (
    ResumeEmbedder,
    classify_role_type,
    classify_work_mode,
    is_explicit_tech_job,
)
from tools.jd_matcher import match_resume_to_job, MIN_LLM_DESCRIPTION_CHARS
from tools.jd_fetcher import fetch_full_job_description
from tools.resume_parser import (
    extract_text_from_pdf,
    parse_resume,
    get_search_queries_from_resume,
)
from tools.csv_exporter import export_jobs_to_csv
from tools.email_sender import send_csv_email
from tools.whatsapp_handler import send_whatsapp_summary

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Politeness/rate-limit delay after each LLM scoring call (Groq free tier).
RATE_LIMIT_SECS = 1.5

CORE_AI_QUERIES = [
    "AI Engineer", "GenAI Developer", "LLM Engineer",
    "Machine Learning Engineer", "AI Automation Engineer",
    "AI Agent Developer", "AI Intern", "Machine Learning Intern",
    "GenAI Intern", "Data Science Intern", "Python AI Developer", "NLP Engineer",
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def find_resume() -> str:
    """Locate the resume PDF in the project directory, prioritizing Manthan_Raut.pdf."""
    candidates = [
        os.path.join(BASE_DIR, "Manthan_Raut.pdf"),
        os.path.join(BASE_DIR, "Manthan_Raut_Resume (1).pdf"),
        os.path.join(BASE_DIR, "data", "current_resume.pdf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "No resume found. Place Manthan_Raut.pdf in the project root."
    )


def get_resume_text(resume_path: str) -> str:
    """Extract raw text from the resume for LLM matching."""
    try:
        return extract_text_from_pdf(resume_path)
    except Exception:
        parsed = parse_resume(resume_path)
        parts = []
        for section, lines in parsed.items():
            if lines:
                parts.append(f"## {section.title()}")
                parts.extend(lines)
        return "\n".join(parts)


def get_existing_db_signatures() -> Tuple[Set[str], Set[str], Set[Tuple[str, str]]]:
    """Existing (link, apply_url, title+company) signatures to deduplicate against."""
    with get_db_context() as db:
        links: Set[str] = set()
        apply_urls: Set[str] = set()
        title_company: Set[Tuple[str, str]] = set()
        for j in db.query(Job.link, Job.apply_url, Job.title, Job.company).all():
            if j[0]:
                links.add(j[0].strip().lower())
            if j[1]:
                apply_urls.add(j[1].strip().lower())
            if j[2] and j[3]:
                title_company.add((j[2].strip().lower(), j[3].strip().lower()))
        return links, apply_urls, title_company


def passes_date_gate(posted_at: Any, within_hours: int) -> bool:
    """Hard recency gate: postings are verified against the window.

    - Verified datetimes (or parseable date strings) must be inside the window.
    - A date field that exists but cannot be parsed is REJECTED: recency
      cannot be verified (previously such postings slipped through, issue #11).
    - No date field at all → passes (many boards publish without dates).
    """
    if posted_at is None:
        return True
    if isinstance(posted_at, str):
        if not posted_at.strip():
            return True
        try:
            posted_at = dateutil.parser.parse(posted_at)
        except (ValueError, OverflowError, TypeError):
            return False
    if not isinstance(posted_at, datetime):
        return False
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    return posted_at >= cutoff


def build_job_card(j: Dict[str, Any], score: Any, reasoning: str, sem_score: float,
                   role_type: str, work_mode: str, seq: int) -> Dict[str, Any]:
    """Shaped payload the dashboard uses to insert a card optimistically."""
    return {
        "id": -seq,
        "job_id": j.get("job_id", f"job-{uuid.uuid4().hex[:8]}"),
        "title": j["title"],
        "company": j["company"],
        "description": j.get("description", "")[:2000],
        "link": j.get("link", ""),
        "apply_url": j.get("apply_url", ""),
        "location": j.get("location", ""),
        "source": j.get("source", "aggregated"),
        "posted_at": str(j.get("posted_at", "")),
        "match_score": score,
        "match_reasoning": reasoning,
        "semantic_score": sem_score,
        "role_type": role_type,
        "work_mode": work_mode,
        "status": "saved",
    }


def _log_run(run_start: datetime, jobs_found: int, jobs_matched: int,
             email_sent: bool, whatsapp_sent: bool, csv_path: Optional[str],
             source: str) -> None:
    try:
        with get_db_context() as db:
            db.add(PipelineRun(
                started_at=run_start,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                status="success",
                jobs_found=jobs_found,
                jobs_matched=jobs_matched,
                email_sent=bool(email_sent),
                whatsapp_sent=bool(whatsapp_sent),
                csv_path=csv_path,
                source=source,
            ))
            db.commit()
    except Exception as e:
        logger.warning(f"Could not log pipeline run: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Main pipeline generator
# ──────────────────────────────────────────────────────────────────────────────

def process_jobs(target_matches: int = 25, threshold: int = 70, source: str = "cli",
                 dry_run: bool = False,
                 should_abort: Optional[Callable[[], bool]] = None) -> Iterator[Dict[str, Any]]:
    """
    Runs the full pipeline, yielding progress events of the shape
    {"step": str, "message": str, "data": optional dict}.

    The final event always has step "complete", "aborted" or "error"; its
    "data" carries the outcome (counts, csv_path, email_sent, ...).
    """
    abort = should_abort or (lambda: False)
    run_start = datetime.now(timezone.utc).replace(tzinfo=None)
    email_sent = False
    whatsapp_sent = False
    csv_path = None

    scored_jobs: List[Dict[str, Any]] = []
    unscored_jobs: List[Dict[str, Any]] = []  # no real JD after enrichment → apply link only
    final_jobs: List[Dict[str, Any]] = []
    seen_in_run_links: Set[str] = set()
    seen_in_run_signatures: Set[Tuple[str, str]] = set()
    total_scraped_count = 0
    duplicate_skipped_count = 0
    semantic_filtered_count = 0

    platform_matched_counts: Dict[str, int] = {}

    def summary_data(status: str = "success") -> Dict[str, Any]:
        return {
            "status": status,
            "matched": len(final_jobs),
            "jobs_matched": len(final_jobs),
            "unscored": len(unscored_jobs),
            "jobs_unscored": len(unscored_jobs),
            "total_scraped": total_scraped_count,
            "duplicate_skipped": duplicate_skipped_count,
            "semantic_filtered": semantic_filtered_count,
            "platform_breakdown": {k: v for k, v in platform_matched_counts.items() if v > 0},
            "email_sent": bool(email_sent),
            "whatsapp_sent": bool(whatsapp_sent),
            "csv_path": csv_path,
        }

    try:
        # ── Step 1: Locate & parse resume, build embeddings ────────────────
        yield {"step": "resume", "message": "Locating and parsing candidate resume..."}
        resume_path = find_resume()
        resume_text = get_resume_text(resume_path)
        yield {"step": "resume", "message": f"Resume loaded: {os.path.basename(resume_path)} ({len(resume_text)} chars)"}

        yield {"step": "resume", "message": "Generating vector embeddings for candidate resume sections..."}
        embedder = ResumeEmbedder(resume_path)
        yield {"step": "resume", "message": f"Vector embeddings ready ({len(embedder.chunks)} semantic sections cached)"}

        # ── Step 2: Search queries ─────────────────────────────────────────
        yield {"step": "queries", "message": "Generating AI, GenAI & ML search queries (India Only)..."}
        search_queries = get_search_queries_from_resume(resume_path)
        for q in CORE_AI_QUERIES:
            if q not in search_queries:
                search_queries.append(q)
        yield {"step": "queries",
               "message": f"Active AI Queries ({len(search_queries)}): {', '.join(search_queries[:5])}...",
               "data": search_queries}

        # ── Step 3: Storage cleanup + dedup signatures ─────────────────────
        try:
            cleaned_count = cleanup_expired_rejected_jobs(max_age_hours=24)
            if cleaned_count:
                yield {"step": "cleanup",
                       "message": f"🧹 Storage cleanup: permanently purged {cleaned_count} rejected opening(s) older than 24h."}
        except Exception as e:
            logger.warning(f"Storage cleanup notice: {e}")

        db_links, db_apply_urls, db_title_company = get_existing_db_signatures()
        yield {"step": "scraping",
               "message": f"Known DB listings to deduplicate against: {len(db_links)} records"}

        platforms = get_scraper_platforms()
        platform_matched_counts = {p["source"]: 0 for p in platforms}
        yield {"step": "scraping",
               "message": f"Starting primary portal search (Target: {target_matches} verified India AI openings across {len(platforms)} platforms)...",
               "data": [{"name": p["name"], "quota": p["quota"]} for p in platforms]}

        def _harvest(raw_jobs: List[Dict[str, Any]], tag: str, window: int,
                     source_key: str) -> Iterator[Dict[str, Any]]:
            """Shared scrape → dedup → guardrail → date gate → enrich → classify →
            score stage for every pass (Main, CSV fallback, LinkedIn deep-widen).

            `tag` names the origin in log messages, `window` is the date-gate
            window in hours, `source_key` feeds the per-platform match counts.
            Nested generator over pipeline state; counters rebound via nonlocal.
            """
            nonlocal total_scraped_count, duplicate_skipped_count, semantic_filtered_count
            total_scraped_count += len(raw_jobs)

            for j in raw_jobs:
                if abort():
                    yield {"step": "aborted", "message": "Pipeline aborted (client disconnected).",
                           "data": summary_data(status="aborted")}
                    return
                if len(scored_jobs) >= target_matches:
                    break

                link = (j.get("link") or "").strip().lower()
                apply_url = (j.get("apply_url") or "").strip().lower()
                title = (j.get("title") or "").strip().lower()
                company = (j.get("company") or "").strip().lower()
                sig = (title, company)

                if (link in db_links or
                    apply_url in db_apply_urls or
                    sig in db_title_company or
                    link in seen_in_run_links or
                    sig in seen_in_run_signatures):
                    duplicate_skipped_count += 1
                    continue

                # Strict India location guardrail
                if not is_located_in_india(j):
                    continue

                # Internship-only guardrail (spec): the title itself must declare
                # an internship; full-time roles are never delivered.
                if not is_internship_title(title):
                    continue

                # Hard date gate (24h on Main; the pass's own window on fallbacks)
                if not passes_date_gate(j.get("posted_at"), window):
                    continue

                if link:
                    seen_in_run_links.add(link)
                if apply_url:
                    seen_in_run_links.add(apply_url)
                if title and company:
                    seen_in_run_signatures.add(sig)

                desc = j.get("description", "")
                if len(desc.strip()) < MIN_LLM_DESCRIPTION_CHARS and j.get("link"):
                    try:
                        enriched = fetch_full_job_description(j["link"])
                        if enriched and len(enriched) > len(desc):
                            desc = enriched
                            j["description"] = desc
                    except Exception:
                        pass

                if not desc or len(desc.strip()) < 30:
                    continue

                # AI-family guardrail (spec): only AI Automation / AI Engineer /
                # GenAI / AI Generalist / AI Consultant equivalents are delivered.
                if not is_ai_role(j.get("title"), desc):
                    continue

                role_type = classify_role_type(j)
                work_mode = classify_work_mode(j)
                j["role_type"] = role_type
                j["work_mode"] = work_mode

                sem_score = embedder.compute_semantic_score(desc, j.get("title", ""))
                j["semantic_score"] = sem_score

                # Explicit whole-word tech keyword → skip the cheap semantic pre-filter
                is_explicit_tech = is_explicit_tech_job(j.get("title", ""), desc)

                if not is_explicit_tech and sem_score < 15.0:
                    semantic_filtered_count += 1
                    yield {"step": "matching",
                           "message": f"⏩ [{tag}] Pre-filtered non-tech role ({sem_score}/100): {j['title']} @ {j['company']}"}
                    continue

                yield {"step": "matching",
                       "message": f"[{len(scored_jobs)}/{target_matches} Found] 🔄 Scoring [{tag} | {role_type.upper()}|{work_mode.upper()}]: {j['title']} @ {j['company']} (Semantic: {sem_score})..."}

                try:
                    result = match_resume_to_job(resume_text, desc)
                    score = result.get("score", 0)
                    reasoning = result.get("reasoning", "")
                    key_matches = result.get("key_matches", [])
                except Exception as e:
                    yield {"step": "matching", "message": f"❌ Error scoring {j['title']}: {e}"}
                    continue

                j["match_score"] = score
                j["match_reasoning"] = reasoning
                j["key_matches"] = key_matches

                # No real JD even after enrichment → deliver honestly as
                # "apply link only"; never let the LLM invent a score.
                if score is None:
                    unscored_jobs.append(j)
                    yield {"step": "matching",
                           "message": f"⏸️ Unscored — no real job description after enrichment ({len(desc)} chars): {j['title']} @ {j['company']} → apply link only"}
                    continue

                job_card = build_job_card(j, score, reasoning, sem_score, role_type,
                                          work_mode, len(scored_jobs) + 1)

                emoji = "✅" if score >= threshold else "⬇️"
                yield {"step": "matching",
                       "message": f"[{len(scored_jobs)+1}/{target_matches}] {emoji} [{tag} | {role_type.upper()}|{work_mode.upper()}] {j['title']} @ {j['company']} → {score}/100",
                       "data": {
                           "title": j["title"],
                           "company": j["company"],
                           "score": score,
                           "role_type": role_type,
                           "work_mode": work_mode,
                           "semantic_score": sem_score,
                           "job": job_card if score >= threshold else None,
                       }}

                if score >= threshold:
                    scored_jobs.append(j)
                    platform_matched_counts[source_key] = platform_matched_counts.get(source_key, 0) + 1
                    if len(scored_jobs) >= target_matches:
                        yield {"step": "matching",
                               "message": f"🎉 Reached exact target of {target_matches} qualified India AI openings on {tag}! Halting search."}
                        break

                time.sleep(RATE_LIMIT_SECS)

        # ── Node 1: Primary Portals Search ─────────────────────────────────
        for p_idx, platform in enumerate(platforms, 1):
            if len(scored_jobs) >= target_matches:
                break

            plat_name = platform["name"]
            plat_source = platform["source"]
            plat_fn = platform["fn"]
            plat_quota = platform["quota"]

            yield {"step": "scraping",
                   "message": f"🚀 [Priority {p_idx}/{len(platforms)}] Searching {plat_name} (Quota: {plat_quota}, Remaining: {target_matches - len(scored_jobs)} matches)..."}
            plat_matches_before = platform_matched_counts[plat_source]

            for query in search_queries:
                if abort():
                    yield {"step": "aborted", "message": "Pipeline aborted (client disconnected).",
                           "data": summary_data(status="aborted")}
                    return
                if len(scored_jobs) >= target_matches:
                    break
                if (platform_matched_counts[plat_source] - plat_matches_before) >= plat_quota:
                    break

                yield {"step": "scraping", "message": f"[{plat_name}] Fetching: \"{query}\" (24h)..."}
                try:
                    raw_jobs = plat_fn(query, 10, 24, 0)
                except Exception as e:
                    yield {"step": "scraping", "message": f"⚠️ Scraper warning on {plat_name}: {e}"}
                    continue

                yield from _harvest(raw_jobs, plat_name, 24, plat_source)

        # ── Node 2: CSV Fallback Portals (only while still under target) ──
        if len(scored_jobs) < target_matches:
            fallbacks = get_fallback_platforms()
            needed = target_matches - len(scored_jobs)
            yield {"step": "scraping",
                   "message": f"⚠️ Fallback Node Activated: Primary platforms yielded {len(scored_jobs)}/{target_matches} matches. Searching {len(fallbacks)} CSV fallback portals for {needed} more..."}

            # 24h window first, then 72h if still below target
            for time_window in [24, 72]:
                if len(scored_jobs) >= target_matches:
                    break

                for f_idx, platform in enumerate(fallbacks, 1):
                    if len(scored_jobs) >= target_matches:
                        break

                    plat_name = platform["name"]
                    plat_source = platform["source"]
                    plat_fn = platform["fn"]
                    plat_quota = platform["quota"]
                    plat_matches_before = platform_matched_counts.setdefault(plat_source, 0)

                    yield {"step": "scraping",
                           "message": f"🔽 [Fallback {f_idx}/{len(fallbacks)}] Searching {plat_name} ({time_window}h, Quota: {plat_quota}, Remaining: {target_matches - len(scored_jobs)} matches)..."}

                    for query in search_queries:
                        if abort():
                            yield {"step": "aborted", "message": "Pipeline aborted (client disconnected).",
                                   "data": summary_data(status="aborted")}
                            return
                        if len(scored_jobs) >= target_matches:
                            break
                        if (platform_matched_counts[plat_source] - plat_matches_before) >= plat_quota:
                            break

                        yield {"step": "scraping", "message": f"[{plat_name}] Fetching: \"{query}\" ({time_window}h)..."}
                        try:
                            raw_jobs = plat_fn(query, 10, time_window, 0)
                        except Exception as e:
                            yield {"step": "scraping", "message": f"⚠️ Scraper warning on {plat_name}: {e}"}
                            continue

                        yield from _harvest(raw_jobs, plat_name, time_window, plat_source)

        # ── Node 3: LinkedIn Deep-Widen Safety Net (uncapped, last resort) ─
        if len(scored_jobs) < target_matches:
            needed = target_matches - len(scored_jobs)
            yield {"step": "scraping",
                   "message": f"🔍 Deep-widen Net Activated: {needed} short — paginated LinkedIn India search (6 offsets × 24/72h windows)..."}

            # Search LinkedIn India: 24h first, then 72h window if still below target
            for time_window in [24, 72]:
                if len(scored_jobs) >= target_matches:
                    break

                for offset in [0, 10, 20, 30, 40, 50]:
                    if len(scored_jobs) >= target_matches:
                        break

                    for query in search_queries:
                        if abort():
                            yield {"step": "aborted", "message": "Pipeline aborted (client disconnected).",
                                   "data": summary_data(status="aborted")}
                            return
                        if len(scored_jobs) >= target_matches:
                            break

                        yield {"step": "scraping",
                               "message": f"[LinkedIn Fallback] Querying: \"{query}\" (offset={offset}, {time_window}h)..."}
                        try:
                            raw_jobs = fetch_linkedin_jobs(
                                search_query=query,
                                location="India",
                                limit=10,
                                posted_within_hours=time_window,
                                start_offset=offset,
                            )
                        except Exception as e:
                            yield {"step": "scraping", "message": f"⚠️ LinkedIn fallback warning: {e}"}
                            continue

                        yield from _harvest(raw_jobs, "LinkedIn Fallback", time_window, "linkedin")

        # ── Sort and slice top target matches ──────────────────────────────
        scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        final_jobs = scored_jobs[:target_matches]

        yield {"step": "matching",
               "message": f"Scoring complete! Found {len(final_jobs)} qualified unique India AI matches ({threshold}+ threshold) and {len(unscored_jobs)} unscored listings (no real JD — apply link only).",
               "data": {
                   "matched": len(final_jobs),
                   "unscored": len(unscored_jobs),
                   "total_scraped": total_scraped_count,
                   "duplicate_skipped": duplicate_skipped_count,
                   "semantic_filtered": semantic_filtered_count,
                   "platform_breakdown": {k: v for k, v in platform_matched_counts.items() if v > 0},
               }}

        if not final_jobs and not unscored_jobs:
            _log_run(run_start, total_scraped_count, 0, False, False, None, source)
            yield {"step": "complete",
                   "message": "No postings met the threshold in the specified timeframe. Pipeline finished.",
                   "data": summary_data()}
            return

        # ── Save to Database (scored + unscored) ───────────────────────────
        total_saved = len(final_jobs) + len(unscored_jobs)
        yield {"step": "saving",
               "message": f"Saving {total_saved} new listings to database ({len(final_jobs)} scored, {len(unscored_jobs)} unscored)..."}

        with get_db_context() as db:
            for job in final_jobs + unscored_jobs:
                posted_at_val = job.get("posted_at")
                if isinstance(posted_at_val, str) and posted_at_val:
                    try:
                        posted_at_val = dateutil.parser.parse(posted_at_val)
                    except Exception:
                        posted_at_val = None
                elif not posted_at_val:
                    posted_at_val = None

                db.add(Job(
                    job_id=f"job-{uuid.uuid4().hex[:8]}",
                    title=job["title"],
                    company=job["company"],
                    description=job.get("description", "")[:2000],
                    link=job["link"],
                    apply_url=job.get("apply_url", ""),
                    location=job.get("location", ""),
                    source=job.get("source", "aggregated"),
                    posted_at=posted_at_val,
                    match_score=job["match_score"],
                    match_reasoning=job.get("match_reasoning", ""),
                    semantic_score=job.get("semantic_score"),
                    role_type=job.get("role_type", "internship"),
                    work_mode=job.get("work_mode", "onsite"),
                    status="saved",
                ))
            db.commit()

        yield {"step": "saving",
               "message": f"Saved {total_saved} unique listings to database ({len(final_jobs)} scored, {len(unscored_jobs)} unscored — apply link only)."}

        # ── Export CSV (scored + unscored: blank score, honest reasoning) ──
        yield {"step": "csv", "message": "Generating structured CSV report with direct apply links..."}
        csv_filename = f"internships_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = export_jobs_to_csv(final_jobs + unscored_jobs, csv_filename)
        if csv_path:
            yield {"step": "csv",
                   "message": f"CSV report exported: {csv_filename} ({len(final_jobs)} scored, {len(unscored_jobs)} unscored rows)"}

        # ── Email CSV (only when there are qualified matches) ──────────────
        if csv_path and final_jobs:
            if dry_run:
                yield {"step": "email", "message": "🔒 [DRY RUN] Skipping email delivery."}
            else:
                yield {"step": "email",
                       "message": f"Delivering CSV report to {settings.recipient_email} via Gmail OAuth..."}
                email_sent = send_csv_email(csv_path, len(final_jobs))
                if email_sent:
                    yield {"step": "email", "message": f"✅ CSV report delivered to {settings.recipient_email}!"}
                else:
                    yield {"step": "email", "message": "⚠️ Email delivery failed or is not configured."}

        # ── WhatsApp Notification ──────────────────────────────────────────
        if dry_run:
            yield {"step": "whatsapp", "message": "🔒 [DRY RUN] Skipping WhatsApp notification."}
        else:
            yield {"step": "whatsapp", "message": "Sending WhatsApp summary notification..."}
            if settings.whatsapp_from and settings.user_whatsapp_number:
                whatsapp_sent = send_whatsapp_summary(settings.user_whatsapp_number, final_jobs)
                if whatsapp_sent:
                    yield {"step": "whatsapp", "message": "📲 WhatsApp notification sent successfully!"}
                else:
                    yield {"step": "whatsapp", "message": "⚠️ WhatsApp notification failed."}
            else:
                yield {"step": "whatsapp", "message": "WhatsApp notification skipped (not fully configured)."}

        # ── Run Log ────────────────────────────────────────────────────────
        _log_run(run_start, total_scraped_count, len(final_jobs), email_sent,
                 whatsapp_sent, csv_path, source)

        yield {"step": "complete",
               "message": f"Pipeline complete! {len(final_jobs)} qualified matches + {len(unscored_jobs)} unscored listings (no real JD — apply link only) delivered.",
               "data": summary_data()}

    except FileNotFoundError as e:
        yield {"step": "error", "message": str(e), "data": {"status": "error", "message": str(e)}}
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        yield {"step": "error", "message": f"Pipeline error: {str(e)}",
               "data": {"status": "error", "message": f"Pipeline error: {str(e)}"}}
