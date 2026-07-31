# Autonomous Internship Agent - Complete Implementation Plan

## 1. SYSTEM ARCHITECTURE

```
Resume Upload
    ↓
Daily Scheduler (APScheduler)
    ↓
LangGraph Agent Workflow
    ├─ Job Scraper Node
    ├─ Resume Matcher Node (LLM)
    ├─ WhatsApp Approval Node
    ├─ Application Node
    └─ Summary Node
    ↓
Email + WhatsApp Notifications
```

## 2. TECH STACK

- **Framework**: LangGraph, LangChain
- **LLM**: OpenAI (GPT-4) or Claude
- **Job Sources**: Indeed (API), LinkedIn, Internship.com (web scraping)
- **WhatsApp**: Twilio SDK
- **Email**: SMTP / SendGrid
- **Monitoring**: LangSmith
- **Scheduling**: APScheduler
- **Database**: PostgreSQL (track applications, approvals)
- **Storage**: AWS S3 (resumes, portfolios)

## 3. CORE COMPONENTS

### A. Resume Parser & Embedder
```python
# Extract: skills, experience, education, projects
# Store embeddings for similarity matching
# Update in vector DB (Pinecone/Weaviate)
```

### B. Job Scraper
```python
# Daily scraper for internships
# Extract: title, company, description, link, requirements
# Store in PostgreSQL
```

### C. Resume-JD Matcher (LangChain Agent)
```python
# Input: Resume + Job Description
# Output: Match score (0-100) + reasoning
# Use semantic similarity + LLM-based matching
# Threshold: 70+
```

### D. WhatsApp Integration (Twilio)
```python
# Send: "Job Title @Company - Match: X%"
# Options: ✅ Approve / ❌ Reject
# Store user response in DB
# Timeout: 24hrs auto-reject
```

### E. Auto-Applicant
```python
# Pre-fill application with:
#   - Resume (PDF)
#   - Portfolio link
#   - GitHub profile
#   - LinkedIn profile
# POST to job application endpoint
# Log application ID
```

### F. Daily Summary Generator
```python
# Aggregate: Applied count, success rate, profiles sent
# Generate email + WhatsApp report
# Include: Application links, company names, match scores
```

## 4. LANGGRAPH WORKFLOW STATE

```python
class AgentState(TypedDict):
    job_id: str
    job_data: dict  # title, description, link, company
    resume: str
    match_score: float
    match_reasoning: str
    user_approval: bool  # from WhatsApp
    application_status: str  # pending, approved, rejected, applied
    error: Optional[str]
    timestamp: datetime
```

## 5. LANGGRAPH NODE FLOW

```
START
  ↓
[1] Fetch Jobs (daily scheduler)
  ↓
[2] FOR EACH JOB:
    ├─ Parse Job Description
    ├─ Calculate Match Score (LLM)
    ├─ IF score > 70:
    │   ├─ Send WhatsApp Approval Message
    │   ├─ WAIT for user response (24h timeout)
    │   ├─ IF approved:
    │   │   ├─ Fill Application Form
    │   │   ├─ Submit Application
    │   │   ├─ Log to DB
    │   │   └─ Add to summary
    │   └─ IF rejected or timeout:
    │       └─ Log rejection
    └─ IF score ≤ 70:
        └─ Log as non-matching
  ↓
[3] Generate Daily Summary
  ↓
[4] Send Email + WhatsApp Report
  ↓
END
```

## 6. FILE STRUCTURE

```
internship-agent/
├── config/
│   ├── settings.py (API keys, thresholds)
│   └── prompts.py (LLM prompts)
├── agents/
│   ├── __init__.py
│   ├── workflow.py (LangGraph graph definition)
│   └── nodes/
│       ├── scraper_node.py
│       ├── matcher_node.py
│       ├── approval_node.py
│       ├── applicant_node.py
│       └── summary_node.py
├── tools/
│   ├── resume_parser.py
│   ├── jd_matcher.py
│   ├── whatsapp_handler.py
│   ├── email_handler.py
│   ├── application_filler.py
│   └── job_scraper.py
├── db/
│   ├── models.py (SQLAlchemy)
│   ├── database.py
│   └── queries.py
├── utils/
│   ├── embeddings.py
│   └── logging.py
├── scheduler.py (APScheduler entry)
├── main.py (FastAPI server for WhatsApp webhooks)
└── requirements.txt
```

