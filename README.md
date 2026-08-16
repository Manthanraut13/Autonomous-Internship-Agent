# 🤖 Autonomous Internship Agent

An AI-powered autonomous agent that scrapes real-time AI/ML internship openings from multiple job platforms, scores each listing against your resume using Groq LLM, delivers a curated CSV report to your email, sends a WhatsApp summary to your phone — and runs fully automated twice a day at **9:00 AM** and **9:00 PM IST** via GitHub Actions.

Includes a secure **React CRM Dashboard** deployed on Render for tracking applications, managing job statuses (Applied / Not Applied / Inbox), and triggering live pipeline runs from any browser.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔍 **Multi-Source Job Scraping** | Fetches live listings from Remotive, Arbeitnow, Himalayas, LinkedIn (via scraping), and JSearch APIs |
| 🧠 **AI Resume-JD Matching** | Groq LLM (`llama-3.1-8b-instant`) scores each job 0–100 across 4 dimensions: Tech Stack, Domain Alignment, Seniority Level, and Project Relevance |
| 🔄 **Iterative Deduplication Loop** | Loops through multiple scraping waves until exactly 25 unique, qualified AI listings are found — with strict cross-run database deduplication |
| 📧 **Automated Email Reports** | Delivers a structured CSV with direct apply links to your inbox via Gmail OAuth 2.0 API |
| 📲 **WhatsApp Notifications** | Sends a quick summary alert to your phone via Twilio WhatsApp |
| ⏰ **Dual Daily Cron Schedule** | Runs automatically at 9:00 AM and 9:00 PM IST via GitHub Actions (100% free) |
| 🖥️ **Secure CRM Dashboard** | React-based dark-mode UI with admin login, job tracking (Inbox → Applied → Not Applied), delete, and live terminal streaming |
| 🔒 **Backend Authentication** | HMAC-SHA256 signed tokens protect all API endpoints; constant-time password comparison prevents timing attacks |
| 💾 **PostgreSQL + SQLite Fallback** | Shared cloud PostgreSQL for production; automatic SQLite fallback for local development |

---

## 🏗️ System Architecture

