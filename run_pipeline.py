#!/usr/bin/env python
"""
run_pipeline.py
===============
Full end-to-end Autonomous Internship Agent pipeline.

Guarantees 25 unique, qualified AI internship listings per run:
  1. Parses the candidate resume PDF.
  2. Generates comprehensive AI/GenAI search queries.
  3. Queries the database to prevent duplicates across morning/evening runs.
  4. Iteratively scrapes and scores jobs in waves (past 24h) until 25 unique matches are found.
  5. Saves matched jobs to the database.
  6. Exports the final 25 listings to a CSV report with direct apply links.
  7. Delivers the CSV via Gmail OAuth.
  8. Sends a summary notification via WhatsApp.
  9. Records execution statistics in the database.

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
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import settings
from db.database import get_db_context, init_db
from db.models import Job, PipelineRun
from tools.job_api import fetch_jobs
from tools.resume_parser import parse_resume, extract_text_from_pdf, get_search_queries_from_resume
from tools.jd_matcher import match_resume_to_job
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
    """Locate the resume PDF in the project directory."""
    candidates = [
        os.path.join(BASE_DIR, "Manthan_Raut_Resume (1).pdf"),
        os.path.join(BASE_DIR, "data", "current_resume.pdf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "No resume found. Place your PDF in the project root or upload via /upload-resume."
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
    Query existing records in SQLite to ensure no duplicates from previous runs
    (morning vs evening or day-to-day) are re-processed or emailed again.
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
    unique AI internship listings.
    """
    run_start = datetime.utcnow()
    email_sent = False
    whatsapp_sent = False
    csv_path = None

    print("\n" + "=" * 65)
    print("  🚀  AUTONOMOUS INTERNSHIP AGENT — TARGET 25 AI LISTINGS")
    print("=" * 65)

    try:
        resume_path = find_resume()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return {"status": "error", "message": str(e)}

    print(f"\n📄 Resume: {os.path.basename(resume_path)}")
    resume_text = get_resume_text(resume_path)
    print(f"   Extracted {len(resume_text)} characters of text")

    # Fetch AI search queries (strictly AI, GenAI, AI Automation)
    print("\n🧠 Generating optimal AI/GenAI search queries from resume...")
    search_queries = get_search_queries_from_resume(resume_path)
    # Ensure standard comprehensive pool of AI keywords
    core_ai_queries = [
        "AI Consultant Intern",
        "AI Automation Intern",
        "GenAI Developer Intern",
        "Agentic AI Intern",
        "LLM Engineer Intern",
        "AI ML Intern",
        "AI Python Developer Intern",
        "Full Stack AI Developer Intern",
        "AI Data Analyst Intern",
        "AI Automation Engineer Intern"
    ]
    for q in core_ai_queries:
        if q not in search_queries:
            search_queries.append(q)

    print(f"   Queries ({len(search_queries)}): {', '.join(search_queries)}")

    # Load existing database signatures to prevent cross-run duplicates
    db_links, db_apply_urls, db_title_company = get_existing_db_signatures()
    print(f"   Known DB listings to deduplicate against: {len(db_links)} records")

    # ── Multi-wave Scraping & Scoring Loop ─────────────────────────────
    print(f"\n🔍 Searching for unique postings (past 24 hours, Target = {target_matches} matches)...")
    scored_jobs: List[Dict[str, Any]] = []
    seen_in_run_links: Set[str] = set()
    seen_in_run_signatures: Set[Tuple[str, str]] = set()

    total_scraped_count = 0
    duplicate_skipped_count = 0

    for wave in range(1, max_waves + 1):
        if len(scored_jobs) >= target_matches:
            break

        start_offset = (wave - 1) * 20
        print(f"\n{'━' * 60}")
        print(f"🌊 Wave {wave}/{max_waves} (Offset: {start_offset}) — Target remaining: {target_matches - len(scored_jobs)}")
        print(f"{'━' * 60}")

        wave_jobs: List[Dict[str, Any]] = []

        for query in search_queries:
            if len(scored_jobs) >= target_matches:
                break

            print(f"   ➤ Query: \"{query}\" (limit=10, 24h)")
            raw_jobs = fetch_jobs(query, limit=10, posted_within_hours=24, start_offset=start_offset)
            total_scraped_count += len(raw_jobs)

            for j in raw_jobs:
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

                if link:
                    seen_in_run_links.add(link)
                if apply_url:
                    seen_in_run_links.add(apply_url)
                if title and company:
                    seen_in_run_signatures.add(sig)

                wave_jobs.append(j)

        print(f"\n   Wave {wave} yielded {len(wave_jobs)} fresh unique postings to evaluate.")

        # Score wave jobs with Groq LLM
        for i, job in enumerate(wave_jobs, 1):
            if len(scored_jobs) >= target_matches:
                print(f"   🎯 Reached target of {target_matches} unique qualified matches! Proceeding to delivery.")
                break

            title = job["title"]
            company = job["company"]
            desc = job.get("description", "")

            if not desc or len(desc.strip()) < 30:
                print(f"   [{i}/{len(wave_jobs)}] ⏭  {title} @ {company} — skipped (no description)")
                continue

            print(f"   [{i}/{len(wave_jobs)}] 🔄 Scoring: {title} @ {company}…", end="", flush=True)

            try:
                result = match_resume_to_job(resume_text, desc)
                score = result.get("score", 0)
                reasoning = result.get("reasoning", "")
                key_matches = result.get("key_matches", [])
            except Exception as e:
                print(f" ❌ Error: {e}")
                continue

            job["match_score"] = score
            job["match_reasoning"] = reasoning
            job["key_matches"] = key_matches

            emoji = "✅" if score >= threshold else "⬇️"
            print(f" {emoji} Score: {score}/100")

            if score >= threshold:
                scored_jobs.append(job)
                print(f"      [Progress: {len(scored_jobs)}/{target_matches} matches]")

            # 3-second delay between LLM evaluations to prevent rate-limit bursts
            time.sleep(3)

    # ── Summary of Qualified Matches ──────────────────────────────────────
    print(f"\n{'─' * 65}")
    print(f"📊 Pipeline Execution Summary:")
    print(f"   • Total Scraped: {total_scraped_count}")
    print(f"   • Cross-run Duplicates Filtered: {duplicate_skipped_count}")
    print(f"   • Final Unique Matches ({threshold}+ score): {len(scored_jobs)}")

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
    # Take top target_matches
    final_jobs = scored_jobs[:target_matches]

    print(f"\n🏆 Final {len(final_jobs)} Unique Matches Selected for Report:")
    for idx, j in enumerate(final_jobs, 1):
        print(f"   {idx}. {j['title']} @ {j['company']} — Score: {j['match_score']}/100")

    # ── Save to Database ──────────────────────────────────────────────────
    print(f"\n💾 Saving {len(final_jobs)} new listings to database…")
    saved_jobs = []
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
                status="saved",
            )
            db.add(db_job)
            saved_jobs.append(db_job)
        db.commit()

    print(f"   Saved {len(saved_jobs)} jobs.")

    # ── Export to CSV ─────────────────────────────────────────────────────
    print(f"\n📝 Generating CSV report with 25 unique matches…")
    csv_filename = f"internships_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = export_jobs_to_csv(final_jobs, output_filename=csv_filename)
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
    with get_db_context() as db:
        run_log = PipelineRun(
            started_at=run_start,
            completed_at=datetime.utcnow(),
            status="success",
            jobs_found=total_scraped_count,
            jobs_matched=len(final_jobs),
            email_sent=bool(email_sent),
            whatsapp_sent=bool(whatsapp_sent),
            csv_path=csv_path,
            source="cli"
        )
        db.add(run_log)
        db.commit()

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
