# Autonomous Internship Agent - Step by Step Build Guide

---

## STEP 1: PROJECT SETUP

### 1.1 Create Project Structure

```bash
mkdir internship-agent
cd internship-agent
git init
```

### 1.2 Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 1.3 Create Project Folders

```bash
mkdir config agents tools db utils scheduler tests
touch requirements.txt .env .gitignore main.py
```

### 1.4 Add to .gitignore

```
venv/
.env
__pycache__/
*.pyc
.DS_Store
*.db
```

---

## STEP 2: DEPENDENCIES & REQUIREMENTS

### 2.1 Create requirements.txt

**Placeholder:** Paste the following into requirements.txt:

```
langgraph==0.0.21
langchain==0.1.13
langchain-openai==0.1.1
langchain-community==0.1.1
langsmith==0.1.9
openai==1.3.0
twilio==8.10.0
sendgrid==6.10.0
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
selenium==4.15.0
playwright==1.40.0
requests==2.31.0
beautifulsoup4==4.12.2
APScheduler==3.10.4
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.2
python-dotenv==1.0.0
pydantic-settings==2.1.0
PyPDF2==3.0.1
```

### 2.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.3 Install Playwright Browsers

```bash
playwright install chromium
```

---

## STEP 3: API KEYS & EXTERNAL TOOL SETUP

### 3.1 Get OpenAI API Key

1. Go to https://platform.openai.com/account/api-keys
2. Create new API key
3. Copy it (save securely)

### 3.2 Get LangSmith API Key

1. Go to https://smith.langchain.com
2. Sign up with GitHub/Google
3. Settings → Create API Key
4. Copy it

### 3.3 Get Twilio Account (WhatsApp)

1. Go to https://www.twilio.com
2. Sign up, verify phone number
3. Console → Account SID & Auth Token (copy)
4. Get a Twilio Phone Number (with WhatsApp enabled)
5. Verify your personal WhatsApp number in Twilio

### 3.4 Get SendGrid API Key (Email)

1. Go to https://sendgrid.com
2. Sign up
3. Settings → API Keys → Create API Key
4. Copy it (name it: internship-agent)

### 3.5 PostgreSQL Database Setup

**On Windows:**
1. Download PostgreSQL installer from https://www.postgresql.org/download/windows/
2. Install with default settings
3. Remember the password you set for `postgres` user
4. Open pgAdmin (installed with PostgreSQL)

**On Mac:**
```bash
brew install postgresql
brew services start postgresql
```

**On Linux:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 3.6 Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# In psql terminal:
CREATE DATABASE internship_agent;
\c internship_agent
```

---

## STEP 4: ENVIRONMENT CONFIGURATION

### 4.1 Create .env File

Create `.env` in root folder with:

```env
# OpenAI
OPENAI_API_KEY=sk-your_key_here
OPENAI_MODEL=gpt-4

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_your_key_here
LANGCHAIN_PROJECT=internship-agent

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=AC_your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_PHONE_NUMBER=+1234567890
USER_WHATSAPP_NUMBER=+1234567890

# SendGrid (Email)
SENDGRID_API_KEY=SG_your_key_here
SENDER_EMAIL=your-email@domain.com
RECIPIENT_EMAIL=your-personal-email@gmail.com

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/internship_agent

# Agent Config
MATCH_SCORE_THRESHOLD=70
APPROVAL_TIMEOUT_HOURS=24
AUTO_REJECT_ON_TIMEOUT=true

# Job Sources
JOB_SOURCES=indeed,linkedin,internship.com

# Debug
DEBUG=false
```

### 4.2 Create config/settings.py

**AI Prompt to give Claude:**
```
Create a Pydantic BaseSettings class that loads all environment variables from .env file. 
Include settings for:
- OpenAI API key and model
- Twilio credentials and phone numbers
- SendGrid API key and email addresses
- Database URL
- Match score threshold (integer)
- Approval timeout hours
- Auto reject on timeout (boolean)
- Job sources (list)
Make sure to use @field_validator for database URL validation.
```

**Placeholder:**

```python
# config/settings.py

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # [PLACEHOLDER: Add all settings fields with validators]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 4.3 Create config/prompts.py

**AI Prompt to give Claude:**
```
Create a file with three LLM system prompts:
1. MATCH_SYSTEM_PROMPT - for resume-job matching analysis
2. APPLICATION_EMAIL_PROMPT - for generating application emails
3. SUMMARY_PROMPT - for creating daily summaries

Each prompt should guide GPT-4 to return structured output.
```

**Placeholder:**

```python
# config/prompts.py

MATCH_SYSTEM_PROMPT = """
[PLACEHOLDER: Resume matching prompt]
"""

APPLICATION_EMAIL_PROMPT = """
[PLACEHOLDER: Application email prompt]
"""

SUMMARY_PROMPT = """
[PLACEHOLDER: Summary generation prompt]
"""
```

---

## STEP 5: DATABASE SETUP

### 5.1 Create db/models.py

**AI Prompt to give Claude:**
```
Create SQLAlchemy ORM models for:
1. Job model with fields: job_id, title, company, description, link, source, scraped_at, match_score, status
2. Application model with fields: job_id (FK), applied_at, application_id, status, application_link
3. WhatsAppResponse model with fields: job_id (FK), user_approval, responded_at, message_sid

Include proper relationships and timestamps.
```

