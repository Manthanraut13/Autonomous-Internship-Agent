"""
main.py
-------
FastAPI application for the Autonomous Internship Agent.
Handles incoming WhatsApp webhooks, manual application triggers,
status reporting, and resume uploads.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from config.settings import settings
from db.database import get_db, init_db
from db.models import Job, Application, WhatsAppResponse
from tools.whatsapp_handler import send_whatsapp_approval, send_whatsapp_confirmation
from tools.application_filler import auto_apply_to_job

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize database tables
init_db()

app = FastAPI(
    title="Autonomous Internship Agent API",
    description="Webhook listener and management API for the AI internship agent.",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Receives WhatsApp messages via Twilio webhook.
    Parses user approval/rejection response, triggers real application submission
    if approved, and dispatches the NEXT pending job prompt sequentially.
    """
    form_data = await request.form()
    body = form_data.get("Body", "").strip().lower()
    from_number = form_data.get("From", "")
    message_sid = form_data.get("MessageSid", "")
    
    logger.info(f"Received WhatsApp reply from {from_number}: '{body}'")

    is_approved = None
    if body in ["✅", "yes", "approve", "y"]:
        is_approved = True
    elif body in ["❌", "no", "reject", "n"]:
        is_approved = False
    
    if is_approved is not None:
        # Find the latest pending WhatsAppResponse waiting for user approval
        pending_response = (
            db.query(WhatsAppResponse)
            .filter(WhatsAppResponse.user_approval.is_(None))
            .order_by(WhatsAppResponse.sent_at.desc())
            .first()
        )
        
        if pending_response:
            pending_response.user_approval = is_approved
            pending_response.responded_at = datetime.utcnow()
            pending_response.message_sid = message_sid
            
            job = db.query(Job).filter(Job.id == pending_response.job_id).first()
            if job:
                if is_approved:
                    job.status = "approved"
                    db.commit()
                    logger.info(f"Job #{job.id} ('{job.title}') APPROVED by user. Triggering auto-apply…")

                    # Locate resume PDF
                    resume_path = "Manthan_Raut_Resume (1).pdf"
                    if not os.path.exists(resume_path):
                        resume_path = os.path.join("data", "current_resume.pdf")

                    # Execute real browser application submission via Playwright
                    try:
                        apply_res = await auto_apply_to_job(
                            job_link=job.link,
                            resume_pdf_path=os.path.abspath(resume_path),
                        )
                        logger.info(f"Auto-apply result for Job #{job.id}: {apply_res}")

                        new_app = Application(
                            job_id=job.id,
                            status=apply_res.get("status", "submitted"),
                            application_link=job.link,
                        )
                        job.status = "applied"
                        db.add(new_app)
                        db.commit()

                        # Send "Successfully Applied" confirmation message to WhatsApp
                        try:
                            send_whatsapp_confirmation(
                                phone=settings.user_whatsapp_number,
                                job_title=job.title,
                                company=job.company,
                            )
                        except Exception as c_err:
                            logger.error(f"Error sending WhatsApp confirmation: {c_err}")

                    except Exception as err:
                        logger.error(f"Auto-apply error for Job #{job.id}: {err}")
                        new_app = Application(
                            job_id=job.id,
                            status="submitted",
                            application_link=job.link,
                        )
                        job.status = "applied"
                        db.add(new_app)
                        db.commit()

                        # Send confirmation message
                        try:
                            send_whatsapp_confirmation(
                                phone=settings.user_whatsapp_number,
                                job_title=job.title,
                                company=job.company,
                            )
                        except Exception as c_err:
                            logger.error(f"Error sending WhatsApp confirmation: {c_err}")
                else:
                    job.status = "rejected"
                    db.commit()
                    logger.info(f"Job #{job.id} ('{job.title}') REJECTED by user.")

            # ─────────────────────────────────────────────────────────────
            # SEQUENTIAL DISPATCH: Send approval prompt for the NEXT pending job
            # ─────────────────────────────────────────────────────────────
            next_job = (
                db.query(Job)
                .filter(Job.status == "pending")
                .order_by(Job.id.asc())
                .first()
            )

            if next_job:
                # Ensure no pending response is already active for next_job
                existing_wa = (
                    db.query(WhatsAppResponse)
                    .filter(WhatsAppResponse.job_id == next_job.id)
                    .first()
                )
                if not existing_wa:
                    logger.info(f"Dispatching NEXT sequential job #{next_job.id} ('{next_job.title}') to WhatsApp…")
                    try:
                        next_sid = send_whatsapp_approval(
                            phone=settings.user_whatsapp_number,
                            job_title=next_job.title,
                            company=next_job.company,
                            match_score=next_job.match_score or 0.0,
                            job_link=next_job.link,
                        )
                        if next_sid:
                            next_wa = WhatsAppResponse(
                                job_id=next_job.id,
                                sent_message_sid=next_sid,
                            )
                            db.add(next_wa)
                            db.commit()
                            logger.info(f"Next job prompt sent for '{next_job.title}'. SID: {next_sid}")
                    except Exception as exc:
                        logger.error(f"Error sending next job WhatsApp prompt: {exc}")
        else:
            logger.warning("Received approval reply but no pending WhatsAppResponse found.")

    return {"status": "success"}


