"""
main.py
-------
FastAPI application for the Autonomous Internship Agent.
Serves the React dashboard, provides CRM APIs for browsing scraped jobs,
and exposes a pipeline trigger endpoint.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from config.settings import settings
from db.database import get_db, init_db
from db.models import Job

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize database tables
init_db()

app = FastAPI(
    title="Autonomous Internship Agent API",
    description="Dashboard API and pipeline trigger for the AI internship agent.",
    version="2.0.0"
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


@app.get("/status")
async def get_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns today's jobs summary.
    """
    today = datetime.utcnow().date()
    
    # Filter jobs created/updated today
    jobs_today = db.query(Job).filter(Job.updated_at >= today).all()
    
    saved_count = sum(1 for j in jobs_today if j.status == "saved")
    emailed_count = sum(1 for j in jobs_today if j.status == "emailed")
    
    return {
        "date": str(today),
        "total_processed": len(jobs_today),
        "saved_count": saved_count,
        "emailed_count": emailed_count,
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


# --------------------------------------------------------------------------- #
# CRM Dashboard APIs                                                           #
# --------------------------------------------------------------------------- #

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    all_jobs = db.query(Job).all()
    total_jobs = len(all_jobs)
    
    saved_count = sum(1 for j in all_jobs if j.status == "saved")
    emailed_count = sum(1 for j in all_jobs if j.status == "emailed")
    
    scores = [j.match_score for j in all_jobs if j.match_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    
    # Distribution by source
    sources_count = {}
    for j in all_jobs:
        src = j.source or "other"
        sources_count[src] = sources_count.get(src, 0) + 1
        
    # Status distribution
    status_count = {
        "saved": saved_count,
        "emailed": emailed_count,
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
        "saved_count": saved_count,
        "emailed_count": emailed_count,
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
        results.append({
            "id": j.id,
            "job_id": j.job_id,
            "title": j.title,
            "company": j.company,
            "description": j.description,
            "link": j.link,
            "apply_url": j.apply_url or "",
            "location": j.location or "",
            "source": j.source,
            "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            "scraped_at": j.scraped_at.isoformat() if j.scraped_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            "match_score": j.match_score,
            "match_reasoning": j.match_reasoning,
            "status": j.status,
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
        
    if action == "delete":
        db.delete(job)
        db.commit()
        return {"status": "success", "message": f"Job #{job_id} deleted."}
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Only 'delete' is supported.")


@app.post("/api/dashboard/run-pipeline")
async def trigger_pipeline_search(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    query = payload.get("query", "AI Automation Intern")
    limit = int(payload.get("limit", 5))
    threshold = int(payload.get("threshold", 70))
    
    import subprocess
    import sys
    
    cmd = [sys.executable, "run_pipeline.py", "--limit", str(limit), "--threshold", str(threshold)]
    subprocess.Popen(cmd, cwd=os.getcwd())
    
    return {
        "status": "started",
        "message": f"Pipeline launched in background (limit={limit}, threshold={threshold}). CSV report will be emailed when complete."
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