**Placeholder:**

```python
# db/models.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    # [PLACEHOLDER: Define Job model fields]

class Application(Base):
    __tablename__ = "applications"
    # [PLACEHOLDER: Define Application model fields]

class WhatsAppResponse(Base):
    __tablename__ = "whatsapp_responses"
    # [PLACEHOLDER: Define WhatsAppResponse model fields]
```

### 5.2 Create db/database.py

**AI Prompt to give Claude:**
```
Create database initialization and session functions:
1. Create engine using DATABASE_URL from settings
2. Create all tables function using Base.metadata.create_all
3. Create SessionLocal factory using sessionmaker
4. Create get_db dependency function for FastAPI
```

**Placeholder:**

```python
# db/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from db.models import Base

DATABASE_URL = settings.database_url

# [PLACEHOLDER: Create engine, SessionLocal, init_db function, get_db function]

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created!")
```

### 5.3 Create Database Tables

```bash
python -c "from db.database import init_db; init_db()"
```

---

## STEP 6: RESUME PARSER

### 6.1 Create tools/resume_parser.py

**AI Prompt to give Claude:**
```
Create a resume parser function that:
1. Accepts file path to PDF or TXT resume
2. If PDF: extract text using PyPDF2
3. If TXT: read directly
4. Extract key sections: skills, experience, education, projects
5. Return dictionary with structured data

Use regex or simple string matching for section detection.
Return format: {"skills": [...], "experience": [...], "education": [...], "projects": [...]}
```

**Placeholder:**

```python
# tools/resume_parser.py

from pathlib import Path
import re
import PyPDF2

def parse_resume(file_path: str) -> dict:
    """Parse resume and extract sections."""
    # [PLACEHOLDER: Read file based on extension]
    # [PLACEHOLDER: Extract text]
    # [PLACEHOLDER: Parse sections using regex]
    # [PLACEHOLDER: Return structured dict]
    pass

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    # [PLACEHOLDER: Use PyPDF2 to read PDF]
    pass

def extract_skills(text: str) -> list:
    """Extract skills section from resume text."""
    # [PLACEHOLDER: Find skills section and parse]
    pass
```

---

## STEP 7: JOB SCRAPER

### 7.1 Create tools/job_scraper.py

**AI Prompt to give Claude:**
```
Create three job scraper functions:

1. scrape_indeed(search_query, num_pages, location) - Scrapes Indeed jobs
   - Use BeautifulSoup to parse HTML
   - Extract: title, company, description, link, location
   - Return list of dicts

2. scrape_internship_com(search_query, num_pages) - Scrapes internship.com
   - Similar to Indeed
   
3. scrape_all_sources() - Main function that calls all scrapers
   - Combine results
   - Deduplicate by link
   - Return unified list

Each job dict should have: title, company, description, link, source (indeed/internship.com/linkedin)
Add delays between requests to avoid blocking.
```

**Placeholder:**

```python
# tools/job_scraper.py

import requests
from bs4 import BeautifulSoup
import time
from typing import List

def scrape_indeed(search_query: str = "internship", num_pages: int = 1, location: str = "") -> List[dict]:
    """Scrape internships from Indeed."""
    # [PLACEHOLDER: Implement Indeed scraping]
    pass

def scrape_internship_com(search_query: str = "internship", num_pages: int = 1) -> List[dict]:
    """Scrape internships from internship.com."""
    # [PLACEHOLDER: Implement internship.com scraping]
    pass

def scrape_all_sources() -> List[dict]:
    """Scrape from all job sources and deduplicate."""
    all_jobs = []
    
    # [PLACEHOLDER: Call all scrapers]
    # [PLACEHOLDER: Deduplicate by link]
    # [PLACEHOLDER: Return combined list]
    pass

def deduplicate_jobs(jobs: List[dict]) -> List[dict]:
    """Remove duplicate jobs by link."""
    # [PLACEHOLDER: Implement deduplication logic]
    pass
```

### 7.2 Test Job Scraper

```bash
python -c "from tools.job_scraper import scrape_all_sources; jobs = scrape_all_sources(); print(f'Found {len(jobs)} jobs')"
```

---

## STEP 8: RESUME-JD MATCHER (LLM)

### 8.1 Create tools/jd_matcher.py

**AI Prompt to give Claude:**
```
Create a resume-job matching agent using LangChain:

1. Use ChatOpenAI with gpt-4 model
2. Create ChatPromptTemplate with resume and job description
3. Create JsonOutputParser with Pydantic model for output
4. Pydantic model should have: score (int 0-100), reasoning (str), key_matches (list), gaps (list)
5. Chain: prompt | llm | parser
6. Function signature: match_resume_to_job(resume_text: str, job_description: str) -> dict

Return dict with score, reasoning, key_matches, gaps.
Score should be based on: skills overlap, experience relevance, education fit, project alignment.
```

**Placeholder:**

```python
# tools/jd_matcher.py

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from config.settings import settings
from config.prompts import MATCH_SYSTEM_PROMPT

class MatchResult(BaseModel):
    score: int = Field(description="Match score 0-100")
    reasoning: str = Field(description="Why this score")
    key_matches: list = Field(description="Matching skills")
    gaps: list = Field(description="Missing skills")

def match_resume_to_job(resume_text: str, job_description: str) -> dict:
    """Calculate resume-job match score using LLM."""
    # [PLACEHOLDER: Create LLM instance]
    # [PLACEHOLDER: Create prompt template]
    # [PLACEHOLDER: Create JsonOutputParser]
    # [PLACEHOLDER: Create chain]
    # [PLACEHOLDER: Invoke chain with resume and job description]
    # [PLACEHOLDER: Return result dict]
    pass
```