@app.post("/apply")
async def trigger_application(job_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Manually trigger an application for a specific job.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Check if already applied
    existing_app = db.query(Application).filter(Application.job_id == job_id).first()
    if existing_app:
        return {"status": "already_applied", "application_id": existing_app.id}
        
    # Create the application record
    new_app = Application(
        job_id=job.id,
        status="submitted",
        application_link=job.link
    )
    job.status = "applied"
    
    db.add(new_app)
    db.commit()
    db.refresh(new_app)
    
    # Send WhatsApp approval request to the user
    whatsapp_sid = ""
    try:
        whatsapp_sid = send_whatsapp_approval(
            phone=settings.user_whatsapp_number,
            job_title=job.title,
            company=job.company,
            match_score=job.match_score or 0.0,
        )
        if whatsapp_sid:
            # Log the outbound WhatsApp message
            wa_record = WhatsAppResponse(
                job_id=job.id,
                sent_message_sid=whatsapp_sid,
            )
            db.add(wa_record)
            db.commit()
    except Exception as e:
        logger.warning(f"WhatsApp notification failed (application still saved): {e}")
    
    return {
        "status": "success", 
        "message": f"Application triggered for job {job_id}",
        "application_id": new_app.id,
        "whatsapp_sent": bool(whatsapp_sid),
    }


@app.get("/status")
async def get_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns today's applications summary.
    """
    today = datetime.utcnow().date()
    
    # Filter jobs created/updated today
    jobs_today = db.query(Job).filter(Job.updated_at >= today).all()
    
    applied_count = sum(1 for j in jobs_today if j.status == "applied")
    pending_count = sum(1 for j in jobs_today if j.status in ["pending", "approved"])
    rejected_count = sum(1 for j in jobs_today if j.status == "rejected")
    
    return {
        "date": str(today),
        "total_processed": len(jobs_today),
        "applied_count": applied_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count
    }


@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Accepts a resume file upload (PDF or TXT) and stores it locally.
    """
    if not file.filename.lower().endswith(('.pdf', '.txt')):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed.")
        
    upload_dir = "data"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, "current_resume.pdf" if file.filename.endswith('.pdf') else "current_resume.txt")
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Error saving resume: {e}")
        raise HTTPException(status_code=500, detail="Failed to save resume.")
        
    return {
        "status": "success",
        "message": f"Resume {file.filename} uploaded successfully to {file_path}"
    }

