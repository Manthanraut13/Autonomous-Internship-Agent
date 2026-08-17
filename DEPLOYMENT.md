# Complete Deployment Guide: Render Web Service + Shared PostgreSQL + GitHub Actions

This guide provides the complete step-by-step instructions to deploy the **Autonomous Internship Agent**:
- **Render Web Service (Free)**: Hosts your interactive Web CRM Dashboard with secure Admin login.
- **Render PostgreSQL (Free)**: A shared cloud database that stores all scraped jobs, application statuses, and run logs.
- **GitHub Actions (Free)**: The automated background worker that wakes up at **9:00 AM & 9:00 PM IST**, scrapes 25 unique AI listings, scores them with Groq, delivers the CSV report to your email, sends a WhatsApp alert, and saves everything into the shared PostgreSQL database!

---

## 🏗️ Architecture Overview

```
                          ┌────────────────────────────────────────┐
                          │   1. GitHub Actions (9 AM & 9 PM)      │
                          │   • Scrapes 25 fresh AI listings       │
                          │   • Scores with Groq LLM               │
                          │   • Delivers CSV Email via Gmail API   │
                          │   • Sends WhatsApp alert via Twilio    │
                          └──────────────────┬─────────────────────┘
                                             │ Writes 25 new jobs
                                             ▼
                          ┌────────────────────────────────────────┐
                          │   2. Shared Render PostgreSQL Database │
                          │   • Stores all job listings & CRM state│
                          │   • Enforces cross-run deduplication   │
                          └──────────────────▲─────────────────────┘
                                             │ Reads & Updates
                                             │ (Applied / Rejected)
                          ┌──────────────────┴─────────────────────┐
                          │   3. Render Web Service (Dashboard UI) │
                          │   • Open in browser on Mobile / Desktop│
                          │   • Protected by Secure Admin Login    │
                          │   • Live CRM table, Actions & Terminal │
                          └────────────────────────────────────────┘
```

---

## Step 1: Create a Free PostgreSQL Database on Render

1. Go to your [Render Dashboard](https://dashboard.render.com/) and click **New +** → **PostgreSQL**.
2. Configure your database:
   - **Name**: `internship-db`
   - **Database**: `internship_agent`
   - **User**: `agent_admin`
   - **Region**: Choose the closest region to you (e.g., *Singapore* or *Frankfurt*)
   - **Plan**: `Free`
3. Click **Create Database**.
4. Once created, scroll down to **Connections**:
   - Copy the **Internal Database URL** (used for Render Web Service).
   - Copy the **External Database URL** (used for GitHub Actions).

---

## Step 2: Deploy the Web Dashboard on Render

### 1. Create Web Service
1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository (`Autonomous-Internship-Agent`).
3. Configure the build & run settings:
   - **Name**: `internship-agent`
   - **Region**: Same region as your database
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`

### 2. Add Environment Variables on Render
Go to the **Environment** tab of your Web Service and add:

| Environment Variable | Value / Example | Description |
|---|---|---|
| `DATABASE_URL` | *(Paste Internal Database URL from Step 1)* | Shared PostgreSQL Connection |
| `ADMIN_USERNAME` | `admin` | Username for dashboard login |
| `ADMIN_PASSWORD` | `your_secure_password` | Password for dashboard login |
| `AUTH_SECRET_KEY` | `32_char_random_string_here` | Secret key for signing session tokens |
| `GROQ_API_KEY` | `gsk_...` | Your Groq LLM API Key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq Model for JD evaluation |
| `RECIPIENT_EMAIL` | `manthanr141@gmail.com` | Email address to receive CSV reports |
| `TWILIO_ACCOUNT_SID` | `AC...` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | `your_twilio_token` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | `+14155238886` | Twilio WhatsApp Sandbox Number |
| `USER_WHATSAPP_NUMBER` | `+919529883808` | Your WhatsApp Number (E.164) |
| `MATCH_SCORE_THRESHOLD` | `70` | Minimum match score (0-100) |
| `PYTHON_VERSION` | `3.11.9` | Python runtime version |

### 3. Add Secret Files (Gmail OAuth)
1. Go to the **Environment** tab → **Secret Files**.
2. Add a Secret File named `credentials.json` and paste your Google OAuth client credentials JSON.
3. Add a Secret File named `token.json` and paste your generated access/refresh token JSON.
4. Click **Save Changes** and deploy the service.

---

## Step 3: Configure GitHub Actions Secrets

GitHub Actions runs the **9:00 AM & 9:00 PM IST** cron schedule.

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** for each of the following:

| Secret Name | Value | Purpose |
|---|---|---|
| `DATABASE_URL` | *(Paste **External Database URL** from Step 1)* | Writes 25 jobs directly to Render DB |
| `GROQ_API_KEY` | `gsk_...` | LLM JD scoring |
| `RECIPIENT_EMAIL` | `manthanr141@gmail.com` | Email delivery target |
| `TWILIO_ACCOUNT_SID` | `AC...` | WhatsApp alert |
| `TWILIO_AUTH_TOKEN` | `your_twilio_token` | WhatsApp alert |
| `TWILIO_PHONE_NUMBER` | `+14155238886` | WhatsApp sandbox number |
| `USER_WHATSAPP_NUMBER` | `+919529883808` | Your phone number |
| `GMAIL_CREDENTIALS` | *(Full contents of `credentials.json`)* | Gmail API OAuth |
| `GMAIL_TOKEN` | *(Full contents of `token.json`)* | Gmail API OAuth Token |
| `RENDER_APP_URL` | `https://internship-agent.onrender.com` *(Optional)* | Wakes up Render when cron runs |

---

## Step 4: Verification & Daily Routine

### 1. Test GitHub Actions Workflow (Manual Trigger)
1. Go to your GitHub repo → **Actions** tab.
2. Select **9 AM & 9 PM Daily Internship Pipeline** on the left.
3. Click **Run workflow** → **Run workflow**.
4. Check execution output:
   - ✅ Scrapes listings and loops until 25 unique matches are found.
   - ✅ Sends email CSV to your inbox.
   - ✅ Sends WhatsApp alert.
   - ✅ Writes 25 records to Render PostgreSQL.

### 2. Log in to Your Render Dashboard
1. Open your Render Web Service URL in your browser: `https://internship-agent.onrender.com/`
2. Enter your `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
3. In the **Openings & CRM** tab:
   - You will see the **25 listings scraped by GitHub Actions**!
   - Click **Apply** to open the direct link.
   - Click **Applied** to move it into your "Applied" tracking tab.
   - Click **Not Applied** or **Delete** to organize unwanted listings.

---

## 🔒 Security Best Practices

- **Zero Public Access**: All dashboard APIs, data queries, and live streaming routes require Bearer token authentication.
- **Credentials Ignored**: `.env`, `credentials.json`, `token.json`, and database files are listed in `.gitignore` and never pushed to GitHub.
- **Constant-Time Comparison**: Backend password verification protects against timing attacks.
