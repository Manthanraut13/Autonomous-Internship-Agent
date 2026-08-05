# 🤖 Autonomous Internship & Job Agent

An AI-powered autonomous agent that searches real-time job openings, matches them against your resume using Groq LLM (Llama 3.3 70B), sends interactive 1-by-1 WhatsApp approval prompts, and automatically fills application forms live in a visible browser using Playwright.

Includes a dynamic React CRM Dashboard for real-time tracking, application status management, and manual pipeline triggers.

---

## ✨ Features

- **🌐 Real-Time Job Fetching**: Pulls live job listings from multiple APIs (Arbeitnow, Remotive, Himalayas, Adzuna) with direct apply links to Greenhouse, Lever, and corporate portals.
- **📄 Resume Parsing & AI Matching**: Extracts skills and experience from your resume PDF/TXT and scores each job from 0 to 100 with detailed LLM reasoning (Groq Llama-3.3-70b-versatile).
- **📱 Sequential WhatsApp Approval**: Sends instant job match alerts to your WhatsApp via Twilio. Reply `yes` to auto-apply or `no` to skip. The next queued job prompt is dispatched automatically.
- **🎭 Automated Form Filler (Playwright)**: Launches a visible Chromium browser to navigate job portals, click external apply links, fill candidate details (Name, Email, Phone, PDF Resume, LinkedIn, GitHub, Salary, Availability), select dropdown options, and submit applications.
- **📊 Dynamic CRM Dashboard**: A React frontend built with Vite, Tailwind CSS, and Lucide Icons to track total jobs, application statuses, match score distributions, and trigger job searches directly from the UI.
- **💾 Dual Database Engine**: Supports PostgreSQL with automatic fallback to local SQLite (`data/agent.db`) for zero-setup local execution.

---

## 🏗️ System Architecture

