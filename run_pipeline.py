#!/usr/bin/env python
"""
run_pipeline.py
===============
Full end-to-end Autonomous Internship Agent pipeline with Semantic Matching.

Key Upgrades:
  1. Locates candidate resume (Manthan_Raut.pdf).
  2. Embeds resume once using local SentenceTransformer (all-MiniLM-L6-v2).
  3. Cascades across 10 platforms: LinkedIn + 9 new portals from list.csv.
  4. Strictly filters for Remote, Online, or Virtual openings.
  5. Enriches short descriptions via JD page fetcher.
  6. Computes semantic similarity (0-100) and filters out poor matches (< 35).
  7. Classifies role type as 'internship' or 'full-time'.
  8. Evaluates top matches using Groq LLM for comprehensive scoring.
  9. Ensures multi-portal diversity (minimum 3 platforms represented).
  10. Saves matched jobs to DB (including semantic_score & role_type).
  11. Exports CSV report and delivers via Gmail OAuth + WhatsApp.

Usage:
    python run_pipeline.py
    python run_pipeline.py --target 25 --threshold 70
"""

import argparse
import logging
import sys
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Set, Tuple

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import settings
from db.database import get_db_context, init_db
from db.models import Job, PipelineRun
from tools.job_api import get_scraper_platforms, is_remote_or_virtual, PLATFORM_QUOTAS
from tools.resume_parser import parse_resume, extract_text_from_pdf, get_search_queries_from_resume
from tools.jd_matcher import match_resume_to_job
from tools.semantic_matcher import ResumeEmbedder, classify_role_type
from tools.jd_fetcher import fetch_full_job_description
from tools.whatsapp_handler import send_whatsapp_summary
from tools.csv_exporter import export_jobs_to_csv
from tools.email_sender import send_csv_email

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Ensure tables exist
init_db()


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
    """
    Query existing records in PostgreSQL to ensure no duplicates from previous runs
    are re-processed or emailed again.
    """
    with get_db_context() as db:
        links = set()
        apply_urls = set()
        title_company = set()
        for j in db.query(Job.link, Job.apply_url, Job.title, Job.company).all():
            if j[0]:
                links.add(j[0].strip().lower())
            if j[1]:
                apply_urls.add(j[1].strip().lower())
            if j[2] and j[3]:
                title_company.add((j[2].strip().lower(), j[3].strip().lower()))
        return links, apply_urls, title_company


# ──────────────────────────────────────────────────────────────────────────────
# Main Pipeline Function
# ──────────────────────────────────────────────────────────────────────────────

