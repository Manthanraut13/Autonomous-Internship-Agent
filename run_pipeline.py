#!/usr/bin/env python
"""
run_pipeline.py
===============
Full end-to-end Autonomous Internship Agent pipeline.

Steps:
  1. Parse the resume PDF
  2. Generate search queries based on the resume
  3. Fetch jobs from JSearch, LinkedIn, Arbeitnow, etc. (within last 24h)
  4. Score each job against the resume using the Groq LLM
  5. Save matched jobs to the database
  6. Generate a CSV report
  7. Email the CSV report to the user
  8. Send a WhatsApp notification (one-way)

Usage:
    python run_pipeline.py
    python run_pipeline.py --limit 10
"""

import argparse
import logging
import sys
import os
import time
import uuid
from typing import List, Dict, Any

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import settings
from db.database import get_db_context
from db.models import Job
from tools.job_api import fetch_jobs
from tools.resume_parser import parse_resume, extract_text_from_pdf, get_search_queries_from_resume
from tools.jd_matcher import match_resume_to_job
from tools.whatsapp_handler import send_whatsapp_summary
from tools.csv_exporter import export_jobs_to_csv
from tools.email_sender import send_csv_email

# Force UTF-8 output on Windows (prevents cp1252 emoji crashes)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


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


# ──────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run(limit: int, threshold: int):
    """Execute the full pipeline."""

    # ── 1. Parse resume ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  🚀  AUTONOMOUS INTERNSHIP AGENT — FULL PIPELINE")
    print("=" * 60)

    try:
        resume_path = find_resume()
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    print(f"\n📄 Resume: {os.path.basename(resume_path)}")
    resume_text = get_resume_text(resume_path)
    print(f"   Extracted {len(resume_text)} characters of text")
    
    print("\n🧠 Generating optimal search queries from resume...")
    search_queries = get_search_queries_from_resume(resume_path)
    if not search_queries:
        search_queries = ["software engineer intern", "python developer intern"]
    
    print(f"   Queries: {', '.join(search_queries)}")

    # ── 2. Fetch real jobs ───────────────────────────────────────────────
    print(f"\n🔍 Searching for jobs (last 24 hours)...")
    all_jobs = []
    seen_urls = set()
    
    # We distribute the limit across the queries
    query_limit = max(1, limit // len(search_queries))
    
    for query in search_queries:
        print(f"   ➤ Fetching for: \"{query}\" (limit={query_limit})")
        jobs = fetch_jobs(query, limit=query_limit, posted_within_hours=24)
        for j in jobs:
            link = j.get("link", "")
            if link not in seen_urls:
                seen_urls.add(link)
                all_jobs.append(j)
                
    if not all_jobs:
        print("❌ No jobs found in the last 24 hours.")
        return

    print(f"\n   Total unique jobs found: {len(all_jobs)}")

    # ── 3. Score each job against the resume ──────────────────────────────
    print(f"\n🤖 Matching resume against {len(all_jobs)} jobs using Groq LLM…")
    print(f"   Model: {settings.groq_model}")
    print(f"   Threshold: {threshold}/100\n")

    scored_jobs = []
    
    for i, job in enumerate(all_jobs, 1):
        title = job["title"]
        company = job["company"]
        desc = job.get("description", "")

        if not desc or len(desc.strip()) < 30:
            print(f"   [{i}/{len(all_jobs)}] ⏭  {title} @ {company} — skipped (no description)")
            continue

        print(f"   [{i}/{len(all_jobs)}] 🔄 Scoring: {title} @ {company}…", end="", flush=True)

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

        # Delay to respect Groq free-tier rate limits (RPM/TPM)
        time.sleep(3)

    # ── 4. Summary of matches ─────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"📊 Matching complete: {len(scored_jobs)}/{len(all_jobs)} jobs above threshold ({threshold})")

    if not scored_jobs:
        print("   No jobs met the threshold.")
        # Send empty notification anyway
        if settings.whatsapp_from and settings.user_whatsapp_number:
            send_whatsapp_summary(settings.user_whatsapp_number, [])
        return

    # Sort scored jobs descending
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    
    for j in scored_jobs:
        print(f"   ✅ {j['title']} @ {j['company']} — Score: {j['match_score']}")

    # ── 5. Save to DB ─────────────────────────────────────────────────────
    print(f"\n💾 Saving {len(scored_jobs)} matched jobs to database…")
    saved_jobs = []
    with get_db_context() as db:
        from datetime import datetime
        import dateutil.parser
        
        for job in scored_jobs:
            posted_at_val = job.get("posted_at")
            if isinstance(posted_at_val, str) and posted_at_val:
                try:
                    posted_at_val = dateutil.parser.parse(posted_at_val)
                except Exception:
                    try:
                        posted_at_val = datetime.fromisoformat(posted_at_val.replace("Z", "+00:00"))
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
                location=job.get("location", ""),
                source=job.get("source", "aggregated"),
                posted_at=posted_at_val,
                match_score=job["match_score"],
                match_reasoning=job.get("match_reasoning", ""),
                status="saved", # We are no longer interactive
            )
            db.add(db_job)
            db.flush()
            saved_jobs.append(db_job)
        db.commit()

    print(f"   Saved {len(saved_jobs)} jobs.")

    # ── 6. Export to CSV ──────────────────────────────────────────────────
    print(f"\n📝 Generating CSV report...")
    csv_filename = f"internships_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = export_jobs_to_csv(scored_jobs, output_filename=csv_filename)
    if csv_path:
        print(f"   CSV generated at: {csv_path}")
    
        # ── 7. Email CSV ──────────────────────────────────────────────────────
        print(f"\n📧 Sending CSV report via Email...")
        if send_csv_email(csv_path, len(scored_jobs)):
            print(f"   Email sent successfully to {settings.recipient_email}!")
        else:
            print(f"   ⚠️ Email sending failed or is not configured.")

    # ── 8. WhatsApp Notification ──────────────────────────────────────────
    print(f"\n📱 Sending WhatsApp Notification...")
    if settings.whatsapp_from and settings.user_whatsapp_number:
        if send_whatsapp_summary(settings.user_whatsapp_number, scored_jobs):
            print("   📲 WhatsApp notification sent successfully!")
        else:
            print("   ⚠️ WhatsApp notification failed.")
    else:
        print("   WhatsApp is not fully configured, skipping notification.")

    # ── Done ───────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  ✅  PIPELINE COMPLETE")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full internship agent pipeline"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Max number of jobs to fetch per query (default: 20)",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=settings.match_score_threshold,
        help=f"Minimum match score (default: {settings.match_score_threshold})",
    )
    args = parser.parse_args()

    run(
        limit=args.limit,
        threshold=args.threshold,
    )