### 8.2 Test Matcher

```bash
python -c "
from tools.jd_matcher import match_resume_to_job
result = match_resume_to_job(
    'Python developer with 2 years experience',
    'Looking for Python dev with FastAPI knowledge'
)
print(f'Score: {result[\"score\"]}')
"
```

---

## STEP 9: WHATSAPP INTEGRATION

### 9.1 Create tools/whatsapp_handler.py

**AI Prompt to give Claude:**
```
Create WhatsApp functions using Twilio SDK:

1. send_whatsapp_approval(phone: str, job_title: str, company: str, match_score: float) -> str
   - Send message with job details and match score
   - Message should include job title, company, match score
   - Suggest user to reply with ✅ to apply or ❌ to skip
   - Return message SID

2. send_whatsapp_summary(phone: str, applications: list) -> bool
   - Send daily summary of applications
   - Include: applied count, company names, match scores
   - Return True/False for success

3. Format messages to be concise and WhatsApp-friendly
```

**Placeholder:**

```python
# tools/whatsapp_handler.py

from twilio.rest import Client
from config.settings import settings
from typing import List

twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

def send_whatsapp_approval(phone: str, job_title: str, company: str, match_score: float) -> str:
    """Send WhatsApp message requesting job approval."""
    # [PLACEHOLDER: Format message body]
    # [PLACEHOLDER: Create message using twilio_client.messages.create]
    # [PLACEHOLDER: Return message SID]
    pass

def send_whatsapp_summary(phone: str, applications: List[dict]) -> bool:
    """Send daily WhatsApp summary of applications."""
    # [PLACEHOLDER: Format summary message]
    # [PLACEHOLDER: Create message using twilio_client.messages.create]
    # [PLACEHOLDER: Return True/False]
    pass
```

### 9.2 Create main.py (FastAPI Server for Webhook)

**AI Prompt to give Claude:**
```
Create a FastAPI application with:

1. POST /webhook/whatsapp endpoint that:
   - Receives WhatsApp messages via Twilio webhook
   - Extracts user message body and phone number
   - Parses user response (✅/YES/APPROVE for approval, ❌/NO/REJECT for rejection)
   - Store response in WhatsAppResponse table in database
   - Link response to correct job using message metadata
   - Return {"status": "success"} JSON response

2. POST /apply endpoint that:
   - Accepts job_id as parameter
   - Manually trigger application for a job
   - Return application status

3. GET /status endpoint that:
   - Return today's applications summary
   - Include: applied count, pending count, rejected count

4. POST /upload-resume endpoint that:
   - Accept resume file upload (PDF)
   - Store in database or S3
   - Return success message

Include CORS middleware and proper error handling.
```

**Placeholder:**

```python
# main.py

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from db.database import SessionLocal, get_db
from db.models import WhatsAppResponse, Job
from config.settings import settings

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/webhook/whatsapp")
async def handle_whatsapp_response(request: Request):
    """Handle incoming WhatsApp messages."""
    # [PLACEHOLDER: Parse form data from request]
    # [PLACEHOLDER: Extract message body, phone number, message SID]
    # [PLACEHOLDER: Parse approval/rejection from message]
    # [PLACEHOLDER: Store in database]
    # [PLACEHOLDER: Trigger applicant node if approved]
    # [PLACEHOLDER: Return success response]
    pass

@app.post("/apply")
async def manual_apply(job_id: str):
    """Manually trigger application for a job."""
    # [PLACEHOLDER: Fetch job from database]
    # [PLACEHOLDER: Trigger applicant node]
    # [PLACEHOLDER: Return status]
    pass

@app.get("/status")
async def get_daily_status():
    """Get today's applications summary."""
    # [PLACEHOLDER: Query applications from database]
    # [PLACEHOLDER: Calculate counts and statistics]
    # [PLACEHOLDER: Return summary]
    pass

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload user resume."""
    # [PLACEHOLDER: Validate file is PDF]
    # [PLACEHOLDER: Save file locally or to S3]
    # [PLACEHOLDER: Return success response]
    pass

@app.get("/")
async def root():
    return {"status": "Internship Agent Server Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 9.3 Setup Twilio Webhook

1. Go to Twilio Console → Phone Numbers
2. Select your WhatsApp-enabled number
3. Messaging → A message comes in → Send webhook to:
   ```
   http://your-server-url:8000/webhook/whatsapp
   ```
4. Choose HTTP POST
5. Save

### 9.4 Test WhatsApp (Locally)

For local testing, use ngrok to expose your local server:

```bash
ngrok http 8000
```

Then use ngrok URL in Twilio webhook settings.

---

## STEP 10: AUTO-APPLICANT (FORM FILLING)

### 10.1 Create tools/application_filler.py

**AI Prompt to give Claude:**
```
Create async functions for automated job applications using Playwright:

