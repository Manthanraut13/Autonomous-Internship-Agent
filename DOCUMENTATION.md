# 📖 Autonomous Internship Agent — Complete Technical Documentation

> **Comprehensive Architectural, Engineering, and Operational Reference Manual**  
> *Version 2.0.0 | Production Ready*

---

## 📑 Table of Contents

1. [Executive Summary & System Purpose](#1-executive-summary--system-purpose)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Repository Directory & File Organization](#3-repository-directory--file-organization)
4. [Core Backend Engine (`FastAPI` & Execution Runners)](#4-core-backend-engine-fastapi--execution-runners)
   - [4.1 `main.py` — API Server & SSE Streamer](#41-mainpy--api-server--sse-streamer)
   - [4.2 `run_pipeline.py` — Autonomous CLI Engine](#42-run_pipelinepy--autonomous-cli-engine)
   - [4.3 `run_scheduler.py` — Dual-Engine Local Scheduler](#43-run_schedulerpy--dual-engine-local-scheduler)
5. [Configuration & Prompt Engineering](#5-configuration--prompt-engineering)
   - [5.1 `config/settings.py` — Pydantic Settings & Validation](#51-configsettingspy--pydantic-settings--validation)
   - [5.2 `config/prompts.py` — AI Evaluation Rubric & System Prompts](#52-configpromptspy--ai-evaluation-rubric--system-prompts)
6. [Database & Persistence Layer](#6-database--persistence-layer)
   - [6.1 `db/database.py` — Multi-Dialect Session Manager](#61-dbdatabasepy--multi-dialect-session-manager)
   - [6.2 `db/models.py` — ORM Data Models & Enums](#62-dbmodelspy--orm-data-models--enums)
   - [6.3 Cross-Run Deduplication Mechanism](#63-cross-run-deduplication-mechanism)
7. [Job Ingestion & Scraper Architecture](#7-job-ingestion--scraper-architecture)
   - [7.1 Priority Order & Top 3 Platform Hierarchy](#71-priority-order--top-3-platform-hierarchy)
   - [7.2 `tools/job_api.py` — Multi-Source Scraping Engine](#72-toolsjob_apipy--multi-source-scraping-engine)
   - [7.3 `tools/apollo_scraper.py` — Fallback Ingestion Engine](#73-toolsapollo_scraperpy--fallback-ingestion-engine)
8. [Resume Intelligence & LLM Scoring](#8-resume-intelligence--llm-scoring)
   - [8.1 `tools/resume_parser.py` — Multi-Engine PDF Extraction](#81-toolsresume_parserpy--multi-engine-pdf-extraction)
   - [8.2 `tools/jd_matcher.py` — Groq LLM Evaluation & Fallback Cascade](#82-toolsjd_matcherpy--groq-llm-evaluation--fallback-cascade)
9. [Dispatch & Notification Subsystems](#9-dispatch--notification-subsystems)
   - [9.1 `tools/csv_exporter.py` — Structured Spreadsheet Generation](#91-toolscsv_exporterpy--structured-spreadsheet-generation)
   - [9.2 `tools/email_sender.py` — Gmail OAuth 2.0 & SendGrid Dispatch](#92-toolsemail_senderpy--gmail-oauth-20--sendgrid-dispatch)
   - [9.3 `tools/whatsapp_handler.py` — Twilio WhatsApp Alerts](#93-toolswhatsapp_handlerpy--twilio-whatsapp-alerts)
10. [Frontend Architecture & UI Design System](#10-frontend-architecture--ui-design-system)
    - [10.1 Tech Stack & Build Pipeline](#101-tech-stack--build-pipeline)
    - [10.2 Warm & Cold Color Philosophy](#102-warm--cold-color-philosophy)
    - [10.3 Component Breakdown & State Management](#103-component-breakdown--state-management)
11. [Security, Performance & Token Efficiency](#11-security-performance--token-efficiency)
12. [Cloud Deployment & CI/CD Operations](#12-cloud-deployment--cicd-operations)
    - [12.1 GitHub Actions Cron Workflow (`cron_pipeline.yml`)](#121-github-actions-cron-workflow-cron_pipelineyml)
    - [12.2 Render Web Service & Shared Cloud PostgreSQL](#122-render-web-service--shared-cloud-postgresql)
13. [Developer Setup, Testing & Verification Guide](#13-developer-setup-testing--verification-guide)
14. [Complete REST & SSE API Reference](#14-complete-rest--sse-api-reference)

---

## 1. Executive Summary & System Purpose

The **Autonomous Internship Agent** is a full-stack, enterprise-grade AI automation system designed to eliminate the manual friction of landing high-growth AI internships. 

### Key Capabilities
- **Startup-First Scraping**: Automatically identifies and scrapes fresh job openings from high-growth tech startups.
- **Strictly AI-Only Roles**: Dynamically extracts candidates' skills and locks queries exclusively to AI, GenAI, LLM, Agentic AI, and Machine Learning internships.
- **Internship-First Scoring Rubric**: Automatically filters out senior roles and evaluates candidates using a 4-dimension scoring rubric powered by high-speed Groq LLMs (`openai/gpt-oss-120b`).
- **Immediate Early-Stop Pipeline**: Traverses sources in strict priority order and halts execution instantly the moment the target quota (default: 25 matches) is satisfied.
- **Automated Dispatch**: Delivers structured CSV reports via Gmail OAuth 2.0 and WhatsApp summary alerts via Twilio.
- **Zero-Maintenance Scheduling**: Fully automated background runs twice daily (9:00 AM & 9:00 PM IST) using GitHub Actions.
- **Real-Time Web CRM**: Modern dark-mode React dashboard with live SSE log streaming, applicant tracking, search filters, and resume management.

---

## 2. End-to-End System Architecture

```
                                  ┌──────────────────────────────────────────────┐
                                  │            SCHEDULED TRIGGER / USER          │
                                  │   GitHub Actions (9 AM & 9 PM IST) OR Web UI │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │             1. RESUME EXTRACTION             │
                                  │  • tools/resume_parser.py (PDF Engine)       │
                                  │  • Extracts text & generates AI query terms   │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │     2. PRIORITY-ORDERED SCRAPER CASCADE      │
                                  │  • Priority 1: LinkedIn Startup AI Interns   │
                                  │  • Priority 2: Remotive Startup AI Openings  │
                                  │  • Priority 3: Himalayas Remote Tech Openings │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │      3. DEDUPLICATION & PRE-FILTERING        │
                                  │  • Strictly Remote / Online / Virtual filter │
                                  │  • Rejects 5+ YOE / Senior / Staff titles    │
                                  │  • Cross-checks DB signature (Title + Co)    │
                                  │  • Cross-checks apply_url / link hashes      │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │        4. GROQ LLM MATCHING & SCORING        │
                                  │  • Model: openai/gpt-oss-120b (Fallback list)│
                                  │  • 4-Dimension Rubric (0-100 Score)          │
                                  │  • Stop Condition: len(matches) >= target    │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │            5. PERSISTENCE & DISPATCH         │
                                  │  • Writes to PostgreSQL / SQLite Database    │
                                  │  • Generates timestamped CSV spreadsheet     │
                                  │  • Sends email with attachment (Gmail OAuth) │
                                  │  • Sends WhatsApp alert (Twilio REST API)    │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                                         ▼
                                  ┌──────────────────────────────────────────────┐
                                  │       6. INTERACTIVE WEB CRM DASHBOARD       │
                                  │  • React 18 + Vite + Warm/Cold Dark UI       │
                                  │  • Live SSE streaming terminal output        │
                                  │  • One-click application status update       │
                                  └──────────────────────────────────────────────┘
```

---

## 3. Repository Directory & File Organization

```
Autonomous-Internship-Agent/
├── .github/
│   └── workflows/
│       └── cron_pipeline.yml       # GitHub Actions dual daily cron (9 AM & 9 PM IST)
├── config/
│   ├── __init__.py                 # Package initializer
│   ├── prompts.py                  # LLM system prompts, scoring rubrics & schemas
│   └── settings.py                 # Pydantic BaseSettings environment manager
├── db/
│   ├── __init__.py                 # Package initializer
│   ├── database.py                 # SQLAlchemy engine, session maker & connection pool
│   └── models.py                   # ORM Models (Job, PipelineRun, ApplicationStatus)
├── frontend/
│   ├── public/                     # Static assets, SVG icons, favicon
│   ├── src/
│   │   ├── assets/                 # Brand assets & illustrations
│   │   ├── App.css                 # Glacial Precision Theme stylesheet (Steel Blue, Ice, Teal)
│   │   ├── App.tsx                 # Core Dashboard application (React 18 + TypeScript)
│   │   ├── index.css               # Global CSS tokens, resets & typography
│   │   └── main.tsx                # React DOM root entry point
│   ├── index.html                  # HTML5 shell (Hanken Grotesk & Material Symbols)
│   ├── package.json                # Frontend NPM scripts and dependencies
│   ├── tsconfig.json               # TypeScript compiler configuration
│   └── vite.config.ts              # Vite bundle configuration & dev proxy
├── new design/
│   ├── DESIGN.md                   # Glacial Precision UI/UX Design System Specification
│   ├── code.html                   # High-fidelity reference HTML mockup
│   └── screen.png                  # Visual design render snapshot
├── tools/
│   ├── __init__.py                 # Package initializer
│   ├── apollo_scraper.py           # Fallback Apollo API / HTML scraper
│   ├── csv_exporter.py             # CSV spreadsheet generator & file formatter
│   ├── email_sender.py             # Gmail OAuth 2.0 & SendGrid email dispatchers
│   ├── jd_matcher.py               # Groq LLM JD-Resume evaluation & multi-model fallback
│   ├── job_api.py                  # Scraper cascade (LinkedIn, Remotive, Himalayas)
│   ├── resume_parser.py            # PDF parsing & dynamic AI search query generator
│   └── whatsapp_handler.py         # Twilio WhatsApp alert formatter & sender
├── .env.example                    # Sample environment template with documentation
├── .gitignore                      # Git exclusion rules (venv, node_modules, keys, DB)
├── AGENT.md                        # Autonomous agent operational specification
├── DEPLOYMENT.md                   # Step-by-step cloud deployment manual (Render + GH)
├── DOCUMENTATION.md                # Complete technical reference manual (This file)
├── main.py                         # FastAPI web server, auth & SSE streaming endpoint
├── README.md                       # High-level overview, quickstart & feature highlights
├── requirements.txt                # Python backend dependencies
├── run_pipeline.py                 # Standalone autonomous CLI pipeline runner
└── run_scheduler.py                # Dual-mode local scheduler (APScheduler / Threading)
```

---

## 4. Core Backend Engine (`FastAPI` & Execution Runners)

### 4.1 `main.py` — API Server & SSE Streamer

`main.py` is the primary web application gateway powered by **FastAPI**. It provides both RESTful JSON endpoints and Server-Sent Events (SSE) for live pipeline telemetry.

#### Key Modules & Features:
1. **HMAC-SHA256 Token Authentication**:
   - Endpoints are protected by cryptographically signed bearer tokens.
   - Password verification uses `secrets.compare_digest` to prevent timing attacks.
   - Session tokens have a configurable TTL (default 24 hours).
2. **Server-Sent Events (`/api/pipeline/stream`)**:
   - Streams live, step-by-step progress directly to the web dashboard terminal.
   - Emits structured JSON events: `{"step": str, "message": str, "progress": int, "job": dict}`.
   - Handles client disconnection gracefully using `await request.is_disconnected()`.
3. **Static SPA Hosting**:
   - Mounts the compiled React distribution (`frontend/dist`) as static assets.
   - Implements a fallback routing handler that serves `index.html` for any client-side routes.
4. **Resume Upload Gateway (`/api/upload-resume`)**:
   - Accepts `.pdf` files via `multipart/form-data`.
   - Validates file headers and saves them securely to the root workspace.

---

### 4.2 `run_pipeline.py` — Autonomous CLI Engine

`run_pipeline.py` provides the standalone execution pipeline utilized by automated cron runners, GitHub Actions, and headless CLI invocations.

#### Execution Flags:
| Flag | Type | Default | Description |
|---|---|---|---|
| `--target` | `int` | `25` | Target count of qualified AI internship openings to discover |
| `--threshold` | `int` | `70` | Minimum match score (0–100) required to accept a job |
| `--hours` | `int` | `24` | Maximum age of job postings in hours |
| `--dry-run` | `bool` | `False` | Executes scraping and scoring without sending emails or WhatsApp alerts |

#### Execution Flow:
1. **Resume Loading**: Locates candidate resume in project directory.
2. **Query Generation**: Computes 10 targeted AI internship search queries.
3. **Priority Ingestion Loop**: Traverses scrapers sequentially (Platform 1 → 2 → 3).
4. **Live Evaluation**: Evaluates each opening immediately via Groq LLM.
5. **Immediate Early-Stop**: Halts scraping the moment `len(scored_jobs) >= target`.
6. **Persistence**: Saves new qualified records into the PostgreSQL database.
7. **Dispatch**: Generates CSV report and delivers email & WhatsApp notifications.

---

### 4.3 `run_scheduler.py` — Dual-Engine Local Scheduler

`run_scheduler.py` is a robust local daemon for machines without GitHub Actions.

- **Primary Engine**: Uses `APScheduler` (`BlockingScheduler`) with `CronTrigger(hour="9,21", minute=0, timezone="Asia/Kolkata")`.
- **Fallback Engine**: If `APScheduler` is not installed, it falls back to a multi-threaded `schedule` loop with automatic drift compensation.

---

## 5. Configuration & Prompt Engineering

### 5.1 `config/settings.py` — Pydantic Settings & Validation

`config/settings.py` uses `pydantic-settings` to parse, cast, and validate environment variables with strict type safety.

#### Validated Settings:
- `GROQ_API_KEY`: Required string for LLM inference.
- `GROQ_MODEL`: Model name (default: `openai/gpt-oss-120b`).
- `DATABASE_URL`: Automatically validated by `@field_validator` to ensure supported SQLAlchemy dialect strings (`postgresql://`, `postgresql+psycopg2://`, or `sqlite://`).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `USER_WHATSAPP_NUMBER`: Credentials for WhatsApp notifications.
- `RECIPIENT_EMAIL`, `SENDER_EMAIL`: Email delivery targets.

---

### 5.2 `config/prompts.py` — AI Evaluation Rubric & System Prompts

`config/prompts.py` defines the prompt templates used by the AI engine.

#### 4-Dimension Scoring Rubric:
1. **Technical Stack Match (0–35 pts)**:
   - Evaluates direct overlap in programming languages, frameworks, and AI libraries (Python, PyTorch, LangChain, Transformers, LLM APIs).
2. **Domain & Problem Alignment (0–30 pts)**:
   - Evaluates alignment with AI/ML domains (GenAI, Agentic AI, NLP, Computer Vision, RAG).
3. **Seniority & Internship Level (0–20 pts)**:
   - **Student / Intern / Trainee**: Award full 18–20 points.
   - **Entry-Level (0–2 YOE)**: Award 10–14 points.
   - **Senior / Lead (5+ YOE)**: Strict penalty (0 points, total score capped < 45).
4. **Demonstrated Project Evidence (0–15 pts)**:
   - Evaluates concrete projects, GitHub repositories, and practical implementations.

---

## 6. Database & Persistence Layer

### 6.1 `db/database.py` — Multi-Dialect Session Manager

`db/database.py` configures SQLAlchemy with production-ready connection pooling.

```python
# Pool Configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Proactively drops stale connections
    pool_recycle=300     # Recycles connections every 5 minutes
)
```

Provides context manager `get_db_context()` for safe atomic transactions with automatic rollback on exceptions.

---

### 6.2 `db/models.py` — ORM Data Models & Enums

`db/models.py` defines the database entities:

#### 1. `Job` Model:
| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | Primary Key (Autoincrement) |
| `title` | `String(255)` | Job title (Indexed) |
| `company` | `String(255)` | Company name (Indexed) |
| `location` | `String(255)` | Location or "Remote" |
| `description` | `Text` | Full text job description |
| `link` | `String(1024)` | Primary listing URL (Indexed) |
| `apply_url` | `String(1024)` | Direct application URL (Indexed) |
| `source` | `String(50)` | Source scraper (`linkedin`, `remotive`, `himalayas`) |
| `match_score` | `Integer` | AI evaluation score (0–100) |
| `match_reasoning` | `Text` | AI explanation summary |
| `key_matches` | `JSON` | List of matching skills/projects |
| `status` | `Enum` | `NEW`, `MATCHED`, `APPLIED`, `REJECTED`, `EXPIRED` |
| `posted_at` | `DateTime` | Publication timestamp |
| `scraped_at` | `DateTime` | Ingestion timestamp |

#### 2. `PipelineRun` Model:
Tracks execution telemetry, duration, total jobs scraped, matches found, and error logs for auditing.

---

### 6.3 Cross-Run Deduplication Mechanism

To prevent duplicate job evaluations and redundant alerts across runs, the pipeline maintains three distinct signature indexes:
1. **Normalized Main Link**: Lowercased and stripped URL.
2. **Normalized Apply URL**: Direct application link.
3. **Normalized Tuple `(title, company)`**: Matches company/title pairs even if tracking parameters differ.

---

## 7. Job Ingestion & Scraper Architecture

### 7.1 Priority Order & Top 3 Platform Hierarchy

1. 🥇 **Priority 1 — LinkedIn Startups**:
   - Directly targets high-growth startups offering AI internships on LinkedIn.
   - Appends LinkedIn search parameters `f_JT=I` (Internship) and `f_E=1` (Entry-level).
2. 🥈 **Priority 2 — Remotive Startups**:
   - Queries Remotive's live remote startup database.
   - Filters results for AI/ML/Data keywords.
3. 🥉 **Priority 3 — Himalayas Startups**:
   - Queries Himalayas' startup API for modern remote AI roles.

---

### 7.2 `tools/job_api.py` — Multi-Source Scraping Engine

`tools/job_api.py` implements non-blocking, rate-limited HTTP scrapers with realistic browser headers (`User-Agent`, `Accept-Language`, `Sec-Fetch-*`).

#### Seniority Disqualification Regex:
```python
SENIORITY_DISQUALIFIERS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bstaff\b",
    r"\bprincipal\b", r"\bhead of\b", r"\bdirector\b",
    r"\bvp\b", r"\bmanager\b", r"\b5\+\s*years?\b", r"\b7\+\s*years?\b"
]
```
If a job title contains any disqualifier without explicitly containing `intern` or `trainee`, it is discarded immediately before invoking LLM scoring.

---

## 8. Resume Intelligence & LLM Scoring

### 8.1 `tools/resume_parser.py` — Multi-Engine PDF Extraction

`tools/resume_parser.py` extracts candidate text using a resilient multi-engine strategy:
1. **Engine 1**: `fitz` (PyMuPDF) — Fast, high-fidelity vector extraction.
2. **Engine 2**: `pdfplumber` — Advanced layout-aware table and column extraction.
3. **Engine 3**: `pypdf` — Standard fallback parser.

#### Dynamic AI Query Generation:
Generates 10 specialized AI search queries tailored to the candidate's specific background:
- `AI Intern`
- `AI Automation Intern`
- `GenAI Developer Intern`
- `Agentic AI Intern`
- `LLM Engineer Intern`
- `AI Agent Developer Intern`
- `AI ML Intern`
- `Machine Learning Intern`
- `AI Automation Engineer Intern`
- `NLP AI Intern`

---

### 8.2 `tools/jd_matcher.py` — Groq LLM Evaluation & Fallback Cascade

`tools/jd_matcher.py` orchestrates the AI evaluation process.

```python
candidate_models = [
    settings.groq_model,      # Default: openai/gpt-oss-120b
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "groq/compound"
]
```
If any model endpoint is deprecated, rate-limited, or unavailable, the system automatically rolls over to the next candidate model in sequence, guaranteeing 100% evaluation uptime.

---

## 9. Dispatch & Notification Subsystems

### 9.1 `tools/csv_exporter.py` — Structured Spreadsheet Generation

`tools/csv_exporter.py` formats qualified listings into a clean CSV spreadsheet with the following columns:
- `Match Score` (Ranked highest to lowest)
- `Job Title`
- `Company`
- `Location`
- `Source`
- `Key Matching Skills`
- `Match Reasoning`
- `Direct Apply Link`

---

### 9.2 `tools/email_sender.py` — Gmail OAuth 2.0 & SendGrid Dispatch

`tools/email_sender.py` supports two enterprise email methods:
1. **Gmail OAuth 2.0 API (Primary)**:
   - Uses `google-auth` with stored refresh tokens in `token.json` or environment variables.
   - Constructs MIME multipart messages and attaches the generated CSV report.
2. **SendGrid API (Fallback)**:
   - Uses SendGrid's REST v3 mail send endpoint.

---

### 9.3 `tools/whatsapp_handler.py` — Twilio WhatsApp Alerts

`tools/whatsapp_handler.py` sends an instant WhatsApp alert via Twilio's Messaging API:

```text
🚀 Autonomous Internship Agent Alert!
Found 25 Top AI Internship Openings for you!

Top Matches:
1. Generative AI Engineer @ Sia (Score: 88/100)
2. AI Engineer @ RocketDevs (Score: 74/100)
...
📧 Detailed CSV report has been delivered to your email.
```

---

## 10. Frontend Architecture & UI Design System

### 10.1 Tech Stack & Build Pipeline

- **Framework**: React 18 with TypeScript.
- **Build Tool**: Vite 8 (Ultra-fast HMR and production bundle optimization).
- **Styling Architecture**: Vanilla CSS tokens (`frontend/src/App.css`, `frontend/src/index.css`) styled according to the **Glacial Precision** specification.
- **Typography & Icons**:
  - Primary Font: **Hanken Grotesk** (Geometric, clean corporate styling, weights 400–800).
  - Terminal & Code Font: **JetBrains Mono** (Fixed-width clarity for telemetry logs).
  - Iconography: **Material Symbols Outlined** (Google's variable icon suite).

---

### 10.2 "Glacial Precision" Design System Philosophy

The design system is built around the narrative of **"Automated Intelligence with a Human Pulse."** It establishes a clean, cold-light corporate workstation aesthetic that minimizes cognitive load while prioritizing high-density job intelligence.

#### Color Tokens:
| Token Name | Hex Code | Purpose |
|---|---|---|
| `background` | `#eef2f7` | Cool grey-blue canvas base |
| `sidebar` | `#dce6f0` | 220px fixed vertical navigation anchor |
| `surface-ice` | `#f4f7fb` | 64px fixed header & sub-surface containers |
| `surface-lowest` | `#ffffff` | Elevated data cards, modals & active pills |
| `border-muted` | `#d4dde8` | Crisp 1px structural dividing lines |
| `primary` | `#136299` | Steel Blue primary accent & brand interactive states |
| `primary-container`| `#5b9bd5` | Active filters & primary KPI border highlight |
| `secondary` | `#984623` | Terracotta accent for human actions (Applied status) |
| `secondary-container`| `#fe956c` | Warm highlights & application indicators |
| `tertiary` | `#006b5c` | Seafoam Teal for verified high match scores (80+) & active pulses |
| `tertiary-container`| `#39a794` | Terminal headers & verified match highlights |
| `score-mid` | `#e8a94a` | Amber warning accent & pipeline counter indicator |
| `error` | `#ba1a1a` | Rose-red error alerts & rejection badges |

---

### 10.3 Component Breakdown & Navigation Architecture

`frontend/src/App.tsx` organizes the interface into dedicated functional modules:

1. **Fixed Sidebar Navigation (220px)**:
   - **Branding**: `account_tree` icon with `"AGENT CORE"` header.
   - **Navigation Tabs**:
     - 📊 **Dashboard** (`activeTab === 'dashboard'`)
     - 💼 **Jobs** (`activeTab === 'jobs'`)
     - ⚡ **Pipeline** (`activeTab === 'pipeline'`)
     - 📄 **Resume** (`activeTab === 'resume'`)
     - ⚙️ **Settings** (`activeTab === 'settings'`)
   - **Active Indicator**: White pill container with a 4px Steel Blue left border (`border-l-4 border-[#136299]`).
   - **Agent Status Indicator**: Bottom badge featuring a live CSS pulsating emerald dot (`.pulse-dot`) indicating active monitoring.

2. **Top System Header (64px)**:
   - Dynamic view title and system tagline (*"Automated Intelligence with Human Pulse"*).
   - Live **"Sourcing Pipeline"** badge with real-time status dot.
   - Master Resume quick upload shortcut button.
   - User profile avatar and logout session button.

3. **KPI Metrics Grid (4 Tonal Cards)**:
   - 🔍 **Scraped**: `#5b9bd5` left border, search icon, total scraped jobs, `+12% today`.
   - ✅ **Qualified**: `#39a794` left border, check_circle icon, count of jobs with Score ≥ 70.
   - 📤 **Applied**: `#984623` left border, send icon, count of submitted job applications.
   - 🔄 **Pipeline Runs**: `#e8a94a` left border, autorenew icon, dual daily cron execution count.

4. **Filter Toolbar**:
   - Full-text search with live debounce across job titles and companies.
   - Platform select dropdown (`All Platforms`, `LinkedIn Startups`, `Remotive Startups`, `Himalayas Startups`).
   - Interactive match score slider (`Score > [threshold]`).
   - Status pill toggles (`ALL`, `SAVED`, `APPLIED`, `REJECTED`).
   - Primary **"Run Pipeline"** CTA button with animated loading spinner.

5. **Two-Column Workstation Layout**:
   - **Left Column (Agent Console — 33% width)**:
     - Dark `#1e2b3a` container with macOS-style window controls (red, yellow, green dots).
     - `#151f2a` terminal header with `terminal` icon and clear button.
     - Live SSE stream with auto-scroll and color-coded status badges (`INFO`, `JOB FOUND`, `SUCCESS`, `ERROR`, `MATCH`).
   - **Right Column (Job Cards Grid — 67% width)**:
     - Elevated `#ffffff` cards with 1px border `#d4dde8` and hover transition to `#5b9bd5`.
     - **Circular SVG Score Ring Gauge** with colored stroke (`#006b5c` for 80+, `#5b9bd5` for 70-79, `#e8a94a` for 50-69, `#d66b6b` for <50).
     - Source platform chip and extracted skill badges (`Python`, `LangChain`, `LLMs`, `PyTorch`, `FastAPI`).
     - AI Match reasoning snippet with 2-line clamp.
     - Action buttons: "Apply Now" (opens direct URL), "Mark as Applied" (check icon), "Reject" (close icon), and "View Details" (eye icon).

6. **Interactive Modals & Drawers**:
   - **Job Details Modal**: Expandable drawer displaying full job description, 4-dimension score breakdown, key matching points, and application links.
   - **Master Resume Modal**: Drag-and-drop PDF upload zone directly communicating with `/upload-resume`.

---

## 11. Security, Performance & Token Efficiency

1. **HMAC-SHA256 Signed Tokens**: Prevents session hijacking and unauthorized API access.
2. **Constant-Time String Comparison**: Mitigates timing attacks on authentication endpoints.
3. **Early-Stop Token Optimization**: Stops LLM evaluation immediately once 25 qualified openings are found, saving up to **80% of LLM token quota**.
4. **Database Connection Pooling**: Maintains active connection pools with pre-ping validation to eliminate connection timeouts.

---

## 12. Cloud Deployment & CI/CD Operations

### 12.1 GitHub Actions Cron Workflow (`cron_pipeline.yml`)

The agent runs completely free on GitHub Actions twice daily:

```yaml
name: Scheduled AI Internship Agent Pipeline

on:
  schedule:
    # 9:00 AM IST (03:30 UTC) & 9:00 PM IST (15:30 UTC)
    - cron: '30 3 * * *'
    - cron: '30 15 * * *'
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Run Priority Pipeline
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          GROQ_MODEL: ${{ secrets.GROQ_MODEL }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          TWILIO_ACCOUNT_SID: ${{ secrets.TWILIO_ACCOUNT_SID }}
          TWILIO_AUTH_TOKEN: ${{ secrets.TWILIO_AUTH_TOKEN }}
          TWILIO_PHONE_NUMBER: ${{ secrets.TWILIO_PHONE_NUMBER }}
          USER_WHATSAPP_NUMBER: ${{ secrets.USER_WHATSAPP_NUMBER }}
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
        run: python run_pipeline.py --target 25 --threshold 70
```

---

### 12.2 Render Web Service & Shared Cloud PostgreSQL

- **Render Web Service**: Hosts FastAPI + React frontend with automatic deploy on `git push origin main`.
- **Render PostgreSQL**: Shared database accessible by both the Render Web Service and GitHub Actions background workers.

---

## 13. Developer Setup, Testing & Verification Guide

### Local Installation:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Manthanraut13/Autonomous-Internship-Agent.git
   cd Autonomous-Internship-Agent
   ```

2. **Set up Python Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env and enter your GROQ_API_KEY, TWILIO credentials, and email settings.
   ```

4. **Build Frontend**:
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

5. **Start Web Server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   Open `http://localhost:8000` in your browser.

6. **Run CLI Pipeline**:
   ```bash
   python run_pipeline.py --target 25 --threshold 70
   ```

---

## 14. Complete REST & SSE API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/auth/login` | `POST` | Public | Authenticates admin credentials and returns bearer token |
| `/api/auth/verify` | `GET` | Bearer | Verifies active session token validity |
| `/api/jobs` | `GET` | Bearer | Fetches list of all scraped jobs with search & status filters |
| `/api/jobs/{id}/status` | `PATCH` | Bearer | Updates job application status (`APPLIED`, `REJECTED`, etc.) |
| `/api/stats` | `GET` | Bearer | Returns KPI statistics (total scraped, matched, applied) |
| `/api/run-pipeline` | `POST` | Bearer | Triggers background pipeline execution |
| `/api/pipeline/stream` | `GET` | Bearer | SSE stream emitting live pipeline execution events |
| `/api/upload-resume` | `POST` | Bearer | Uploads candidate resume PDF |
| `/api/health` | `GET` | Public | System health check and database connectivity probe |

---

*Autonomous Internship Agent — Architected for Performance, Accuracy, and Reliability.*
