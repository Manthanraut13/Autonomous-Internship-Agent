"""
main.py
-------
FastAPI application for the Autonomous Internship Agent.
Serves the React dashboard, provides secure CRM APIs with JWT-like HMAC auth,
runs background 9 AM & 9 PM cron schedules, and streams pipeline execution
in real-time via Server-Sent Events (SSE).
"""

import os
import sys
import json
import time
import uuid
import hmac
import base64
import hashlib
import secrets
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator, List, Set, Tuple

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from db.database import get_db, get_db_context, init_db
from db.models import Job, PipelineRun

# Ensure project root is on path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger(__name__)

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Initialize database tables
init_db()

# --------------------------------------------------------------------------- #
# Security & Token Authentication (HMAC-SHA256)                               #
# --------------------------------------------------------------------------- #

def create_access_token(username: str, expires_in_seconds: int = 86400 * 7) -> str:
    """Creates a signed HMAC-SHA256 auth token valid for 7 days."""
    payload = {
        "sub": username,
        "exp": int(time.time()) + expires_in_seconds,
        "iat": int(time.time()),
        "nonce": secrets.token_hex(8)
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    
    signature = hmac.new(
        settings.auth_secret_key.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"


def verify_access_token(token: str) -> Optional[str]:
    """Verifies signature and expiration of an access token."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, signature = token.rsplit(".", 1)
        expected_sig = hmac.new(
            settings.auth_secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not secrets.compare_digest(signature, expected_sig):
            return None
            
        # Add padding back if necessary
        padded_b64 = payload_b64 + '=' * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload.get("sub")
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


async def require_admin(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> str:
    """
    Dependency requiring a valid authorization token.
    Accepts Bearer token in Authorization header or ?token= query param (for SSE).
    """
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:].strip()
    elif token:
        raw_token = token.strip()

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")

    user = verify_access_token(raw_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    return user


# --------------------------------------------------------------------------- #
# Background Cron Scheduler (9:00 AM & 9:00 PM)                                #
# --------------------------------------------------------------------------- #
scheduler = AsyncIOScheduler()

async def scheduled_pipeline_execution():
    """Triggered by FastAPI AsyncIOScheduler at 9:00 AM & 9:00 PM daily."""
    logger.info("⏰ [APScheduler] Triggering automatic 9 AM/9 PM pipeline run...")
    try:
        from run_pipeline import run as execute_pipeline
        res = await asyncio.to_thread(execute_pipeline, target_matches=25, threshold=settings.match_score_threshold)
        logger.info(f"✅ [APScheduler] Scheduled pipeline run completed: {res}")
    except Exception as exc:
        logger.error(f"❌ [APScheduler] Scheduled pipeline execution failed: {exc}", exc_info=True)


app = FastAPI(
    title="Autonomous Internship Agent API",
    description="Secure Dashboard API, Cron Scheduler, and live pipeline streaming for AI internship matching.",
    version="2.3.0"
)

@app.on_event("startup")
async def startup_event():
    """Start background cron scheduler on application startup."""
    try:
        scheduler.add_job(
            scheduled_pipeline_execution,
            trigger=CronTrigger(hour=9, minute=0),
            id="morning_run",
            name="Morning Run (09:00 AM)",
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_pipeline_execution,
            trigger=CronTrigger(hour=21, minute=0),
            id="evening_run",
            name="Evening Run (09:00 PM)",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("📅 APScheduler started inside FastAPI (Runs scheduled at 09:00 AM and 09:00 PM).")
    except Exception as e:
        logger.warning(f"Could not start background scheduler: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown background scheduler cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("📅 APScheduler stopped.")


# CORS middleware — vuln-0003 fix: explicit origin allowlist, no wildcard
_cors_origins = settings.cors_allowed_origins if settings.cors_allowed_origins else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,               # Env-driven allowlist (no wildcard)
    allow_credentials=bool(_cors_origins),      # Only allow credentials with explicit origins
    allow_methods=["GET", "POST", "OPTIONS"],   # Minimum required methods
    allow_headers=["Authorization", "Content-Type"],  # Minimum required headers
)

# Mount compiled React CRM frontend if dist exists
dist_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
assets_dir = os.path.join(dist_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    index_file = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Autonomous Internship Agent API running. Build frontend with 'npm run build' inside frontend/ to view dashboard."}


# --------------------------------------------------------------------------- #
# Authentication Endpoints                                                     #
# --------------------------------------------------------------------------- #

@app.post("/api/auth/login")
async def login(credentials: Dict[str, str]):
    username = credentials.get("username", "").strip()
    password = credentials.get("password", "").strip()

    valid_user = secrets.compare_digest(username, settings.admin_username)
    valid_pass = secrets.compare_digest(password, settings.admin_password)

    if not (valid_user and valid_pass):
        logger.warning(f"Failed login attempt for user: '{username}'")
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_access_token(username)
    logger.info(f"Successful login for user: '{username}'")
    return {
        "status": "success",
        "token": token,
        "username": username,
        "message": "Authentication successful"
    }


@app.get("/api/auth/me")
async def get_current_user_profile(user: str = Depends(require_admin)):
    return {
        "status": "success",
        "authenticated": True,
        "username": user
    }


@app.post("/upload-resume")
@app.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    admin: str = Depends(require_admin)
) -> Dict[str, str]:
    """
    Secure resume upload with defense-in-depth validation (vuln-0005 fix):
    1. File size limit (5 MB)
    2. Extension whitelist
    3. Magic bytes / content validation
    4. Path traversal protection
    """
    # --- 1. Extension whitelist ---
    filename_lower = (file.filename or "").lower()
    if not filename_lower.endswith(('.pdf', '.txt')):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed.")

    # --- 2. Read with size limit (5 MB) ---
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents) / (1024*1024):.1f} MB). Maximum allowed: 5 MB."
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # --- 3. Content / magic bytes validation ---
    if filename_lower.endswith('.pdf'):
        # PDF files must start with the %PDF- magic header
        if not contents[:5] == b'%PDF-':
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file: content does not match PDF format (missing %PDF- header)."
            )
        target_name = "current_resume.pdf"
    else:
        # TXT files must be valid UTF-8
        try:
            contents.decode('utf-8')
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Invalid text file: content is not valid UTF-8 encoded text."
            )
        target_name = "current_resume.txt"

    # --- 4. Path traversal protection ---
    upload_dir = os.path.abspath("data")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.normpath(os.path.join(upload_dir, target_name))
    if not file_path.startswith(upload_dir):
        raise HTTPException(status_code=400, detail="Invalid file path detected.")

    # --- 5. Write validated content ---
    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Error saving resume: {e}")
        raise HTTPException(status_code=500, detail="Failed to save resume.")

    logger.info(f"Resume uploaded: {target_name} ({len(contents)} bytes)")
    return {"status": "success", "message": f"Resume uploaded successfully ({len(contents) / 1024:.1f} KB)."}


# --------------------------------------------------------------------------- #
# Secure CRM Dashboard APIs                                                    #
# --------------------------------------------------------------------------- #

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    all_jobs = db.query(Job).all()
    total_jobs = len(all_jobs)
    saved_count = sum(1 for j in all_jobs if j.status == "saved")
    applied_count = sum(1 for j in all_jobs if j.status == "applied")
    rejected_count = sum(1 for j in all_jobs if j.status in ["rejected", "not_applied"])

    emailed_runs_count = db.query(PipelineRun).filter(PipelineRun.email_sent == True).count()

    scores = [j.match_score for j in all_jobs if j.match_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    sources_count: Dict[str, int] = {}
    for j in all_jobs:
        src = j.source or "other"
        sources_count[src] = sources_count.get(src, 0) + 1

    recent_jobs = db.query(Job).order_by(Job.updated_at.desc()).limit(10).all()
    activity_list = [{
        "id": j.id, "title": j.title, "company": j.company,
        "status": j.status, "match_score": j.match_score,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    } for j in recent_jobs]

    return {
        "total_jobs": total_jobs,
        "saved_count": saved_count,
        "applied_count": applied_count,
        "rejected_count": rejected_count,
        "emailed_count": emailed_runs_count,
        "avg_match_score": avg_score,
        "sources_distribution": sources_count,
        "recent_activity": activity_list,
    }


@app.get("/api/dashboard/jobs")
async def get_dashboard_jobs(
    status: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc",
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    query = db.query(Job)
    if status and status != "all":
        if status in ["rejected", "not_applied"]:
            query = query.filter(Job.status.in_(["rejected", "not_applied"]))
        else:
            query = query.filter(Job.status == status)
    if source and source != "all":
        query = query.filter(Job.source == source)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Job.title.ilike(search_fmt)) | (Job.company.ilike(search_fmt))
        )
    if sort_by == "match_score":
        query = query.order_by(Job.match_score.desc() if order == "desc" else Job.match_score.asc())
    else:
        query = query.order_by(Job.id.desc() if order == "desc" else Job.id.asc())

    jobs = query.all()
    results = [{
        "id": j.id, "job_id": j.job_id, "title": j.title,
        "company": j.company, "description": j.description,
        "link": j.link, "apply_url": j.apply_url or "",
        "location": j.location or "", "source": j.source,
        "posted_at": j.posted_at.isoformat() if j.posted_at else None,
        "scraped_at": j.scraped_at.isoformat() if j.scraped_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        "match_score": j.match_score, "match_reasoning": j.match_reasoning,
        "status": j.status,
    } for j in jobs]
    return {"total": len(results), "jobs": results}


@app.post("/api/dashboard/jobs/{job_id}/action")
async def execute_job_action(
    job_id: int,
    payload: Dict[str, str],
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    action = payload.get("action")
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if action == "delete":
        db.delete(job)
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} deleted."}

    elif action == "mark_applied":
        job.status = "applied"
        job.updated_at = datetime.utcnow()
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} marked as applied."}

    elif action in ["mark_not_applied", "reject"]:
        job.status = "rejected"
        job.updated_at = datetime.utcnow()
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} marked as not applied."}

    elif action in ["mark_saved", "restore"]:
        job.status = "saved"
        job.updated_at = datetime.utcnow()
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} moved back to Inbox."}

    raise HTTPException(status_code=400, detail=f"Invalid action '{action}'.")


@app.get("/api/dashboard/settings")
async def get_agent_settings(admin: str = Depends(require_admin)) -> Dict[str, Any]:
    sched_jobs = []
    if scheduler.running:
        for j in scheduler.get_jobs():
            sched_jobs.append({
                "id": j.id,
                "name": j.name,
                "next_run": j.next_run_time.isoformat() if j.next_run_time else None
            })

    return {
        "groq_model": settings.groq_model,
        "match_score_threshold": settings.match_score_threshold,
        "user_whatsapp_number": settings.user_whatsapp_number,
        "twilio_phone_number": settings.twilio_phone_number,
        "job_sources": settings.job_sources,
        "recipient_email": settings.recipient_email,
        "candidate_name": settings.candidate_name,
        "candidate_email": settings.candidate_email,
        "cron_schedule": {
            "active": scheduler.running,
            "morning": "09:00 AM",
            "evening": "09:00 PM",
            "jobs": sched_jobs
        }
    }


# --------------------------------------------------------------------------- #
# SSE Pipeline Execution — streams each step with authentication             #
# --------------------------------------------------------------------------- #

@app.get("/api/pipeline/stream")
async def stream_pipeline(
    request: Request,
    target: int = 25,
    threshold: int = 70,
    admin: str = Depends(require_admin)
):
    """
    Server-Sent Events endpoint that runs the multi-wave deduplicated pipeline inline
    and streams real-time feedback. Protected with require_admin.
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        run_start = datetime.utcnow()
        email_sent = False
        whatsapp_sent = False
        csv_path = None
        scored_jobs: List[Dict[str, Any]] = []

        def evt(step: str, message: str, data: Any = None) -> dict:
            payload = {"step": step, "message": message, "timestamp": datetime.utcnow().isoformat()}
            if data is not None:
                payload["data"] = data
            return {"event": "pipeline", "data": json.dumps(payload)}

        try:
            # ── Step 1: Parse resume ─────────────────────────────────────
            yield evt("resume", "Locating and parsing candidate resume...")
            await asyncio.sleep(0.1)

            from tools.resume_parser import extract_text_from_pdf, get_search_queries_from_resume

            resume_path = None
            for candidate in [
                os.path.join(BASE_DIR, "Manthan_Raut_Resume (1).pdf"),
                os.path.join(BASE_DIR, "data", "current_resume.pdf"),
            ]:
                if os.path.isfile(candidate):
                    resume_path = candidate
                    break

            if not resume_path:
                yield evt("error", "No resume found. Place your PDF in the project root.")
                return

            resume_text = extract_text_from_pdf(resume_path)
            yield evt("resume", f"Resume loaded: {os.path.basename(resume_path)} ({len(resume_text)} chars)")
            await asyncio.sleep(0.1)

            # ── Step 2: Generate search queries ──────────────────────────
            yield evt("queries", "Generating AI, GenAI & Automation search queries...")
            await asyncio.sleep(0.1)

            search_queries = get_search_queries_from_resume(resume_path)
            core_ai_queries = [
                "AI Intern", "AI Automation Intern", "GenAI Developer Intern",
                "Agentic AI Intern", "LLM Engineer Intern", "AI ML Intern",
                "Machine Learning Intern", "AI Agent Developer Intern",
                "AI Automation Engineer Intern", "NLP AI Intern"
            ]
            for q in core_ai_queries:
                if q not in search_queries:
                    search_queries.append(q)

            yield evt("queries", f"Active AI Queries ({len(search_queries)}): {', '.join(search_queries[:5])}...", search_queries)
            await asyncio.sleep(0.1)

            # ── Step 3: Load existing DB signatures to prevent duplicates ─
            with get_db_context() as db:
                db_links = set(r[0].strip().lower() for r in db.query(Job.link).all() if r[0])
                db_apply_urls = set(r[0].strip().lower() for r in db.query(Job.apply_url).all() if r[0])
                db_signatures = set((r[0].strip().lower(), r[1].strip().lower()) for r in db.query(Job.title, Job.company).all() if r[0] and r[1])

            # ── Step 4: Platform Priority Scraping & Immediate Evaluation ─
            from tools.job_api import get_scraper_platforms
            from tools.jd_matcher import match_resume_to_job

            seen_in_run_links: Set[str] = set()
            seen_in_run_signatures: Set[Tuple[str, str]] = set()
            total_scraped_count = 0
            platforms = get_scraper_platforms()

            yield evt("scraping", f"Starting priority search (Target: {target} qualified AI internship openings)...")
            await asyncio.sleep(0.1)

            for p_idx, platform in enumerate(platforms, 1):
                if len(scored_jobs) >= target:
                    break

                plat_name = platform["name"]
                plat_fn = platform["fn"]

                yield evt("scraping", f"🚀 [Priority {p_idx}/{len(platforms)}] Searching {plat_name} (Remaining: {target - len(scored_jobs)} matches)...")
                await asyncio.sleep(0.1)

                for query in search_queries:
                    if await request.is_disconnected():
                        return
                    if len(scored_jobs) >= target:
                        break

                    yield evt("scraping", f"[{plat_name}] Fetching: \"{query}\" (24h)...")
                    try:
                        raw_jobs = await asyncio.to_thread(plat_fn, query, 10, 24, 0)
                    except Exception as e:
                        yield evt("scraping", f"⚠️ Scraper warning on {plat_name}: {e}")
                        continue

                    total_scraped_count += len(raw_jobs)

                    for j in raw_jobs:
                        if await request.is_disconnected():
                            return
                        if len(scored_jobs) >= target:
                            break

                        link = (j.get("link") or "").strip().lower()
                        apply_url = (j.get("apply_url") or "").strip().lower()
                        title = (j.get("title") or "").strip().lower()
                        company = (j.get("company") or "").strip().lower()
                        sig = (title, company)

                        if (link in db_links or
                            apply_url in db_apply_urls or
                            sig in db_signatures or
                            link in seen_in_run_links or
                            sig in seen_in_run_signatures):
                            continue

                        if link: seen_in_run_links.add(link)
                        if apply_url: seen_in_run_links.add(apply_url)
                        if title and company: seen_in_run_signatures.add(sig)

                        desc = j.get("description", "")
                        if not desc or len(desc.strip()) < 30:
                            continue

                        yield evt("matching", f"[{len(scored_jobs)}/{target} Found] 🔄 Scoring: {j['title']} @ {j['company']}...")

                        try:
                            result = await asyncio.to_thread(match_resume_to_job, resume_text, desc)
                            score = result.get("score", 0)
                            reasoning = result.get("reasoning", "")
                            key_matches = result.get("key_matches", [])
                        except Exception as e:
                            yield evt("matching", f"❌ Error scoring {j['title']}: {e}")
                            continue

                        j["match_score"] = score
                        j["match_reasoning"] = reasoning
                        j["key_matches"] = key_matches

                        emoji = "✅" if score >= threshold else "⬇️"
                        yield evt("matching", f"[{len(scored_jobs)+1}/{target}] {emoji} {j['title']} @ {j['company']} → {score}/100",
                                  {"title": j["title"], "company": j["company"], "score": score})

                        if score >= threshold:
                            scored_jobs.append(j)
                            if len(scored_jobs) >= target:
                                yield evt("matching", f"🎉 Reached exact target of {target} qualified AI internship openings on {plat_name}! Halting search.")
                                break

                        await asyncio.sleep(1.5)

                    await asyncio.sleep(0.05)

            # Sort and slice top target matches
            scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            final_jobs = scored_jobs[:target]

            yield evt("matching", f"Scoring complete! Found {len(final_jobs)} qualified unique AI matches ({threshold}+ threshold).",
                      {"matched": len(final_jobs), "total_scraped": total_scraped_count})
            await asyncio.sleep(0.1)

            if not final_jobs:
                yield evt("complete", "No postings met the threshold in the last 24h. Pipeline finished.", {"matched": 0})
                with get_db_context() as db:
                    run_log = PipelineRun(
                        started_at=run_start,
                        completed_at=datetime.utcnow(),
                        status="success",
                        jobs_found=total_scraped_count,
                        jobs_matched=0,
                        email_sent=False,
                        source="dashboard"
                    )
                    db.add(run_log)
                return

            # ── Step 5: Save to Database ─────────────────────────────────
            yield evt("saving", f"Saving {len(final_jobs)} new listings to SQLite...")
            await asyncio.sleep(0.1)

            import dateutil.parser as dp

            with get_db_context() as db:
                for job in final_jobs:
                    posted_at_val = job.get("posted_at")
                    if isinstance(posted_at_val, str) and posted_at_val:
                        try: posted_at_val = dp.parse(posted_at_val)
                        except Exception: posted_at_val = None
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
                db.commit()

            yield evt("saving", f"Saved {len(final_jobs)} unique listings to database.")
            await asyncio.sleep(0.1)

            # ── Step 6: Export CSV ───────────────────────────────────────
            yield evt("csv", "Generating structured CSV report with direct apply links...")
            await asyncio.sleep(0.1)

            from tools.csv_exporter import export_jobs_to_csv

            csv_filename = f"internships_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            csv_path = await asyncio.to_thread(export_jobs_to_csv, final_jobs, csv_filename)

            if csv_path:
                yield evt("csv", f"CSV report exported: {csv_filename}")
            await asyncio.sleep(0.1)

            # ── Step 7: Email CSV ────────────────────────────────────────
            if csv_path:
                yield evt("email", f"Delivering CSV report to {settings.recipient_email} via Gmail OAuth...")
                await asyncio.sleep(0.1)

                from tools.email_sender import send_csv_email

                email_sent = await asyncio.to_thread(send_csv_email, csv_path, len(final_jobs))
                if email_sent:
                    yield evt("email", f"✅ CSV report delivered to {settings.recipient_email}!")
                else:
                    yield evt("email", "⚠️ Email delivery failed or is not configured.")
                await asyncio.sleep(0.1)

            # ── Step 8: WhatsApp Notification ────────────────────────────
            yield evt("whatsapp", "Sending WhatsApp summary notification...")
            await asyncio.sleep(0.1)

            if settings.whatsapp_from and settings.user_whatsapp_number:
                from tools.whatsapp_handler import send_whatsapp_summary
                whatsapp_sent = await asyncio.to_thread(send_whatsapp_summary, settings.user_whatsapp_number, final_jobs)
                if whatsapp_sent:
                    yield evt("whatsapp", "📲 WhatsApp notification sent successfully!")
                else:
                    yield evt("whatsapp", "⚠️ WhatsApp notification failed.")
            else:
                yield evt("whatsapp", "WhatsApp notification skipped (not fully configured).")
            await asyncio.sleep(0.1)

            # ── Step 9: Save Run Log ─────────────────────────────────────
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
                    source="dashboard"
                )
                db.add(run_log)
                db.commit()

            # ── Complete ─────────────────────────────────────────────────
            yield evt("complete", f"Pipeline complete! {len(final_jobs)} unique AI listings delivered.",
                      {"matched": len(final_jobs), "total_scraped": total_scraped_count})

        except Exception as e:
            logger.error(f"Pipeline stream error: {e}", exc_info=True)
            yield evt("error", f"Pipeline error: {str(e)}")

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