1. auto_apply_to_job(job_link: str, resume_pdf_path: str, github: str, linkedin: str) -> dict
   - Main function that detects job platform and calls appropriate filler
   - Launch Playwright browser in headless mode
   - Navigate to job_link
   - Call platform-specific function (Indeed, LinkedIn, generic)
   - Handle timeouts with try-except
   - Return: {"status": "applied"/"email_sent"/"failed", "platform": "indeed"/"linkedin"/"generic"}

2. apply_indeed(page, resume_pdf_path, github, linkedin)
   - Find and click "Easy Apply" button
   - Fill email field
   - Upload resume PDF
   - Fill cover letter with GitHub and LinkedIn links
   - Submit form
   - Wait for confirmation

3. apply_linkedin(page, resume_pdf_path, github, linkedin)
   - Similar to Indeed
   - Handle LinkedIn-specific form fields

4. apply_generic(page, resume_pdf_path, github, linkedin)
   - Detect form fields by placeholder/name attribute
   - Auto-fill email, name, phone if present
   - Upload resume
   - Fill textarea with application message
   - Submit

Add error handling and logging. Use playwright waits for dynamic content.
```

**Placeholder:**

```python
# tools/application_filler.py

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import logging

logger = logging.getLogger(__name__)

async def auto_apply_to_job(job_link: str, resume_pdf_path: str, github: str, linkedin: str) -> dict:
    """Attempt to auto-apply to job on any platform."""
    # [PLACEHOLDER: Launch browser]
    # [PLACEHOLDER: Navigate to job_link with timeout]
    # [PLACEHOLDER: Detect platform from URL]
    # [PLACEHOLDER: Call appropriate apply function]
    # [PLACEHOLDER: Handle exceptions and return status]
    pass

async def apply_indeed(page, resume_pdf_path: str, github: str, linkedin: str):
    """Apply to Indeed job posting."""
    # [PLACEHOLDER: Find Easy Apply button]
    # [PLACEHOLDER: Click button]
    # [PLACEHOLDER: Wait for form to appear]
    # [PLACEHOLDER: Fill email field]
    # [PLACEHOLDER: Upload resume]
    # [PLACEHOLDER: Fill cover letter]
    # [PLACEHOLDER: Submit form]
    pass

async def apply_linkedin(page, resume_pdf_path: str, github: str, linkedin: str):
    """Apply to LinkedIn job posting."""
    # [PLACEHOLDER: Similar to Indeed but LinkedIn-specific]
    pass

async def apply_generic(page, resume_pdf_path: str, github: str, linkedin: str):
    """Apply to generic job board with form fields."""
    # [PLACEHOLDER: Find all input fields]
    # [PLACEHOLDER: Detect field type by placeholder/name]
    # [PLACEHOLDER: Auto-fill text fields]
    # [PLACEHOLDER: Upload resume to file input]
    # [PLACEHOLDER: Fill textarea]
    # [PLACEHOLDER: Find and click submit button]
    pass
```

### 10.2 Test Auto-Apply (Carefully)

```bash
python -c "
import asyncio
from tools.application_filler import auto_apply_to_job

result = asyncio.run(auto_apply_to_job(
    'https://indeed.com/viewjob?jk=test',
    'resume.pdf',
    'https://github.com/user',
    'https://linkedin.com/in/user'
))
print(result)
"
```

---

## STEP 11: EMAIL SUMMARY

### 11.1 Create tools/email_handler.py

**AI Prompt to give Claude:**
```
Create email functions using SendGrid:

1. send_daily_summary(recipient_email: str, applications: list, date: str) -> bool
   - Create HTML email template
   - Include table with: Company, Position, Match Score, Status
   - Calculate statistics: applied count, success rate, pending count
   - Include link to dashboard
   - Send using SendGridAPIClient
   - Return True/False for success

2. generate_email_html(applications: list, date: str) -> str
   - Create HTML template
   - Include header with date
   - Create table with application details
   - Include summary statistics
   - Include footer with dashboard link

3. Format should be professional and mobile-friendly
```

**Placeholder:**

```python
# tools/email_handler.py

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content
from config.settings import settings
from typing import List
from datetime import datetime

def send_daily_summary(recipient_email: str, applications: List[dict], date: str = None) -> bool:
    """Send daily email summary of applications."""
    if date is None:
        date = datetime.now().strftime("%B %d, %Y")
    
    # [PLACEHOLDER: Generate HTML content]
    # [PLACEHOLDER: Create Mail object]
    # [PLACEHOLDER: Send using SendGridAPIClient]
    # [PLACEHOLDER: Return True/False]
    pass