## 7. IMPLEMENTATION STEPS

### Phase 1: Setup
- [ ] Create FastAPI server for WhatsApp webhooks
- [ ] Setup PostgreSQL + Schema
- [ ] Configure Twilio, SendGrid, OpenAI
- [ ] Setup LangSmith tracing

### Phase 2: Core Agents
- [ ] Build resume parser & embeddings
- [ ] Build job scraper (Indeed, LinkedIn)
- [ ] Build LangGraph workflow with nodes
- [ ] Build LLM-based matcher agent

### Phase 3: Integrations
- [ ] WhatsApp approval handler (Twilio)
- [ ] Auto-applicant (Selenium/Playwright for form filling)
- [ ] Email summaries (SendGrid)
- [ ] Application tracker (DB logging)

### Phase 4: Automation
- [ ] APScheduler daily cron
- [ ] Error handling + retry logic
- [ ] LangSmith monitoring dashboard
- [ ] Rate limiting for APIs

## 8. KEY PROMPTS (LangChain)

### Matcher Prompt:
```
Analyze resume and job description. 
Calculate relevance score (0-100).
Consider: skills match, experience level, required qualifications.
Return JSON: {"score": int, "reasoning": str, "key_matches": [str], "gaps": [str]}
```

### Applicant Prompt:
```
Given user data (resume, portfolio, GitHub, LinkedIn), 
generate application email body that matches this job description.
Keep it concise, highlight relevant projects.
```

## 9. APPROVAL FLOW (WhatsApp)

```
Bot: "Python Intern @TechCorp - Match: 85%
     Skills: Python ✓, FastAPI ✓, PostgreSQL ✓
     ✅ Apply  |  ❌ Skip"

User clicks ✅ → Node: submission_node → Stores approval
             → Auto-fills & submits application
             → Logs: "Applied to TechCorp"

User clicks ❌ → Logs rejection
```

## 10. DAILY SUMMARY (Email + WhatsApp)

```
📊 Internship Agent Report - July 23, 2026

Applied Today: 3
Success Rate: 85% (matches sent: 4)

✅ Applications:
1. Python Intern @TechCorp (85% match)
2. Backend Eng @StartupXYZ (78% match)  
3. Data Analyst @DataCo (92% match)

⏳ Pending Approval: 1
❌ Rejected: 1

View applications: [dashboard_link]
```

## 11. LANGSMITH INTEGRATION

```python
from langsmith import traceable

@traceable(name="match_job_to_resume")
def match_job(resume, job_desc):
    # Automatically traces to LangSmith
    # View: Runs, latency, token usage, errors
```

## 12. CRITICAL IMPLEMENTATION DETAILS

**Resume Matching**:
- Use vector similarity (embeddings) + LLM reasoning
- Don't rely on keyword matching alone

**Form Filling**:
- Use Selenium/Playwright for complex forms
- Fallback: Generate email + manual submission link

**Error Handling**:
- Retry failed applications (exponential backoff)
- Alert on scraper failures
- Manual approval required for edge cases

**Privacy**:
- Encrypt stored resumes
- No resume data to LLM unless necessary
- Use private LangSmith workspace

**Rate Limiting**:
- Job scraper: 1 call/day per source
- WhatsApp: 1 msg per 5 seconds
- Application submission: throttle to 2/minute

## 13. DEPLOYMENT OPTIONS

- **Local + Cloud Scheduler**: FastAPI on server, APScheduler daily
- **Serverless**: AWS Lambda + EventBridge (cost-effective)
- **Docker**: Containerize for easy deployment
- **Monitoring**: LangSmith + Sentry for errors

## 14. OPTIONAL ENHANCEMENTS

- [ ] Multi-profile support (different resumes for different roles)
- [ ] Salary/location filtering
- [ ] Interview prep from job descriptions
- [ ] Analytics dashboard (match distribution, success rate)
- [ ] Slack integration (alternative to WhatsApp)
- [ ] Custom ML model for matching (vs LLM)
