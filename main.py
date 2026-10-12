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
import logging

# Ensure stdout/stderr are flushed immediately on cloud hosts (Render/Docker)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Ensure project root is on path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
import time
import asyncio
import hmac
import base64
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, Optional, AsyncGenerator

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from db.database import get_db, get_db_context, init_db, cleanup_expired_rejected_jobs
from db.models import Job, PipelineRun
from tools.auth_guard import LoginRateLimiter

# --------------------------------------------------------------------------- #
# Security & Token Authentication (HMAC-SHA256)                               #
# --------------------------------------------------------------------------- #

# Use configured secret or generate a cryptographically secure 256-bit runtime secret
_AUTH_SECRET_KEY = settings.auth_secret_key or secrets.token_hex(32)


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
        _AUTH_SECRET_KEY.encode('utf-8'),
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
            _AUTH_SECRET_KEY.encode('utf-8'),
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
    """Initialise database tables and optionally start background cron scheduler on application startup."""
    try:
        init_db()
        logger.info("✅ Database tables initialized and verified.")
        # Proactively purge expired rejected openings (older than 24 hours) to free database space
        purged = cleanup_expired_rejected_jobs(max_age_hours=24)
        if purged:
            logger.info(f"🧹 Startup cleanup: permanently purged {purged} rejected opening(s) older than 24h.")
    except Exception as e:
        logger.error(f"⚠️ Database startup check warning: {e}")

    # PRODUCTION SAFETY: When DISABLE_SCHEDULER=true (set on Render), skip APScheduler.
    # GitHub Actions handles the 9AM/9PM cron externally — running the scheduler inside
    # the web process caused memory spikes and duplicate pipeline executions.
    if os.environ.get("DISABLE_SCHEDULER", "").lower() in ("true", "1", "yes"):
        logger.info("📅 APScheduler DISABLED (DISABLE_SCHEDULER=true). Pipeline scheduling is handled by GitHub Actions.")
        return

    try:
        scheduler.add_job(
            scheduled_pipeline_execution,
            trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Kolkata"),
            id="morning_run",
            name="Morning Run (09:00 AM IST)",
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_pipeline_execution,
            trigger=CronTrigger(hour=21, minute=0, timezone="Asia/Kolkata"),
            id="evening_run",
            name="Evening Run (09:00 PM IST)",
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


# --------------------------------------------------------------------------- #
# Health Check (public — used by Render for health monitoring)                 #
# --------------------------------------------------------------------------- #

@app.get("/health")
async def health_check():
    """Public health check endpoint for Render / uptime monitors. No auth required."""
    from db.database import check_db_connection
    db_ok = check_db_connection()
    scheduler_status = "disabled" if os.environ.get("DISABLE_SCHEDULER", "").lower() in ("true", "1", "yes") else ("running" if scheduler.running else "stopped")
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "scheduler": scheduler_status,
        "version": app.version,
    }


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

# Brute-force guard: per-IP failure window (5 fails / 15 min → 429) plus a
# constant 1s delay on every failed attempt. In-memory: fine for this
# single-process app; would need a shared store if it ever runs multiple workers.
_login_limiter = LoginRateLimiter(max_failures=5, window_secs=900)


def _client_ip(request: Request) -> str:
    # First X-Forwarded-For hop as set by the hosting proxy (Render).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/api/auth/login")
async def login(request: Request, credentials: Dict[str, str]):
    username = credentials.get("username", "").strip()
    password = credentials.get("password", "").strip()

    client_ip = _client_ip(request)
    if _login_limiter.locked_out(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.")

    admin_user = settings.admin_username or "admin"
    admin_pass = settings.admin_password

    if not admin_pass:
        logger.error("ADMIN_PASSWORD has not been configured in the environment.")
        raise HTTPException(
            status_code=500,
            detail="Admin credentials have not been configured on this server."
        )

    valid_user = secrets.compare_digest(username, admin_user)
    valid_pass = secrets.compare_digest(password, admin_pass)

    if not (valid_user and valid_pass):
        _login_limiter.record_failure(client_ip)
        logger.warning(f"Failed login attempt for user: '{username}' from {client_ip}")
        await asyncio.sleep(1.0)  # constant delay blunts credential stuffing
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _login_limiter.reset(client_ip)
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
    # Proactively purge rejected openings older than 24 hours before computing stats
    cleanup_expired_rejected_jobs(db, max_age_hours=24)

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
    # Proactively purge rejected openings older than 24 hours before querying
    cleanup_expired_rejected_jobs(db, max_age_hours=24)

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
        "semantic_score": j.semantic_score,
        "role_type": j.role_type or "internship",
        "work_mode": getattr(j, "work_mode", "onsite") or "onsite",
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
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} marked as applied."}

    elif action in ["mark_not_applied", "reject"]:
        job.status = "rejected"
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        # Clean up any expired rejected jobs (older than 24 hours) from DB
        cleanup_expired_rejected_jobs(db, max_age_hours=24)
        return {"status": "success", "message": f"Job #{job_id} marked as not applied."}

    elif action in ["mark_saved", "restore"]:
        job.status = "saved"
        job.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} moved back to Inbox."}

    raise HTTPException(status_code=400, detail=f"Invalid action '{action}'.")


@app.post("/api/dashboard/cleanup-rejected")
async def trigger_cleanup_rejected(
    max_age_hours: int = 24,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Permanently delete rejected openings older than max_age_hours (default: 24h)
    from both the dashboard view and database to free up storage for incoming openings.
    """
    deleted_count = cleanup_expired_rejected_jobs(db, max_age_hours=max_age_hours)
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": f"Permanently deleted {deleted_count} rejected opening(s) older than {max_age_hours} hours."
    }


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
    Server-Sent Events endpoint that runs the shared pipeline core
    (tools.pipeline_core.process_jobs) in a worker thread and streams its
    progress events live. Protected with require_admin.
    """
    import threading

    async def event_generator() -> AsyncGenerator[dict, None]:
        from tools.pipeline_core import process_jobs

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        abort = threading.Event()

        def worker():
            try:
                for ev in process_jobs(target_matches=target, threshold=threshold,
                                       source="dashboard", should_abort=abort.is_set):
                    loop.call_soon_threadsafe(queue.put_nowait, ("event", ev))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))

        threading.Thread(target=worker, daemon=True, name="pipeline-worker").start()

        def evt(step: str, message: str, data: Any = None) -> dict:
            payload = {"step": step, "message": message, "timestamp": datetime.now(timezone.utc).isoformat()}
            if data is not None:
                payload["data"] = data
            return {"event": "pipeline", "data": json.dumps(payload)}

        while True:
            if await request.is_disconnected():
                abort.set()
                return
            try:
                kind, item = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if kind == "error":
                logger.error(f"Pipeline stream error: {item}")
                yield evt("error", f"Pipeline error: {item}")
                return
            yield evt(item["step"], item["message"], item.get("data"))
            if item["step"] in ("complete", "aborted", "error"):
                return

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=settings.debug)
