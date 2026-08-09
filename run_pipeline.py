#!/usr/bin/env python
"""
run_pipeline.py
===============
Full end-to-end Autonomous Internship Agent pipeline.

Steps:
  1. Parse the resume PDF
  2. Fetch real jobs from the Remotive API
  3. Score each job against the resume using the Groq LLM
  4. Filter jobs above the match-score threshold
  5. Save matched jobs to the database
  6. Send WhatsApp approval messages for each match
  7. Print a summary

After running this script, reply "yes" or "no" on WhatsApp.
The FastAPI server's /webhook/whatsapp endpoint will handle the response.

Usage:
    python run_pipeline.py
    python run_pipeline.py --query "machine learning intern" --limit 8
"""

import argparse
import logging
import sys
import os
import time

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import settings
from db.database import get_db_context
from db.models import Job, WhatsAppResponse
from tools.job_api import fetch_jobs
from tools.resume_parser import parse_resume, extract_text_from_pdf
from tools.jd_matcher import match_resume_to_job
from tools.whatsapp_handler import send_whatsapp_approval

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
        # Fallback: use the structured parser and join sections
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

def run(search_query: str, limit: int, threshold: int):
    """Execute the full pipeline."""

    # ── 1. Parse resume ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  🚀  AUTONOMOUS INTERNSHIP AGENT — FULL PIPELINE")
    print("=" * 60)

    resume_path = find_resume()
    print(f"\n📄 Resume: {os.path.basename(resume_path)}")
    resume_text = get_resume_text(resume_path)
    print(f"   Extracted {len(resume_text)} characters of text")

    # Show parsed skills for context
    parsed = parse_resume(resume_path)
    if parsed.get("skills"):
        print(f"   Skills found: {', '.join(parsed['skills'][:10])}")

    # ── 2. Fetch real jobs ───────────────────────────────────────────────
    print(f"\n🔍 Searching for: \"{search_query}\" (limit={limit})")
    jobs = fetch_jobs(search_query, limit=limit)

    if not jobs:
        print("❌ No jobs found. Try a different search query.")
        return

    print(f"   Found {len(jobs)} job listings\n")
    for i, j in enumerate(jobs, 1):
        print(f"   {i}. {j['title']} @ {j['company']} ({j['location']})")

    # ── 3. Score each job against the resume ──────────────────────────────
    print(f"\n🤖 Matching resume against {len(jobs)} jobs using Groq LLM…")
    print(f"   Model: {settings.groq_model}")
    print(f"   Threshold: {threshold}/100\n")

    scored_jobs = []
    for i, job in enumerate(jobs, 1):
        title = job["title"]
        company = job["company"]
        desc = job.get("description", "")

        if not desc or len(desc.strip()) < 30:
            print(f"   [{i}/{len(jobs)}] ⏭  {title} @ {company} — skipped (no description)")
            continue

        print(f"   [{i}/{len(jobs)}] 🔄 Scoring: {title} @ {company}…", end="", flush=True)

        try:
            result = match_resume_to_job(resume_text, desc)
            score = result.get("score", 0)
            reasoning = result.get("reasoning", "")
            key_matches = result.get("key_matches", [])
            gaps = result.get("gaps", [])
        except Exception as e:
            print(f" ❌ Error: {e}")
            continue

        job["match_score"] = score
        job["match_reasoning"] = reasoning
        job["key_matches"] = key_matches
        job["gaps"] = gaps

        emoji = "✅" if score >= threshold else "⬇️"
        print(f" {emoji} Score: {score}/100")

        if score >= threshold:
            scored_jobs.append(job)

        # Delay to respect Groq free-tier rate limits (RPM/TPM)
        time.sleep(3)

    # ── 4. Summary of matches ─────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"📊 Matching complete: {len(scored_jobs)}/{len(jobs)} jobs above threshold ({threshold})")

    if not scored_jobs:
        print("   No jobs met the threshold. Try lowering it or using a different query.")
        print("   Tip: python run_pipeline.py --query \"python developer\" --threshold 50")
        return

    for j in scored_jobs:
        print(f"   ✅ {j['title']} @ {j['company']} — Score: {j['match_score']}")
        if j.get("key_matches"):
            print(f"      Matches: {', '.join(j['key_matches'][:3])}")

    # ── 5. Save to DB & Sequential 1-by-1 WhatsApp Dispatch ─────────────
    print(f"\n💾 Saving {len(scored_jobs)} matched jobs to database…")

    import uuid

    saved_jobs = []
    with get_db_context() as db:
        for job in scored_jobs:
            db_job = Job(
                job_id=f"remotive-{uuid.uuid4().hex[:8]}",
                title=job["title"],
                company=job["company"],
                description=job.get("description", "")[:2000],
                link=job["link"],
                source=job.get("source", "remotive"),
                match_score=job["match_score"],
                match_reasoning=job.get("match_reasoning", ""),
                status="pending",
            )
            db.add(db_job)
            db.flush()
            saved_jobs.append(db_job)

        db.commit()

    print(f"   Saved {len(saved_jobs)} jobs with status 'pending'.")

    # Check if there is already an active job waiting for user response on WhatsApp
    with get_db_context() as db:
        active_waiting = (
            db.query(WhatsAppResponse)
            .filter(WhatsAppResponse.user_approval.is_(None))
            .first()
        )

        if active_waiting:
            active_job = db.query(Job).filter(Job.id == active_waiting.job_id).first()
            job_title = active_job.title if active_job else f"#{active_waiting.job_id}"
            print(f"\n📱 Active prompt already waiting for response: '{job_title}'")
            print("   Queued new jobs in database. The next prompt will auto-dispatch when you respond!")
        else:
            # Pick the first pending job to send to WhatsApp
            first_job = (
                db.query(Job)
                .filter(Job.status == "pending")
                .order_by(Job.id.asc())
                .first()
            )
            if first_job:
                print(f"\n📱 Dispatching 1st job prompt to WhatsApp: '{first_job.title}' @ {first_job.company}…")
                try:
                    sid = send_whatsapp_approval(
                        phone=settings.user_whatsapp_number,
                        job_title=first_job.title,
                        company=first_job.company,
                        match_score=first_job.match_score or 0.0,
                        job_link=first_job.link,
                    )
                    if sid:
                        wa_record = WhatsAppResponse(
                            job_id=first_job.id,
                            sent_message_sid=sid,
                        )
                        db.add(wa_record)
                        db.commit()
                        print(f"   📲 WhatsApp prompt sent! (SID: {sid[:16]}…)")
                    else:
                        print(f"   ⚠️  WhatsApp send failed for '{first_job.title}'")
                except Exception as e:
                    print(f"   ⚠️  WhatsApp error: {e}")

    # ── 6. Done ───────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  ✅  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\n  📊 Jobs fetched   : {len(jobs)}")
    print(f"  🎯 Above threshold: {len(scored_jobs)}")
    print(f"  📱 WhatsApp sent  : {len(scored_jobs)}")
    print(f"\n  👉 Open WhatsApp and reply 'yes' or 'no' to each message.")
    print(f"  👉 The webhook at /webhook/whatsapp will process your replies.")
    print(f"  👉 Check status at http://127.0.0.1:8000/status\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the full internship agent pipeline"
    )
    parser.add_argument(
        "--query", "-q",
        default="software engineer",
        help="Job search query (default: 'software engineer')",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Max number of jobs to fetch (default: 10)",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=settings.match_score_threshold,
        help=f"Minimum match score to send approval (default: {settings.match_score_threshold})",
    )
    args = parser.parse_args()

    run(
        search_query=args.query,
        limit=args.limit,
        threshold=args.threshold,
    )