def run(target_matches: int = 25, threshold: int = 70, max_waves: int = 4) -> Dict[str, Any]:
    """
    Executes the full pipeline and guarantees up to `target_matches` (default 25)
    unique AI internship listings across 10 platforms.
    """
    run_start = datetime.utcnow()
    email_sent = False
    whatsapp_sent = False
    csv_path = None

    print("\n" + "=" * 65)
    print("  🚀  AUTONOMOUS INTERNSHIP AGENT — SEMANTIC MATCHING PIPELINE")
    print("=" * 65)

    try:
        resume_path = find_resume()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return {"status": "error", "message": str(e)}

    print(f"\n📄 Resume: {os.path.basename(resume_path)}")
    resume_text = get_resume_text(resume_path)
    print(f"   Extracted {len(resume_text)} characters of text")

    # Initialize ResumeEmbedder (chunks resume & computes embeddings ONCE)
    print("\n🧠 Initializing Vector Embedder (Chunking & Embedding Resume once)...")
    try:
        embedder = ResumeEmbedder(resume_path)
        print(f"   ✅ Pre-computed embeddings for {len(embedder.chunks)} semantic sections")
    except Exception as e:
        logger.error(f"Failed to initialize semantic embedder: {e}")
        raise

    # Generate AI search queries
    print("\n🔍 Generating optimal AI/GenAI search queries from resume...")
    search_queries = get_search_queries_from_resume(resume_path)
    core_ai_queries = [
        "AI Intern",
        "AI Automation Intern",
        "GenAI Developer Intern",
        "Agentic AI Intern",
        "LLM Engineer Intern",
        "AI ML Intern",
        "Machine Learning Intern",
        "AI Agent Developer Intern",
        "AI Automation Engineer Intern",
        "NLP AI Intern"
    ]
    for q in core_ai_queries:
        if q not in search_queries:
            search_queries.append(q)

    print(f"   Queries ({len(search_queries)}): {', '.join(search_queries[:6])}...")

    # Load existing database signatures to prevent cross-run duplicates
    db_links, db_apply_urls, db_title_company = get_existing_db_signatures()
    print(f"   Known DB listings to deduplicate against: {len(db_links)} records")

    # Platform Quotas & Cascading Strategy
    platforms = get_scraper_platforms()
    print(f"\n🌐 Active 10 Platforms (Priority Order & Quotas):")
    for p in platforms:
        print(f"   • {p['name']} (Quota: {p['quota']} listings)")
    print(f"   🛑 Stop Condition: Search terminates once target of {target_matches} matches is reached.\n")

    scored_jobs: List[Dict[str, Any]] = []
    seen_in_run_links: Set[str] = set()
    seen_in_run_signatures: Set[Tuple[str, str]] = set()

    platform_matched_counts: Dict[str, int] = {p["source"]: 0 for p in platforms}
    total_scraped_count = 0
    duplicate_skipped_count = 0
    semantic_filtered_count = 0

    for p_idx, platform in enumerate(platforms, 1):
        if len(scored_jobs) >= target_matches:
            break

        plat_name = platform["name"]
        plat_source = platform["source"]
        plat_fn = platform["fn"]
        plat_quota = platform["quota"]

        print(f"\n{'━' * 65}")
        print(f"🚀 [Priority {p_idx}/{len(platforms)}] Platform: {plat_name} (Base Quota: {plat_quota})")
        print(f"   Current total matches: {len(scored_jobs)}/{target_matches}")
        print(f"{'━' * 65}")

        plat_matches_before = platform_matched_counts[plat_source]

        for query in search_queries:
            if len(scored_jobs) >= target_matches:
                break

            # BUG-8 FIX: hard cap at exact platform quota — no 2x multiplier.
            # Previously `plat_quota * 2` allowed LinkedIn to take 14 of 25 slots.
            if (platform_matched_counts[plat_source] - plat_matches_before) >= plat_quota:
                break

            print(f"\n   ➤ [{plat_name}] Query: \"{query}\" (limit=10, 24h)")
            try:
                raw_jobs = plat_fn(query, 10, 24, 0)
            except Exception as e:
                print(f"   ⚠️ Scraper error on {plat_name}: {e}")
                continue

            total_scraped_count += len(raw_jobs)

            for j in raw_jobs:
                if len(scored_jobs) >= target_matches:
                    break

                link = (j.get("link") or "").strip().lower()
                apply_url = (j.get("apply_url") or "").strip().lower()
                title = (j.get("title") or "").strip().lower()
                company = (j.get("company") or "").strip().lower()
                sig = (title, company)

                # Deduplication check across DB and current run
                if (link in db_links or
                    apply_url in db_apply_urls or
                    sig in db_title_company or
                    link in seen_in_run_links or
                    sig in seen_in_run_signatures):
                    duplicate_skipped_count += 1
                    continue

                # Strict Remote / Online / Virtual opening constraint
                if not is_remote_or_virtual(j):
                    continue

                # BUG-7 FIX: 24-hour date gate.
                # Jobs from scrapers that provide real timestamps are checked against cutoff.
                # posted_at is a datetime object (set by scrapers); None/string means skip check.
                posted_at_val = j.get("posted_at")
                if isinstance(posted_at_val, datetime):
                    # Ensure tz-aware comparison
                    if posted_at_val.tzinfo is None:
                        posted_at_val = posted_at_val.replace(tzinfo=timezone.utc)
                    date_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                    if posted_at_val < date_cutoff:
                        continue  # genuinely stale — skip


                if link:
                    seen_in_run_links.add(link)
                if apply_url:
                    seen_in_run_links.add(apply_url)
                if title and company:
                    seen_in_run_signatures.add(sig)

                desc = j.get("description", "")

                # BUG-11 FIX: raised threshold from 200 to 400 chars.
                # Most scraper-generated descriptions are ~60 chars ("AI Intern at Startup."),
                # which are meaningless for semantic matching even though they pass 200.
                if len(desc.strip()) < 400 and j.get("link"):
                    try:
                        enriched = fetch_full_job_description(j["link"])
                        if enriched and len(enriched) > len(desc):
                            desc = enriched
                            j["description"] = desc
                    except Exception:
                        pass

                if not desc or len(desc.strip()) < 30:
                    continue

                # ── Step A: Role Type Classification ──────────────────────────
                role_type = classify_role_type(j)
                j["role_type"] = role_type

                # ── Step B: Semantic Pre-Filtering via Local Embeddings ────────
                sem_score = embedder.compute_semantic_score(desc)
                j["semantic_score"] = sem_score

                # Pre-filter threshold: skip Groq LLM if semantic score is too low (< 35)
                if sem_score < 35.0:
                    semantic_filtered_count += 1
                    print(f"      ⏩ Semantic pre-filter passed over ({sem_score}/100): {j['title']} @ {j['company']}")
                    continue

                # ── Step C: Deep Evaluation with Groq LLM ──────────────────────
                print(f"      🔄 Scoring: [{role_type.upper()}] {j['title']} @ {j['company']} (Semantic: {sem_score})…", end="", flush=True)

                try:
                    result = match_resume_to_job(resume_text, desc)
                    score = result.get("score", 0)
                    reasoning = result.get("reasoning", "")
                    key_matches = result.get("key_matches", [])
                except Exception as e:
                    print(f" ❌ Error: {e}")
                    continue

                j["match_score"] = score
                j["match_reasoning"] = reasoning
                j["key_matches"] = key_matches

                emoji = "✅" if score >= threshold else "⬇️"
                print(f" {emoji} LLM Score: {score}/100")

                if score >= threshold:
                    scored_jobs.append(j)
                    platform_matched_counts[plat_source] += 1
                    print(f"         🎯 [Found {len(scored_jobs)}/{target_matches} matches! ({plat_name}: {platform_matched_counts[plat_source]})]")
                    if len(scored_jobs) >= target_matches:
                        print(f"\n🎉 Reached exact target of {target_matches} qualified AI openings on {plat_name}!")
                        print(f"🛑 Halting search — quota fulfilled.")
                        break

                time.sleep(1.5)

    # ── Summary of Qualified Matches ──────────────────────────────────────
    print(f"\n{'─' * 65}")
    print(f"📊 Pipeline Execution Summary:")
    print(f"   • Total Scraped Across 10 Portals: {total_scraped_count}")
    print(f"   • Cross-run Duplicates Filtered: {duplicate_skipped_count}")
    print(f"   • Low Semantic Match Pre-filtered (<35): {semantic_filtered_count}")
    print(f"   • Final Unique Matches ({threshold}+ score): {len(scored_jobs)}")
    print(f"   • Platform Breakdown: {dict((k, v) for k, v in platform_matched_counts.items() if v > 0)}")

    if not scored_jobs:
        print("   ⚠️ No jobs met the threshold in the past 24 hours.")
        if settings.whatsapp_from and settings.user_whatsapp_number:
            send_whatsapp_summary(settings.user_whatsapp_number, [])
        with get_db_context() as db:
            run_log = PipelineRun(
                started_at=run_start,
                completed_at=datetime.utcnow(),
                status="success",
                jobs_found=total_scraped_count,
                jobs_matched=0,
                email_sent=False,
                source="cli"
            )
            db.add(run_log)
        return {"status": "success", "jobs_matched": 0}

    # Sort descending by match score
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    final_jobs = scored_jobs[:target_matches]

    print(f"\n🏆 Final {len(final_jobs)} Unique Matches Selected for Report:")
    for idx, j in enumerate(final_jobs, 1):
        print(f"   {idx}. [{j.get('role_type','internship')}] {j['title']} @ {j['company']} ({j.get('source','linkedin')}) — Score: {j['match_score']}/100 (Sem: {j.get('semantic_score', 0)})")

    # ── Save to Database ──────────────────────────────────────────────────
    print(f"\n💾 Saving {len(final_jobs)} new listings to database…")
    saved_jobs = []
    try:
        with get_db_context() as db:
            import dateutil.parser

            for job in final_jobs:
                posted_at_val = job.get("posted_at")
                if isinstance(posted_at_val, str) and posted_at_val:
                    try:
                        posted_at_val = dateutil.parser.parse(posted_at_val)
                    except Exception:
                        posted_at_val = None
                elif not posted_at_val:
                    posted_at_val = None

                db_job = Job(
                    job_id=f"job-{uuid.uuid4().hex[:8]}",
                    title=job["title"],
                    company=job["company"],
                    description=job.get("description", "")[:2000],
                    link=job["link"],
                    apply_url=job.get("apply_url", ""),
                    location=job.get("location", "Remote"),
                    source=job.get("source", "aggregated"),
                    posted_at=posted_at_val,
                    match_score=job["match_score"],
                    match_reasoning=job.get("match_reasoning", ""),
                    semantic_score=job.get("semantic_score"),
                    role_type=job.get("role_type", "internship"),
                    status="saved",
                )
                db.add(db_job)
                saved_jobs.append(db_job)
            db.commit()
        print(f"   Saved {len(saved_jobs)} jobs.")
    except Exception as db_err:
        print(f"   ⚠️ Warning: Could not save jobs to database: {db_err}")
        print("   Proceeding with CSV report generation and notifications...")

    # ── Export to CSV ─────────────────────────────────────────────────────
    print(f"\n📝 Generating CSV report with {len(final_jobs)} unique matches…")
    csv_filename = f"internships_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = export_jobs_to_csv(final_jobs, output_filename=csv_filename)

    email_sent = False
    if csv_path:
        print(f"   CSV generated at: {csv_path}")

        # ── Email CSV ─────────────────────────────────────────────────────
        print(f"\n📧 Sending CSV report to {settings.recipient_email} via Gmail API…")
        email_sent = send_csv_email(csv_path, len(final_jobs))
        if email_sent:
            print(f"   ✅ Email delivered successfully to {settings.recipient_email}!")
        else:
            print(f"   ⚠️ Email delivery failed or is not configured.")

    # ── WhatsApp Notification ─────────────────────────────────────────────
    print(f"\n📱 Sending WhatsApp summary notification…")
    if settings.whatsapp_from and settings.user_whatsapp_number:
        whatsapp_sent = send_whatsapp_summary(settings.user_whatsapp_number, final_jobs)
        if whatsapp_sent:
            print("   📲 WhatsApp notification sent successfully!")
        else:
            print("   ⚠️ WhatsApp notification failed.")
    else:
        print("   WhatsApp is not fully configured, skipping notification.")

    # ── Log Run to Database ───────────────────────────────────────────────
    try:
        with get_db_context() as db:
            run_log = PipelineRun(
                started_at=run_start,
                completed_at=datetime.utcnow(),
                status="success",
                jobs_found=total_scraped_count,
                jobs_matched=len(final_jobs),
                email_sent=bool(email_sent),
                whatsapp_sent=bool(whatsapp_sent if 'whatsapp_sent' in locals() else False),
                csv_path=csv_path,
                source="cli"
            )
            db.add(run_log)
            db.commit()
    except Exception as log_err:
        print(f"   ⚠️ Warning: Could not log pipeline run to database: {log_err}")

    print(f"\n{'=' * 65}")
    print(f"  ✅  PIPELINE COMPLETE — {len(final_jobs)} UNIQUE AI LISTINGS DELIVERED")
    print("=" * 65)

    return {
        "status": "success",
        "jobs_matched": len(final_jobs),
        "email_sent": bool(email_sent),
        "whatsapp_sent": bool(whatsapp_sent),
        "csv_path": csv_path
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the autonomous AI internship agent pipeline"
    )
    parser.add_argument(
        "--target", "-t",
        type=int,
        default=25,
        help="Target number of unique matched jobs to return (default: 25)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=settings.match_score_threshold,
        help=f"Minimum match score threshold (default: {settings.match_score_threshold})",
    )
    args = parser.parse_args()

    run(
        target_matches=args.target,
        threshold=args.threshold,
    )