```
  ┌──────────────────────────────────────────────────────────────┐
  │              GitHub Actions (9:00 AM & 9:00 PM IST)          │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │ 1. Parse Resume PDF                                    │  │
  │  │ 2. Generate 10 AI Search Queries                       │  │
  │  │ 3. Scrape Remotive, Arbeitnow, Himalayas, LinkedIn     │  │
  │  │ 4. Deduplicate against DB (cross-run)                  │  │
  │  │ 5. Score with Groq LLM (4-dimension rubric)            │  │
  │  │ 6. Loop until 25 unique matches found                  │  │
  │  │ 7. Export CSV → Email via Gmail OAuth                   │  │
  │  │ 8. Send WhatsApp summary via Twilio                    │  │
  │  └────────────────────┬───────────────────────────────────┘  │
  └───────────────────────┼──────────────────────────────────────┘
                          │  Writes 25 new job records
                          ▼
  ┌──────────────────────────────────────────────────────────────┐
  │              Shared PostgreSQL Database (Render)             │
  │              Stores all jobs, statuses, run logs             │
  └───────────────────────▲──────────────────────────────────────┘
                          │  Reads & Updates
                          │
  ┌───────────────────────┴──────────────────────────────────────┐
  │              Render Web Service (Free Tier)                  │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  FastAPI Backend (Secure Auth + REST API + SSE)        │  │
  │  │  React CRM Dashboard (Login, CRM Table, Live Terminal) │  │
  │  └────────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn, SQLAlchemy |
| **AI / LLM** | Groq API (`llama-3.1-8b-instant`), LangChain |
| **Database** | PostgreSQL (production), SQLite (local fallback) |
| **Frontend** | React 18, TypeScript, Vite |
| **Scheduling** | GitHub Actions Cron, APScheduler (in-process) |
| **Email** | Gmail OAuth 2.0 API (CSV attachments) |
| **Messaging** | Twilio WhatsApp REST API |
| **PDF Parsing** | PyMuPDF (`fitz`), PyPDF2 |
| **Deployment** | Render (Web Service + PostgreSQL), GitHub Actions |

---

## 📁 Repository Structure

```
Autonomous-Internship-Agent/
├── .github/
│   └── workflows/
│       └── cron_pipeline.yml    # GitHub Actions: 9 AM & 9 PM daily cron
├── config/
│   ├── settings.py              # Pydantic BaseSettings (.env loader + validators)
│   ├── prompts.py               # LLM scoring rubric (4-dimension prompt)
│   └── __init__.py
├── db/
│   ├── database.py              # SQLAlchemy engine (PostgreSQL + SQLite fallback)
│   ├── models.py                # Job & PipelineRun ORM models
│   └── __init__.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # React CRM Dashboard (Login, CRM, Pipeline, Settings)
│   │   ├── App.css              # Dark-mode design system
│   │   └── main.tsx             # React entry point
│   ├── dist/                    # Production build (served by FastAPI)
│   ├── package.json
│   └── vite.config.ts           # Vite config with /api proxy
├── tools/
│   ├── job_api.py               # Multi-source job fetcher (Remotive, Arbeitnow, Himalayas, LinkedIn)
│   ├── jd_matcher.py            # Groq LLM resume-JD scorer with rate-limit pacing
│   ├── resume_parser.py         # PDF text extractor & AI query generator
│   ├── csv_exporter.py          # Structured CSV report generator
│   ├── email_sender.py          # Gmail OAuth 2.0 CSV email sender
│   ├── whatsapp_handler.py      # Twilio WhatsApp summary dispatcher
│   ├── apollo_scraper.py        # Apollo.io fallback scraper
│   └── __init__.py
├── main.py                      # FastAPI server: Auth, CRM APIs, SSE streaming, APScheduler
├── run_pipeline.py              # CLI pipeline runner (--target 25 --threshold 70)
├── run_scheduler.py             # Standalone APScheduler daemon (9 AM & 9 PM)
├── requirements.txt             # Python dependencies
├── DEPLOYMENT.md                # Full Render + GitHub Actions deployment guide
├── .env.example                 # Environment variable template
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Python 3.10+
- Node.js 18+
- Groq API Key (free at [console.groq.com](https://console.groq.com/))
- Gmail OAuth credentials (`credentials.json` and `token.json`)
- Twilio Account (for WhatsApp — optional)

### 1. Clone & Install

```bash
git clone https://github.com/Manthanraut13/Autonomous-Internship-Agent.git
cd Autonomous-Internship-Agent

# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your keys:

```ini
# Required
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
RECIPIENT_EMAIL=your-email@gmail.com

# Dashboard Login
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
AUTH_SECRET_KEY=random_32_char_secret_key

# Database (leave empty for automatic SQLite fallback)
DATABASE_URL=

# WhatsApp Notifications (optional)
TWILIO_ACCOUNT_SID=AC_your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+14155238886
USER_WHATSAPP_NUMBER=+91XXXXXXXXXX
```

### 3. Place Your Resume

Save your resume PDF in the project root or as `data/current_resume.pdf`.

### 4. Build Frontend & Run

```bash
# Build the React dashboard
cd frontend && npm install && npm run build && cd ..

# Start the server
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) → Log in with your admin credentials.

### 5. Run Pipeline from CLI

```bash
.\venv\Scripts\python.exe run_pipeline.py --target 25 --threshold 70
```

This will scrape, score, save, email, and notify — all in one command.

---

## ☁️ Production Deployment

The agent is deployed using **Render** (Web Service + PostgreSQL) and **GitHub Actions** (automated cron).

See [DEPLOYMENT.md](DEPLOYMENT.md) for the complete step-by-step guide.

### Deployment Architecture

| Component | Platform | Cost |
|---|---|---|
| CRM Dashboard & API | Render Web Service | Free |
| Shared Database | Render PostgreSQL | Free |
| 9 AM & 9 PM Cron Runner | GitHub Actions | Free (2,000 min/month) |
| Email Delivery | Gmail OAuth 2.0 API | Free |
| LLM Match Scoring | Groq API Free Tier | Free |
| WhatsApp Alerts | Twilio Sandbox | Free |

---

## 🖥️ Dashboard Features

### Secure Login
All dashboard access requires admin authentication. Unauthorized API requests return `401 Unauthorized`.

### Openings & CRM
- **Inbox (New)**: Freshly scraped listings awaiting your review.
- **Applied**: Listings you've marked as applied (tracks your application count).
- **Not Applied**: Listings you've decided to skip.
- **All Listings**: Complete view across all statuses.
- **Actions**: Apply (opens external link), Mark Applied, Mark Not Applied, Restore to Inbox, Delete.

### Live Pipeline Terminal
Stream real-time execution logs directly in the browser when running a pipeline — shows each step from resume parsing through email delivery.

### Settings
View active cron schedules, AI model configuration, notification targets, and candidate profile.

---

## 🔍 AI Search Queries

The agent generates targeted search queries focused on AI/ML internship roles:

- AI Consultant Intern
- AI Automation Intern
- GenAI Developer Intern
- Agentic AI Intern
- LLM Engineer Intern
- AI ML Intern
- AI Python Developer Intern
- Full Stack AI Developer Intern
- AI Data Analyst Intern
- AI Automation Engineer Intern

---

## 📊 Scoring Rubric

Each job is evaluated by the Groq LLM across 4 weighted dimensions:

| Dimension | Weight | What It Measures |
|---|---|---|
| Tech Stack Alignment | 40% | Python, LangChain, FastAPI, ML frameworks, etc. |
| Domain Alignment | 30% | AI, GenAI, Automation, LLM, Agentic workflows |
| Seniority Match | 20% | Intern/Junior/Entry-level vs Senior/Lead |
| Project Relevance | 10% | Similarity to candidate's portfolio projects |

Scores range from **0** (completely irrelevant) to **100** (perfect match). Only listings scoring above the configured threshold (default: 70) are included in reports.

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Commit your changes: `git commit -m "Add my feature"`.
4. Push to the branch: `git push origin feature/my-feature`.
5. Open a Pull Request.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 👤 Author

**Manthan Raut**
- GitHub: [@Manthanraut13](https://github.com/Manthanraut13)
- Email: manthanr141@gmail.com
- LinkedIn: [linkedin.com/in/manthan-raut](https://linkedin.com/in/manthan-raut)
