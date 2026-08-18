# Autonomous Internship Agent

An enterprise-grade autonomous intelligence system designed to automate end-to-end sourcing, matching, and tracking of high-growth AI and Machine Learning internship openings.

The platform continuously monitors top startup job ecosystems, extracts candidate profiles from PDF resumes, performs deep multi-dimensional matching via Groq LLMs, delivers formatted CSV digests via Gmail OAuth 2.0, dispatches WhatsApp alerts via Twilio, and hosts an interactive web dashboard for real-time application pipeline tracking.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [System Architecture](#system-architecture)
- [Technical Stack](#technical-stack)
- [Repository Structure](#repository-structure)
- [Scoring Rubric & Evaluation Logic](#scoring-rubric--evaluation-logic)
- [Dashboard & User Interface](#dashboard--user-interface)
- [Quick Start Guide](#quick-start-guide)
- [Environment Configuration](#environment-configuration)
- [Production Deployment](#production-deployment)
- [API Reference](#api-reference)
- [License & Author](#license--author)

---

## Key Capabilities

| Capability | Technical Implementation | Impact |
|---|---|---|
| **Startup-First Sourcing** | Cascading scraper targeting **LinkedIn Startups**, **Remotive Startups**, and **Himalayas Startups** | Prioritizes high-velocity startup teams and high-impact intern roles |
| **Strictly AI-Only Filtering** | Search vectors locked exclusively to AI, GenAI, LLM, Agentic AI, and ML domains | Eliminates noise from generic web, generic IT, or non-technical listings |
| **Internship-First Pre-Filtering** | Automated disqualification regex rejecting senior/lead roles (5+ YOE) | Focuses exclusively on student, trainee, and entry-level talent |
| **Groq LLM Match Engine** | High-throughput inference via `openai/gpt-oss-120b` with automatic model fallback cascade | Provides accurate, differentiated 0–100 match scoring in under 500ms |
| **Immediate Early-Stop Pipeline** | Traverses priority sources sequentially and halts execution once target quota (25 matches) is met | Reduces API latency and saves up to 80% of token consumption |
| **Automated Dispatch** | Dual-channel notification via Gmail OAuth 2.0 (CSV attachment) and Twilio WhatsApp API | Delivers decision-ready intelligence directly to inbox and mobile device |
| **Dual Daily Automation** | Automated serverless execution at **9:00 AM** and **9:00 PM IST** via GitHub Actions | Zero-maintenance, scheduled daily execution |
| **Glacial Precision CRM UI** | React 18 + Vite dashboard with live SSE streaming terminal, filters, and resume uploader | Centralized interface for application status tracking and manual pipeline execution |
| **Enterprise Security** | HMAC-SHA256 authenticated sessions with constant-time password verification | Protects API routes and dashboard controls against unauthorized access |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCHEDULED EXECUTION / MANUAL TRIGGER                     │
│               GitHub Actions (9:00 AM & 9:00 PM IST) OR Web UI              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. RESUME INTELLIGENCE ENGINE                         │
│   • Multi-engine PDF parser (PyMuPDF / pdfplumber / pypdf)                  │
│   • Extracts tech stack, projects, education, and domain competencies       │
│   • Computes 10 specialized AI search queries                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. PRIORITY-ORDERED SCRAPER CASCADE                       │
│   • Priority 1: LinkedIn Startup AI Internships (Direct & Startup filters)  │
│   • Priority 2: Remotive Startup AI Openings (Remote tech API)              │
│   • Priority 3: Himalayas Startup Openings (Remote engineering API)         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. DEDUPLICATION & SENIORITY FILTERING                    │
│   • Regex disqualification of Senior / Lead / Staff / 5+ YOE titles         │
│   • Cross-run database deduplication (URL hash + Title/Company signature)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      4. GROQ LLM EVALUATION ENGINE                          │
│   • Multi-model cascade: openai/gpt-oss-120b -> gpt-oss-20b -> qwen3.6-27b  │
│   • 4-dimension scoring rubric (Tech Stack, Domain, Seniority, Projects)    │
│   • 🛑 EARLY STOP: Halts immediately upon finding 25 qualified openings     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     5. PERSISTENCE & DISPATCH LAYER                         │
│   • Writes records to PostgreSQL (Production) / SQLite (Local)              │
│   • Generates timestamped CSV spreadsheet report                            │
│   • Dispatches email with CSV attachment via Gmail OAuth 2.0 API            │
│   • Sends formatted summary alert via Twilio WhatsApp API                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 6. INTERACTIVE WEB DASHBOARD (FASTAPI + REACT)              │
│   • Glacial Precision Design System (Hanken Grotesk, Steel Blue, Ice)       │
│   • Real-time SSE streaming console, application tracking, status updates   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Stack

| Layer | Technologies |
|---|---|
| **Backend Core** | Python 3.11, FastAPI, Uvicorn, Pydantic v2, Pydantic Settings |
| **AI Inference** | Groq API (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`), LangChain, LangSmith Tracing |
| **Database & ORM** | PostgreSQL (Render Cloud), SQLite (Local Fallback), SQLAlchemy 2.0 |
| **Frontend UI** | React 18, TypeScript, Vite 8, Vanilla CSS Design System, Lucide / Material Symbols |
| **Document Processing** | PyMuPDF (`fitz`), pdfplumber, pypdf |
| **Scraping & Ingestion** | Requests, BeautifulSoup4, Public API Integrations (LinkedIn, Remotive, Himalayas) |
| **Notification Services** | Google Gmail API (OAuth 2.0 MIME), Twilio Messaging API (WhatsApp), SendGrid API |
| **Scheduling & CI/CD** | GitHub Actions Cron, APScheduler (`AsyncIOScheduler`), Render Web Services |

---

## Repository Structure

```
Autonomous-Internship-Agent/
├── .github/
│   └── workflows/
│       └── cron_pipeline.yml       # GitHub Actions dual daily cron configuration
├── config/
│   ├── __init__.py
│   ├── prompts.py                  # AI 4-dimension scoring rubrics and schemas
│   └── settings.py                 # Pydantic BaseSettings environment manager
├── db/
│   ├── __init__.py
│   ├── database.py                 # SQLAlchemy connection pooling and multi-dialect manager
│   └── models.py                   # ORM models (Job, PipelineRun, ApplicationStatus)
├── frontend/
│   ├── public/                     # Static icons, SVG assets, favicon
│   ├── src/
│   │   ├── assets/                 # Brand illustrations
│   │   ├── App.css                 # Glacial Precision Design System stylesheet
│   │   ├── App.tsx                 # Core Dashboard application (React 18 + TypeScript)
│   │   ├── index.css               # Global CSS tokens, resets, and typography
│   │   └── main.tsx                # React DOM root entry point
│   ├── index.html                  # HTML5 shell (Hanken Grotesk & Material Symbols)
│   ├── package.json                # Frontend NPM scripts and dependencies
│   ├── tsconfig.json               # TypeScript compiler configuration
│   └── vite.config.ts              # Vite bundle configuration and proxy
├── new design/
│   ├── DESIGN.md                   # Glacial Precision UI/UX Design System Specification
│   ├── code.html                   # High-fidelity reference HTML mockup
│   └── screen.png                  # Visual design render snapshot
├── tools/
│   ├── __init__.py
│   ├── apollo_scraper.py           # Fallback Apollo API / HTML scraper
│   ├── csv_exporter.py             # CSV spreadsheet generator and file formatter
│   ├── email_sender.py             # Gmail OAuth 2.0 and SendGrid dispatchers
│   ├── jd_matcher.py               # Groq LLM JD-Resume evaluation and multi-model fallback
│   ├── job_api.py                  # Scraper priority cascade (LinkedIn, Remotive, Himalayas)
│   ├── resume_parser.py            # PDF parsing and dynamic AI search query generator
│   └── whatsapp_handler.py         # Twilio WhatsApp notification handler
├── .env.example                    # Sample environment template with documentation
├── .gitignore                      # Git exclusion rules
├── AGENT.md                        # Autonomous agent operational specification
├── DEPLOYMENT.md                   # Cloud deployment manual (Render + GitHub Actions)
├── DOCUMENTATION.md                # Comprehensive technical reference manual
├── main.py                         # FastAPI web server, authentication, and SSE streamer
├── requirements.txt                # Python backend dependencies
├── run_pipeline.py                 # Standalone autonomous CLI pipeline runner
└── run_scheduler.py                # Standalone local scheduler daemon
```

---

## Scoring Rubric & Evaluation Logic

Each discovered listing is evaluated against the candidate's parsed resume across four weighted dimensions:

| Dimension | Weight | Criteria | Scoring Logic |
|---|---|---|---|
| **Technical Stack Alignment** | 35% | Direct overlap in languages, frameworks, and AI toolkits | Evaluates Python, PyTorch, LangChain, Transformers, LLM APIs, and backend tooling |
| **Domain & Problem Alignment** | 30% | Relevance to core AI/ML domains | Evaluates focus in GenAI, Agentic AI, NLP, Computer Vision, RAG, and Automation |
| **Seniority & Internship Fit** | 20% | Fit for student / trainee / intern level | **Student/Intern/Trainee = 18–20 pts**; Entry-Level (0–2 YOE) = 10–14 pts; Senior/Lead (5+ YOE) = 0 pts (capped < 45) |
| **Demonstrated Project Evidence** | 15% | Practical implementation proof | Evaluates candidate projects, GitHub repositories, and production deployments |

- **Overall Score Range**: 0 to 100.
- **Qualification Threshold**: Listings with a composite score ≥ 70 are classified as qualified matches and saved to the database.

---

## Dashboard & User Interface

The web interface is built on the **Glacial Precision** design system, combining minimal cognitive load with high-density data management.

### Key Views & Components

1. **Fixed Navigation Sidebar (220px)**:
   - Dedicated access to **Dashboard**, **Jobs**, **Pipeline**, **Resume**, and **Settings**.
   - Persistent Agent Status widget displaying real-time monitoring pulse.
2. **Top System Header (64px)**:
   - System title and active sourcing pipeline indicator.
   - Shortcut trigger for updating the candidate resume.
   - User profile badge with session management.
3. **KPI Metrics Grid**:
   - Real-time counters for **Scraped Jobs**, **Qualified Openings**, **Applied Submissions**, and **Pipeline Executions**.
4. **Interactive Filter Toolbar**:
   - Live debounced search by role or company name.
   - Platform filtering (LinkedIn Startups, Remotive Startups, Himalayas Startups).
   - Match score threshold slider.
   - Status pill toggles (`ALL`, `SAVED`, `APPLIED`, `REJECTED`).
   - Primary **Run Pipeline** button with live status feedback.
5. **Two-Column Core Workstation**:
   - **Left Column**: Live Streaming Agent Console with monospace output, colored status tags (`INFO`, `JOB FOUND`, `SUCCESS`, `ERROR`), and real-time SSE event streaming.
   - **Right Column**: Responsive Job Cards Grid featuring Circular SVG Score Ring Gauges, extracted skill tags, match reasoning summaries, and application actions.
6. **Modals & Drawers**:
   - **Job Details Drawer**: Detailed view containing the full job description, AI fit evaluation, and direct application links.
   - **Master Resume Modal**: Drag-and-drop PDF upload connected directly to `/upload-resume`.

---

## Quick Start Guide

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher with npm
- Groq API Key (available at [console.groq.com](https://console.groq.com))
- Gmail OAuth 2.0 credentials (`credentials.json` and `token.json`)
- Twilio Account (for WhatsApp notifications — optional)

### 1. Clone & Set Up Python Environment

```bash
git clone https://github.com/Manthanraut13/Autonomous-Internship-Agent.git
cd Autonomous-Internship-Agent

# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```
Edit `.env` and provide your credentials (see [Environment Configuration](#environment-configuration)).

### 3. Build Frontend & Start Server

```bash
# Build production frontend assets
cd frontend
npm install
npm run build
cd ..

# Start FastAPI server
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser and sign in with your configured admin credentials.

### 4. Execute Pipeline from CLI

```bash
python run_pipeline.py --target 25 --threshold 70
```

---

## Environment Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API Key for LLM scoring |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Model name for resume-JD matching |
| `DATABASE_URL` | No | SQLite fallback | PostgreSQL database connection URI |
| `ADMIN_USERNAME` | Yes | `admin` | Username for dashboard login |
| `ADMIN_PASSWORD` | Yes | — | Password for dashboard login |
| `AUTH_SECRET_KEY` | Yes | — | 32-character key for signing HMAC session tokens |
| `RECIPIENT_EMAIL` | Yes | — | Target email address for daily CSV reports |
| `SENDER_EMAIL` | No | `noreply@internshipagent.com` | Verified sender email address |
| `TWILIO_ACCOUNT_SID` | No | — | Twilio Account SID for WhatsApp alerts |
| `TWILIO_AUTH_TOKEN` | No | — | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | No | `+14155238886` | Twilio WhatsApp Sandbox Number |
| `USER_WHATSAPP_NUMBER` | No | — | Recipient WhatsApp number (E.164 format) |
| `MATCH_SCORE_THRESHOLD` | No | `70` | Minimum score threshold for qualified jobs |

---

## Production Deployment

The platform is designed to deploy seamlessly on free-tier infrastructure using **Render** and **GitHub Actions**.

| Component | Provider | Configuration |
|---|---|---|
| **Web Service (API + UI)** | Render | Python 3 Web Service running `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Shared Database** | Render | Managed PostgreSQL database for cross-run persistence |
| **Scheduled Worker** | GitHub Actions | Cron workflow running at `30 3 * * *` (9 AM IST) and `30 15 * * *` (9 PM IST) |
| **Email Delivery** | Gmail API | OAuth 2.0 token-based dispatch with CSV report attachment |
| **WhatsApp Alerts** | Twilio | REST API sandbox integration for summary notifications |

For complete step-by-step instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## API Reference

All protected routes require a Bearer token in the `Authorization` header (`Bearer <token>`) or as a `?token=` query parameter for SSE endpoints.

| Route | Method | Access | Description |
|---|---|---|---|
| `/api/auth/login` | `POST` | Public | Authenticates credentials and returns a 7-day session token |
| `/api/auth/me` | `GET` | Protected | Verifies session token validity and returns user identity |
| `/api/dashboard/stats` | `GET` | Protected | Returns aggregate metrics (scraped, qualified, applied, averages) |
| `/api/dashboard/jobs` | `GET` | Protected | Retrieves job listings with support for filtering, search, and sorting |
| `/api/dashboard/jobs/{id}/action` | `POST` | Protected | Updates job application status (`mark_applied`, `reject`, `mark_saved`, `delete`) |
| `/api/dashboard/settings` | `GET` | Protected | Returns active agent configuration and cron schedules |
| `/api/pipeline/stream` | `GET` | Protected | Server-Sent Events stream providing real-time pipeline execution telemetry |
| `/upload-resume` | `POST` | Protected | Uploads and processes a new candidate PDF resume |
| `/api/upload-resume` | `POST` | Protected | API alias for candidate PDF resume upload |

---

## License & Author

Distributed under the **MIT License**. See `LICENSE` for details.

### Author
**Manthan Raut**  
- GitHub: [@Manthanraut13](https://github.com/Manthanraut13)  
- Email: [manthanr141@gmail.com](mailto:manthanr141@gmail.com)  
- LinkedIn: [linkedin.com/in/manthan-raut](https://linkedin.com/in/manthan-raut)