```text
               📄 Candidate Resume PDF / TXT
                            │
                            ▼
     🔍 Job Fetcher (Arbeitnow, Remotive, Himalayas, Adzuna)
                            │
                            ▼
     🤖 Resume-JD Matcher (Groq LLM Llama-3.3-70b-versatile)
                            │
                   [Match Score ≥ 50%]
                            │
                            ▼
               💾 Save to Database (Job Model)
                            │
                            ▼
             📱 Twilio WhatsApp Approval Prompt
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
            [User: "yes"]          [User: "no"]
                │                       │
                ▼                       ▼
   🎭 Playwright Auto-Apply     🚫 Mark as Rejected
   (Visible Chromium Window)            │
                │                       └─────────┐
                ▼                                 │
   🎉 WhatsApp Confirmation &                     ▼
      Submit to Database               📲 Dispatch Next Queued
                │                        WhatsApp Prompt
                └─────────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Backend Framework**: Python 3.10+, FastAPI, Uvicorn
- **AI & LLM**: Groq API (`llama-3.3-70b-versatile`), LangChain
- **Browser Automation**: Playwright (Sync API inside `ThreadPoolExecutor`)
- **Database & ORM**: SQLAlchemy, PostgreSQL, SQLite (Auto-Fallback)
- **Messaging**: Twilio WhatsApp REST API
- **Frontend / CRM**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons
- **PDF Extraction**: PyMuPDF (`fitz`), PyPDF2

---

## 📁 Repository Structure

```text
Autonomus Internship Agent/
├── agents/                  # LangGraph / Workflow nodes
│   └── __init__.py
├── config/                  # Configuration & Prompts
│   ├── settings.py          # Pydantic BaseSettings (.env loader)
│   ├── prompts.py           # LLM Prompts (Matcher, Email, Summary)
│   └── __init__.py
├── db/                      # Database Layer
│   ├── database.py          # SQLAlchemy engine & session factory (SQLite fallback)
│   ├── models.py            # Job, Application, WhatsAppResponse models
│   └── __init__.py
├── data/                    # Storage for current_resume.pdf, SQLite DB, screenshots
├── frontend/                # React CRM Dashboard
│   ├── dist/                # Production build (served by FastAPI)
│   ├── src/                 # React components (App.tsx, main.tsx)
│   ├── package.json
│   └── vite.config.ts
├── scheduler/               # APScheduler daily job entries
│   └── __init__.py
├── tools/                   # Core Utility Modules
│   ├── application_filler.py # Playwright automated form filler
│   ├── job_api.py           # Multi-source job fetcher (Arbeitnow, Remotive, etc.)
│   ├── job_scraper.py       # Fallback HTML scrapers
│   ├── jd_matcher.py        # Groq LLM match evaluator
│   ├── resume_parser.py     # PDF text extractor & section parser
│   ├── whatsapp_handler.py  # Twilio WhatsApp sender & summary generator
│   └── __init__.py
├── utils/                   # General helper utilities
│   └── __init__.py
├── main.py                  # FastAPI server & Twilio WhatsApp webhook listener
├── run_pipeline.py          # CLI runner for end-to-end job search pipeline
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── README.md                # Project documentation
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- Python 3.10+
- Node.js 18+ (for building the frontend)
- Twilio Account (for WhatsApp messaging sandbox)
- Groq API Key (Free key at [console.groq.com](https://console.groq.com/))

### 2. Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Manthanraut13/Autonomous-Internship-Agent.git
   cd "Autonomous-Internship-Agent"
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

5. **Configure Environment Variables**:
   Copy `.env.example` or create a `.env` file in the root directory:
   ```ini
   # Groq LLM
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile

   # Twilio WhatsApp
   TWILIO_ACCOUNT_SID=AC_your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=
   USER_WHATSAPP_NUMBER=

   # Candidate Profile (used for auto-filling job forms)
   CANDIDATE_NAME=
   CANDIDATE_EMAIL=
   CANDIDATE_PHONE=
   CANDIDATE_GITHUB=
   CANDIDATE_LINKEDIN=

   # Database (PostgreSQL string or leave as-is for automatic SQLite fallback)
   DATABASE_URL=
   ```

6. **Place Your Resume PDF**:
   Save your resume PDF as `data/current_resume.pdf` or in the root folder as `Manthan_Raut_Resume (1).pdf`.

---

## 💻 Running the Application

### Option A: Running the CRM Dashboard & FastAPI Server

Start the Uvicorn web server:
```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

From the dashboard, you can:
- View live application metrics & match score analytics.
- Filter jobs by status (`applied`, `pending`, `rejected`) or source platform.
- Click **"Trigger Auto-Apply"** to launch the visible Playwright browser on demand.
- Run a fresh job search pipeline directly from the dashboard controls.

---

### Option B: Running the Autonomous Job Pipeline (CLI)

Run the job search pipeline manually from your terminal:

```powershell
# Search for Python developer jobs with a minimum match score threshold of 50
.\venv\Scripts\python.exe run_pipeline.py --query "python developer" --limit 5 --threshold 50
```

**Pipeline Workflow**:
1. Parses `data/current_resume.pdf`.
2. Fetches 5 live job listings from Arbeitnow / Remotive / Himalayas.
3. Evaluates fit using Groq LLM (Llama 3.3 70B).
4. Saves qualifying jobs to the database.
5. Sends an interactive approval prompt to your WhatsApp for the 1st match.

---

## 📱 WhatsApp Webhook Setup (Twilio + Ngrok)

To receive your WhatsApp replies (`yes` / `no`) and auto-trigger form submissions:

1. **Start Ngrok** to expose port 8000:
   ```bash
   ngrok http 8000
   ```
2. Copy the generated HTTPS forwarding URL (e.g. `https://a1b2c3d4.ngrok-free.app`).
3. Open your **[Twilio Sandbox Settings](https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox)**.
4. Set **WHEN A MESSAGE COMES IN** URL to:
   ```text
   https://a1b2c3d4.ngrok-free.app/webhook/whatsapp
   ```
5. Save settings. Now, replying `yes` on WhatsApp will instantly launch the Chromium browser, complete form fields, submit the application, and message back!

---

## 🧪 Verification & Testing

Test Playwright form auto-filling on a job posting:
```powershell
.\venv\Scripts\python.exe -c "
import asyncio, os
from tools.application_filler import auto_apply_to_job

result = asyncio.run(auto_apply_to_job(
    job_link='https://www.arbeitnow.com/jobs/companies/autoscout24/technical-seo-lead-486594',
    resume_pdf_path=os.path.abspath('data/current_resume.pdf')
))
print(result)
"
```

---