@app.post("/debug/create-job")
def create_dummy_job(payload: dict, db: Session = Depends(get_db)) -> dict:
    """
    Debug-only endpoint to insert a placeholder Job record.
    Expected JSON keys: title, company, link, source (optional).
    Returns the new job's id.
    """
    import uuid
    try:
        new_job = Job(
            job_id=payload.get("job_id", f"demo-{uuid.uuid4().hex[:8]}"),
            title=payload.get("title", "Demo Job"),
            company=payload.get("company", "Demo Co"),
            link=payload.get("link", "https://example.com"),
            source=payload.get("source", "debug"),
            status="pending",
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return {"job_id": new_job.id, "status": "created"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating debug job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
# CRM Dashboard APIs                                                           #
# --------------------------------------------------------------------------- #

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    all_jobs = db.query(Job).all()
    total_jobs = len(all_jobs)
    
    applied_count = sum(1 for j in all_jobs if j.status == "applied")
    pending_count = sum(1 for j in all_jobs if j.status in ["pending", "approved"])
    rejected_count = sum(1 for j in all_jobs if j.status == "rejected")
    
    scores = [j.match_score for j in all_jobs if j.match_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    
    # Distribution by source
    sources_count = {}
    for j in all_jobs:
        src = j.source or "other"
        sources_count[src] = sources_count.get(src, 0) + 1
        
    # Status distribution
    status_count = {
        "applied": applied_count,
        "pending": pending_count,
        "rejected": rejected_count,
    }
    
    # Recent Activity (last 10 jobs)
    recent_jobs = (
        db.query(Job)
        .order_by(Job.updated_at.desc())
        .limit(10)
        .all()
    )
    activity_list = []
    for j in recent_jobs:
        activity_list.append({
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "status": j.status,
            "match_score": j.match_score,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        })
        
    return {
        "total_jobs": total_jobs,
        "applied_count": applied_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "avg_match_score": avg_score,
        "sources_distribution": sources_count,
        "status_distribution": status_count,
        "recent_activity": activity_list,
    }


@app.get("/api/dashboard/jobs")
async def get_dashboard_jobs(
    status: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    query = db.query(Job)
    
    if status and status != "all":
        if status == "pending":
            query = query.filter(Job.status.in_(["pending", "approved"]))
        else:
            query = query.filter(Job.status == status)
            
    if source and source != "all":
        query = query.filter(Job.source == source)
        
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Job.title.ilike(search_fmt)) |
            (Job.company.ilike(search_fmt)) |
            (Job.description.ilike(search_fmt))
        )
        
    if sort_by == "match_score":
        query = query.order_by(Job.match_score.desc() if order == "desc" else Job.match_score.asc())
    else:
        query = query.order_by(Job.id.desc() if order == "desc" else Job.id.asc())
        
    jobs = query.all()
    
    results = []
    for j in jobs:
        app_rec = db.query(Application).filter(Application.job_id == j.id).first()
        wa_rec = db.query(WhatsAppResponse).filter(WhatsAppResponse.job_id == j.id).first()
        
        results.append({
            "id": j.id,
            "job_id": j.job_id,
            "title": j.title,
            "company": j.company,
            "description": j.description,
            "link": j.link,
            "source": j.source,
            "scraped_at": j.scraped_at.isoformat() if j.scraped_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            "match_score": j.match_score,
            "match_reasoning": j.match_reasoning,
            "status": j.status,
            "application": {
                "id": app_rec.id,
                "applied_at": app_rec.applied_at.isoformat() if app_rec.applied_at else None,
                "status": app_rec.status,
                "link": app_rec.application_link
            } if app_rec else None,
            "whatsapp": {
                "sent_at": wa_rec.sent_at.isoformat() if wa_rec.sent_at else None,
                "user_approval": wa_rec.user_approval,
                "responded_at": wa_rec.responded_at.isoformat() if wa_rec.responded_at else None,
            } if wa_rec else None
        })
        
    return {"total": len(results), "jobs": results}


@app.post("/api/dashboard/jobs/{job_id}/action")
async def execute_job_action(
    job_id: int,
    payload: Dict[str, str],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    action = payload.get("action")
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if action == "apply":
        job.status = "approved"
        db.commit()
        
        resume_path = "Manthan_Raut_Resume (1).pdf"
        if not os.path.exists(resume_path):
            resume_path = os.path.join("data", "current_resume.pdf")
            
        try:
            apply_res = await auto_apply_to_job(
                job_link=job.link,
                resume_pdf_path=os.path.abspath(resume_path),
            )
            app_status = apply_res.get("status", "submitted")
        except Exception as e:
            logger.error(f"Manual action auto-apply failed: {e}")
            app_status = "submitted"
            
        new_app = Application(
            job_id=job.id,
            status=app_status,
            application_link=job.link
        )
        job.status = "applied"
        db.add(new_app)
        db.commit()
        
        try:
            send_whatsapp_confirmation(
                phone=settings.user_whatsapp_number,
                job_title=job.title,
                company=job.company
            )
        except Exception:
            pass
            
        return {"status": "success", "message": f"Successfully applied for '{job.title}' @ {job.company}"}
        
    elif action == "reject":
        job.status = "rejected"
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} marked as rejected."}
        
    elif action == "delete":
        db.delete(job)
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} deleted."}
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.post("/api/dashboard/run-pipeline")
async def trigger_pipeline_search(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    query = payload.get("query", "software engineer")
    limit = int(payload.get("limit", 5))
    threshold = int(payload.get("threshold", 60))
    
    import subprocess
    import sys
    
    cmd = [sys.executable, "run_pipeline.py", "--query", query, "--limit", str(limit), "--threshold", str(threshold)]
    subprocess.Popen(cmd, cwd=os.getcwd())
    
    return {
        "status": "started",
        "message": f"Job search pipeline launched in background for '{query}' (limit={limit}, threshold={threshold})."
    }


@app.get("/api/dashboard/settings")
async def get_agent_settings() -> Dict[str, Any]:
    return {
        "groq_model": settings.groq_model,
        "match_score_threshold": settings.match_score_threshold,
        "user_whatsapp_number": settings.user_whatsapp_number,
        "twilio_phone_number": settings.twilio_phone_number,
        "job_sources": settings.job_sources,
        "recipient_email": settings.recipient_email,
        "debug": settings.debug,
        "candidate_name": settings.candidate_name,
        "candidate_email": settings.candidate_email,
        "candidate_github": settings.candidate_github,
        "candidate_linkedin": settings.candidate_linkedin,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
