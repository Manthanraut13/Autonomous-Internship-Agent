# Setup & Dependencies

## Requirements.txt

```
# LangGraph & LangChain
langgraph==0.0.21
langchain==0.1.13
langchain-openai==0.1.1
langchain-community==0.1.1
langsmith==0.1.9

# LLM Provider
openai==1.3.0

# Integrations
twilio==8.10.0  # WhatsApp
sendgrid==6.10.0  # Email
psycopg2-binary==2.9.9  # PostgreSQL
SQLAlchemy==2.0.23

# Web Scraping & Automation
selenium==4.15.0
playwright==1.40.0
requests==2.31.0
beautifulsoup4==4.12.2

# Scheduling
APScheduler==3.10.4

# API & Server
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.2

# Utilities
python-dotenv==1.0.0
pydantic-settings==2.1.0
```

## .env File

```env
# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_...
LANGCHAIN_PROJECT=internship-agent

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890
USER_WHATSAPP_NUMBER=+1234567890

# SendGrid (Email)
SENDGRID_API_KEY=SG....
SENDER_EMAIL=agent@yourdomain.com
RECIPIENT_EMAIL=user@gmail.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/internship_agent

# Job Scraping
INDEED_API_KEY=optional  # or use web scraping
LINKEDIN_COOKIES=optional  # for LinkedIn scraping

# Application URLs (indeed, linkedin, etc.)
JOB_SOURCES=[  # comma-separated: indeed, linkedin, internship.com
    "indeed",
    "linkedin",
    "internship.com"
]

# Agent Config
MATCH_SCORE_THRESHOLD=70
APPROVAL_TIMEOUT_HOURS=24
AUTO_REJECT_ON_TIMEOUT=true
```

## Installation Steps

```bash
# 1. Create virtual env
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup database
python -c "from db.database import init_db; init_db()"

# 4. Download Playwright browsers (for form filling)
playwright install chromium

# 5. Test LangSmith connection
python -c "from langsmith import Client; print(Client().list_projects())"
```

## Key Configuration Files

### config/settings.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4"
    match_score_threshold: int = 70
    approval_timeout_hours: int = 24
    database_url: str
    twilio_account_sid: str
    twilio_auth_token: str
    sendgrid_api_key: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### config/prompts.py
```python
MATCH_SYSTEM_PROMPT = """You are an expert resume-job matching agent.
Analyze the resume and job description.
Return ONLY valid JSON with:
{
  "score": <0-100>,
  "reasoning": "<explanation>",
  "key_matches": ["skill1", "skill2"],
  "gaps": ["missing_skill1"]
}"""

APPLICATION_EMAIL_PROMPT = """Generate a professional email for this job application.
Keep it concise (150 words max).
Highlight: relevant projects, skills match, GitHub/portfolio link.
Job: {job_title}
Company: {company}"""
```

## Database Schema

```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE,
    title VARCHAR(255),
    company VARCHAR(255),
    description TEXT,
    link VARCHAR(500),
    source VARCHAR(50),  -- indeed, linkedin, etc
    scraped_at TIMESTAMP,
    match_score FLOAT,
    status VARCHAR(50)  -- pending, approved, rejected, applied
);

CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    applied_at TIMESTAMP,
    application_id VARCHAR(255),
    status VARCHAR(50),  -- submitted, pending, rejected, accepted
    application_link VARCHAR(500)
);

CREATE TABLE whatsapp_responses (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    user_approval BOOLEAN,
    responded_at TIMESTAMP,
    message_sid VARCHAR(255)
);
```

## Running the Agent

### Option 1: Daily Scheduler
```bash
python scheduler.py
# Runs daily at 9 AM (configured in scheduler.py)
```

### Option 2: FastAPI Server (for WhatsApp webhooks)
```bash
python main.py
# Starts server at http://localhost:8000
# Webhook endpoint: POST /webhook/whatsapp
```

### Option 3: Manual Execution
```python
from agents.workflow import agent_workflow
result = agent_workflow.invoke(initial_state)
```

## Monitoring with LangSmith

1. Go to https://smith.langchain.com
2. Create API key in settings
3. Set `LANGCHAIN_API_KEY` in .env
4. View runs, latency, token usage in dashboard
5. Setup alerts for failures

## Debugging

```bash
# Enable debug logging
export DEBUG=true
python main.py

# Check LangSmith traces
python -c "from langsmith import Client; c = Client(); print(c.list_runs('internship-agent', limit=5))"

# Test Twilio connection
python -c "from twilio.rest import Client; c = Client('SID', 'TOKEN'); print(c.api.account.fetch())"

# Test DB connection
python -c "from db.database import SessionLocal; s = SessionLocal(); print(s.execute('SELECT 1').fetchone())"
```

## API Endpoints (FastAPI)

```
POST /webhook/whatsapp
- Receives WhatsApp responses (job approval/rejection)
- Payload: { "job_id": "1", "approval": true }

POST /apply
- Manually trigger application for a job
- Payload: { "job_id": "1" }

GET /status
- Get today's applications summary

POST /upload-resume
- Upload new resume (multipart/form-data)
```

## Docker (Optional)

```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t internship-agent .
docker run -p 8000:8000 --env-file .env internship-agent
```

## Next Steps

1. Configure `.env` with your API keys
2. Setup PostgreSQL database
3. Test LLM matching: `python test_matcher.py`
4. Test WhatsApp sending: `python test_whatsapp.py`
5. Run full workflow: `python scheduler.py`