def generate_email_html(applications: List[dict], date: str) -> str:
    """Generate HTML email template."""
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .summary {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h2>📊 Internship Agent Report - {date}</h2>
            [PLACEHOLDER: Add summary stats]
            <table>
                <tr>
                    <th>Company</th>
                    <th>Position</th>
                    <th>Match Score</th>
                    <th>Status</th>
                </tr>
                [PLACEHOLDER: Add table rows for each application]
            </table>
            [PLACEHOLDER: Add footer]
        </body>
    </html>
    """
    return html
```

---

## STEP 12: LANGGRAPH WORKFLOW

### 12.1 Create agents/workflow.py

**AI Prompt to give Claude:**
```
Create a LangGraph workflow with StateGraph:

1. Define AgentState TypedDict with fields:
   - resume: str
   - portfolio_link, github_link, linkedin_link: str
   - jobs_to_process: List[dict]
   - current_job: Optional[dict]
   - match_score: float
   - match_reasoning: str
   - user_approval: Optional[bool]
   - application_status: str
   - applications_today: List[dict]
   - errors: List[str]

2. Create 5 nodes:
   a) scraper_node - Fetch jobs from all sources
   b) matcher_node - Calculate match score for current job
   c) approval_node - Send WhatsApp approval if score > threshold
   d) applicant_node - Auto-apply if user approved
   e) summary_node - Send email and WhatsApp summary

3. Create conditional edges:
   - After matcher: if score >= 70, go to approval, else process next job
   - After applicant: if more jobs, go back to matcher, else go to summary

4. Compile workflow and return compiled graph

5. Track all jobs processed and applications sent
```

**Placeholder:**

```python
# agents/workflow.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    resume: str
    portfolio_link: str
    github_link: str
    linkedin_link: str
    jobs_to_process: List[dict]
    current_job: Optional[dict]
    match_score: float
    match_reasoning: str
    user_approval: Optional[bool]
    application_status: str
    applications_today: List[dict]
    errors: List[str]

# [PLACEHOLDER: Import all node functions]

def scraper_node(state: AgentState) -> AgentState:
    """Node 1: Fetch jobs from all sources."""
    # [PLACEHOLDER: Call scrape_all_sources()]
    # [PLACEHOLDER: Set jobs_to_process in state]
    # [PLACEHOLDER: Log job count]
    pass

def matcher_node(state: AgentState) -> AgentState:
    """Node 2: Match resume to current job."""
    # [PLACEHOLDER: Get first job from jobs_to_process]
    # [PLACEHOLDER: Set as current_job]
    # [PLACEHOLDER: Call match_resume_to_job()]
    # [PLACEHOLDER: Set match_score and match_reasoning]
    # [PLACEHOLDER: Remove processed job from list]
    pass

def approval_node(state: AgentState) -> AgentState:
    """Node 3: Request WhatsApp approval if score > threshold."""
    # [PLACEHOLDER: Check if score >= MATCH_SCORE_THRESHOLD]
    # [PLACEHOLDER: If yes, send WhatsApp message]
    # [PLACEHOLDER: Set application_status to pending_approval]
    # [PLACEHOLDER: Handle exceptions]
    pass

def applicant_node(state: AgentState) -> AgentState:
    """Node 4: Auto-apply if user approved."""
    # [PLACEHOLDER: Check if user_approval is True]
    # [PLACEHOLDER: If yes, call auto_apply_to_job()]
    # [PLACEHOLDER: Add to applications_today]
    # [PLACEHOLDER: Update application_status]
    pass

def summary_node(state: AgentState) -> AgentState:
    """Node 5: Send daily summary."""
    # [PLACEHOLDER: Call send_daily_summary() for email]
    # [PLACEHOLDER: Call send_whatsapp_summary() for WhatsApp]
    # [PLACEHOLDER: Log summary sent]
    pass

def should_process_more_jobs(state: AgentState) -> str:
    """Decide: process more jobs or finish."""
    # [PLACEHOLDER: If jobs_to_process is not empty, return "matcher"]
    # [PLACEHOLDER: Else return END]
    pass

def should_request_approval(state: AgentState) -> str:
    """Decide: request approval or process next job."""
    # [PLACEHOLDER: If match_score >= MATCH_SCORE_THRESHOLD, return "approval"]
    # [PLACEHOLDER: Else return "matcher" to continue]
    pass

# Build graph
graph = StateGraph(AgentState)

# [PLACEHOLDER: Add nodes to graph]
# [PLACEHOLDER: Set entry point to scraper]
# [PLACEHOLDER: Add edges between nodes]
# [PLACEHOLDER: Add conditional edges]
# [PLACEHOLDER: Compile graph]

agent_workflow = graph.compile()
```

### 12.2 Create agents/__init__.py

```python
# agents/__init__.py

from agents.workflow import agent_workflow, AgentState

__all__ = ['agent_workflow', 'AgentState']
```

---

## STEP 13: SCHEDULER (DAILY AUTOMATION)

### 13.1 Create scheduler/scheduler.py

**AI Prompt to give Claude:**
```
Create APScheduler job scheduler:

1. Setup BackgroundScheduler with:
   - Trigger: CronTrigger for 9:00 AM daily
   - Job: run_agent() function

2. run_agent() function should:
   - Load user's resume from database/file
   - Initialize AgentState with resume, links, empty jobs list
   - Call agent_workflow.invoke(state)
   - Log execution details
   - Handle any exceptions
   - Send alert if workflow fails

3. start_scheduler() function:
   - Create scheduler instance
   - Add run_agent job
   - Start scheduler
   - Return scheduler instance

4. Include graceful shutdown and job persistence
```

**Placeholder:**

```python
# scheduler/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from agents.workflow import agent_workflow, AgentState
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

def run_agent():
    """Execute internship agent workflow."""
    try:
        logger.info("Starting internship agent run...")
        
        # [PLACEHOLDER: Load user resume from file/database]
        # [PLACEHOLDER: Create initial state]
        # [PLACEHOLDER: Invoke workflow]
        # [PLACEHOLDER: Log results]
        
        logger.info("Agent run completed successfully")
    except Exception as e:
        logger.error(f"Agent run failed: {str(e)}")
        # [PLACEHOLDER: Send error alert]

def start_scheduler():
    """Start the APScheduler scheduler."""
    scheduler = BackgroundScheduler()
    
    # [PLACEHOLDER: Add job with CronTrigger(hour=9, minute=0)]
    # [PLACEHOLDER: Start scheduler]
    # [PLACEHOLDER: Return scheduler]
    
    return scheduler

scheduler_instance = None

def init_scheduler():
    """Initialize scheduler (call once on app startup)."""
    global scheduler_instance
    scheduler_instance = start_scheduler()
    logger.info("Scheduler initialized")

def shutdown_scheduler():
    """Shutdown scheduler gracefully."""
    global scheduler_instance
    if scheduler_instance:
        scheduler_instance.shutdown()
        logger.info("Scheduler shutdown")
```

### 13.2 Update main.py to Start Scheduler

**AI Prompt to give Claude:**
```
Add startup and shutdown events to FastAPI app:

1. @app.on_event("startup") - Call init_scheduler()
2. @app.on_event("shutdown") - Call shutdown_scheduler()

This ensures scheduler starts when server starts and stops gracefully on shutdown.
```

**Placeholder:**

```python
# Add to main.py

from scheduler.scheduler import init_scheduler, shutdown_scheduler

@app.on_event("startup")
async def startup():
    """Initialize scheduler on server startup."""
    # [PLACEHOLDER: Call init_scheduler()]
    pass

@app.on_event("shutdown")
async def shutdown():
    """Shutdown scheduler on server shutdown."""
    # [PLACEHOLDER: Call shutdown_scheduler()]
    pass
```

---

## STEP 14: TESTING

### 14.1 Create tests/test_matcher.py

**AI Prompt to give Claude:**
```
Create unit tests for resume matcher:

1. test_high_score_match - Test matching resume with very similar job description
2. test_low_score_match - Test mismatched resume and job
3. test_partial_match - Test resume with some matching skills
4. test_invalid_input - Test with empty resume/job description
5. test_response_format - Verify response has score, reasoning, key_matches, gaps

Use pytest framework and mock OpenAI calls if needed.
```

**Placeholder:**

```python
# tests/test_matcher.py

import pytest
from tools.jd_matcher import match_resume_to_job

@pytest.fixture
def sample_resume():
    return "Python developer with 3 years FastAPI experience"

@pytest.fixture
def sample_job():
    return "Looking for Python backend developer with FastAPI knowledge"

def test_high_score_match(sample_resume, sample_job):
    # [PLACEHOLDER: Call matcher and assert score > 70]
    pass

def test_low_score_match(sample_resume):
    # [PLACEHOLDER: Call matcher with unrelated job description]
    pass

def test_response_format(sample_resume, sample_job):
    # [PLACEHOLDER: Verify response has required keys]
    pass
```

### 14.2 Create tests/test_whatsapp.py

**AI Prompt to give Claude:**
```
Create tests for WhatsApp integration:

1. test_send_message - Mock send_whatsapp_approval and verify message sent
2. test_webhook_approval - Mock POST to /webhook/whatsapp with approval response
3. test_webhook_rejection - Mock POST to /webhook/whatsapp with rejection response
4. test_invalid_response - Test webhook with invalid message body

Use unittest.mock to patch Twilio client.
```

**Placeholder:**

```python
# tests/test_whatsapp.py

import pytest
from unittest.mock import patch, MagicMock
from tools.whatsapp_handler import send_whatsapp_approval

@patch('twilio.rest.Client')
def test_send_message(mock_client):
    # [PLACEHOLDER: Mock Twilio client]
    # [PLACEHOLDER: Call send_whatsapp_approval]
    # [PLACEHOLDER: Assert message was sent]
    pass
```

### 14.3 Create tests/test_scraper.py

**AI Prompt to give Claude:**
```
Create tests for job scraper:

1. test_indeed_scraper - Mock Indeed website and verify jobs extracted
2. test_scraper_deduplication - Verify duplicate jobs removed
3. test_all_sources_combined - Verify scraper combines multiple sources
4. test_scraper_error_handling - Test scraper handles network errors

Mock HTTP requests using responses library.
```

**Placeholder:**

```python
# tests/test_scraper.py

import pytest
from unittest.mock import patch
from tools.job_scraper import scrape_indeed, scrape_all_sources

@patch('requests.get')
def test_indeed_scraper(mock_get):
    # [PLACEHOLDER: Mock Indeed HTML response]
    # [PLACEHOLDER: Call scrape_indeed]
    # [PLACEHOLDER: Verify jobs extracted]
    pass
```

### 14.4 Run Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## STEP 15: MANUAL EXECUTION TEST

### 15.1 Create test_full_workflow.py

```python
# test_full_workflow.py

from agents.workflow import agent_workflow, AgentState
from datetime import datetime

def test_full_workflow():
    """Test complete workflow with real resume."""
    
    initial_state = AgentState(
        resume="""
        John Doe
        Skills: Python, FastAPI, PostgreSQL, Docker
        Experience: 2 years backend development
        Projects: Built e-commerce platform
        """,
        portfolio_link="https://portfolio.example.com",
        github_link="https://github.com/johndoe",
        linkedin_link="https://linkedin.com/in/johndoe",
        jobs_to_process=[],
        current_job=None,
        match_score=0,
        match_reasoning="",
        user_approval=None,
        application_status="",
        applications_today=[],
        errors=[]
    )
    
    print("Starting workflow...")
    result = agent_workflow.invoke(initial_state)
    
    print(f"\n=== WORKFLOW COMPLETE ===")
    print(f"Jobs processed: {len(initial_state['jobs_to_process'])}")
    print(f"Applications sent: {len(result['applications_today'])}")
    print(f"Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors encountered:")
        for error in result['errors']:
            print(f"  - {error}")
    
    if result['applications_today']:
        print("\nApplications sent:")
        for app in result['applications_today']:
            print(f"  - {app['company']}: {app['title']} ({app['match_score']}%)")

if __name__ == "__main__":
    test_full_workflow()
```

### 15.2 Run Full Test

```bash
python test_full_workflow.py
```

---

## STEP 16: START FASTAPI SERVER

### 16.1 Run Server

```bash
python main.py
```

Or with auto-reload:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 16.2 Check Server Status

```
GET http://localhost:8000/
```

Should return:
```json
{"status": "Internship Agent Server Running"}
```

---

## STEP 17: CONFIGURE ENVIRONMENT FOR PRODUCTION

### 17.1 Use ngrok for Local Testing

```bash
ngrok http 8000
```

Get ngrok URL and update in .env as `SERVER_URL`

### 17.2 Update Twilio Webhook

1. Twilio Console → Phone Numbers
2. Select WhatsApp number
3. Messaging → A message comes in:
   ```
   https://your-ngrok-url/webhook/whatsapp
   ```

### 17.3 Upload Resume

```bash
curl -X POST http://localhost:8000/upload-resume \
  -F "file=@resume.pdf"
```

---

## STEP 18: ENABLE LANGSMITH MONITORING

### 18.1 Verify LangSmith Tracing

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_key
export LANGCHAIN_PROJECT=internship-agent

python -c "
from agents.workflow import agent_workflow
print('LangSmith tracing enabled')
"
```

### 18.2 Check LangSmith Dashboard

1. Go to https://smith.langchain.com
2. Project → internship-agent
3. View all runs, latency, token usage

---

## STEP 19: DOCKER DEPLOYMENT (Optional)

### 19.1 Create Dockerfile

**AI Prompt to give Claude:**
```
Create a Dockerfile for the internship agent application:

1. Use python:3.11 slim as base image
2. Set working directory to /app
3. Copy requirements.txt and install dependencies
4. Install Playwright browsers using playwright install chromium
5. Copy entire application code
6. Expose port 8000
7. CMD to run: python main.py

Add proper error handling and logging.
```

**Placeholder:**

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
```

### 19.2 Create docker-compose.yml

**AI Prompt to give Claude:**
```
Create docker-compose.yml that:

1. Defines two services: app and postgres
2. App service:
   - Builds from current Dockerfile
   - Maps port 8000 to 8000
   - Sets environment variables from .env
   - Depends on postgres
   - Mounts volumes for data persistence

3. Postgres service:
   - Uses postgres:15 image
   - Sets POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
   - Maps port 5432
   - Mounts volume for data persistence

Include proper healthchecks and error handling.
```

**Placeholder:**

```yaml
# docker-compose.yml

version: '3.8'

services:
  app:
    # [PLACEHOLDER: Build and container configuration]
    
  postgres:
    # [PLACEHOLDER: PostgreSQL configuration]
```

### 19.3 Build and Run Docker

```bash
docker-compose up --build
```

---

## STEP 20: DEPLOYMENT TO CLOUD

### Option A: Deploy to Heroku

```bash
# 1. Install Heroku CLI
# 2. Login to Heroku
heroku login

# 3. Create Heroku app
heroku create internship-agent

# 4. Set environment variables
heroku config:set OPENAI_API_KEY=sk-...
heroku config:set LANGCHAIN_API_KEY=ls_...
# ... (set all from .env)

# 5. Deploy
git push heroku main
```

### Option B: Deploy to AWS EC2

```bash
# 1. Launch EC2 instance (Ubuntu 22.04)
# 2. SSH into instance
ssh -i key.pem ubuntu@instance-ip

# 3. Install dependencies
sudo apt update
sudo apt install python3-pip postgresql postgresql-contrib

# 4. Clone repo and setup
git clone your-repo-url
cd internship-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure .env with RDS database
# 6. Start application with systemd service

# Create /etc/systemd/system/internship-agent.service
# [PLACEHOLDER: Add systemd service configuration]

# Start service
sudo systemctl start internship-agent
sudo systemctl enable internship-agent
```

### Option C: Deploy to DigitalOcean App Platform

```bash
# 1. Connect GitHub repo to DigitalOcean
# 2. Create app.yaml in root:

name: internship-agent
services:
  - name: api
    github:
      repo: your-username/internship-agent
      branch: main
    build_command: pip install -r requirements.txt
    run_command: python main.py
    envs:
      - key: OPENAI_API_KEY
        value: ${OPENAI_API_KEY}
      # ... add all env vars
    http_port: 8000

# 3. Deploy via DigitalOcean dashboard
```

---

## STEP 21: MONITOR & MAINTAIN

### 21.1 Setup Error Alerts

**AI Prompt to give Claude:**
```
Add error alerting using Sentry:

1. Go to sentry.io and create account
2. Create new project for Python
3. In the application, add Sentry integration:
   - Initialize Sentry SDK
   - Capture all exceptions
   - Add breadcrumbs for debugging
   - Track performance metrics
```

**Placeholder:**

```python
# Add to main.py

import sentry_sdk

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    traces_sample_rate=1.0
)

# All exceptions will be automatically captured
```

### 21.2 Setup Logging

```python
# utils/logging.py

import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """Setup application logging."""
    # [PLACEHOLDER: Configure rotating file handler]
    # [PLACEHOLDER: Set log format with timestamp]
    # [PLACEHOLDER: Log to both file and console]
    pass
```

### 21.3 Monitor Database

```bash
# Connect to PostgreSQL and check tables
psql -U postgres -d internship_agent -c "SELECT COUNT(*) FROM jobs;"
psql -U postgres -d internship_agent -c "SELECT COUNT(*) FROM applications;"
```

---

## STEP 22: FINAL CHECKLIST BEFORE GOING LIVE

- [ ] All environment variables configured in .env
- [ ] Database initialized with all tables
- [ ] OpenAI, LangSmith, Twilio, SendGrid API keys validated
- [ ] Resume parser tested with actual resume
- [ ] Job scraper returns 5+ jobs
- [ ] Resume matcher scores jobs correctly
- [ ] WhatsApp approval flow tested end-to-end
- [ ] Auto-apply tested on 1-2 real job postings
- [ ] Email summaries generating correctly
- [ ] LangGraph workflow completes without errors
- [ ] LangSmith dashboard shows all traces
- [ ] Scheduler configured for daily 9 AM execution
- [ ] FastAPI server responds to health checks
- [ ] Webhook endpoint receiving WhatsApp messages correctly
- [ ] Error alerts configured and working
- [ ] Database backups configured
- [ ] Rate limiting implemented for APIs
- [ ] Application logs being collected
- [ ] Docker image builds successfully
- [ ] Production environment variables set

---

## STEP 23: DAILY OPERATION

### User's Daily Workflow:

1. **9:00 AM** - Agent automatically runs
2. **Agent Flow:**
   - Scrapes internships from Indeed, internship.com, LinkedIn
   - Matches with user's resume using LLM
   - Sends WhatsApp messages for high-match jobs (70%+)
3. **User Action** - Within 24 hours:
   - User receives WhatsApp: "Python Intern @TechCorp - Match: 85%"
   - User replies ✅ to approve or ❌ to skip
4. **Agent Action** - Upon approval:
   - Auto-fills application form
   - Submits application
   - Logs to database
5. **9:30 AM** - User receives:
   - **Email:** Daily summary with all applications sent
   - **WhatsApp:** Quick summary of day's applications

---

## STEP 24: TROUBLESHOOTING

### Issue: "ModuleNotFoundError: No module named 'langgraph'"

```bash
pip install --upgrade langgraph langchain
```

### Issue: "WhatsApp messages not arriving"

Check:
1. Twilio phone number has WhatsApp enabled
2. Your personal number is verified in Twilio
3. .env has correct TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN

### Issue: "Database connection refused"

```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# If not running:
# Windows: Start PostgreSQL from Services
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
```

### Issue: "OpenAI API rate limit exceeded"

Add delay between API calls:

```python
import time
time.sleep(1)  # Add 1 second delay
```

### Issue: "Form filling times out"

Increase timeout in application_filler.py:

```python
await page.goto(job_link, timeout=60000)  # 60 second timeout
```

### Issue: "LangSmith traces not showing"

Verify in Python:

```python
from langsmith import Client
client = Client()
print(client.list_projects())  # Should list your projects
```

---

## QUICK REFERENCE: KEY FILES

| File | Purpose |
|------|---------|
| config/settings.py | Environment configuration |
| config/prompts.py | LLM prompts |
| db/models.py | Database models |
| db/database.py | Database connection |
| tools/resume_parser.py | Parse resume |
| tools/job_scraper.py | Scrape jobs |
| tools/jd_matcher.py | Match resume-JD |
| tools/whatsapp_handler.py | WhatsApp messaging |
| tools/application_filler.py | Auto-apply |
| tools/email_handler.py | Email summaries |
| agents/workflow.py | LangGraph workflow |
| scheduler/scheduler.py | Daily scheduling |
| main.py | FastAPI server |

---

## QUICK COMMANDS

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from db.database import init_db; init_db()"

# Test matcher
python -c "from tools.jd_matcher import match_resume_to_job; print(match_resume_to_job('resume', 'job description'))"

# Run tests
pytest tests/ -v

# Start server
python main.py

# Start scheduler only (no server)
python -c "from scheduler.scheduler import start_scheduler; s = start_scheduler(); import time; time.sleep(999999)"

# Full workflow test
python test_full_workflow.py

# Docker run
docker-compose up --build
```

---

## NEXT STEPS AFTER DEPLOYMENT

1. Monitor LangSmith dashboard for performance
2. Track application success rate
3. Adjust match score threshold based on approval rate
4. Add more job sources if needed
5. Optimize auto-apply for more job boards
6. Collect user feedback on matching quality
7. Implement resume version management
8. Add interview prep features
9. Build analytics dashboard
10. Scale to multiple user profiles

---

**END OF GUIDE**

Total Development Time: 60-75 hours
Deployment Time: 2-4 hours
Estimated Complete Setup: 70-80 hours (2-3 weeks part-time)
