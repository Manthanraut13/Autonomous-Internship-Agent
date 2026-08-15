# Autonomous Internship Agent — Render & Free Cloud Deployment Guide

This guide explains how to deploy the **Autonomous Internship Agent** (FastAPI Backend, React Dashboard, and 9:00 AM & 9:00 PM automated scraping & email pipeline) on the cloud using **Render** and **100% Free Alternatives**.

---

## ⚠️ Important Note About Render Free Tier

1. **Web Services on Free Plan**: Render allows free Web Services, but they sleep after 15 minutes of inactivity.
2. **Cron Jobs on Render**: Render's native "Cron Jobs" feature is **paid** (starts at $1/month + compute).
3. **Best 100% Free Architecture**:
   - **Dashboard & API**: Deploy as a single free **Render Web Service** (serves both FastAPI + React).
   - **Automated 9 AM & 9 PM Cron Trigger**: Use **GitHub Actions** (2,000 free minutes/month) to run the pipeline twice a day with zero cost and zero sleeping issues.

---

## Strategy 1: Deploy on Render (Web Service + Built-in Scheduler)

You can deploy the entire app (FastAPI + React Dashboard + APScheduler) in a single free Render Web Service.

### 1. Push Code to GitHub
Ensure your repository is up to date:
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Create Web Service on Render
1. Go to [dashboard.render.com](https://dashboard.render.com/) and click **New +** → **Web Service**.
2. Connect your GitHub repository (`Autonomous-Internship-Agent`).
3. Configure the settings:
   - **Name**: `internship-agent`
   - **Region**: Choose the closest region (e.g., Singapore or Frankfurt)
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

### 3. Add Environment Variables on Render
In the **Environment** tab of your Render Web Service, add the following key-value pairs from your `.env`:

| Key | Example Value | Description |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Your Groq LLM API Key |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Model for JD evaluation |
| `RECIPIENT_EMAIL` | `manthanr141@gmail.com` | Email address to receive CSV reports |
| `DATABASE_URL` | `sqlite:///data/agent.db` | Or a Render Free PostgreSQL internal URL |
| `TWILIO_ACCOUNT_SID` | `AC...` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | `your_twilio_token` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | `+14155238886` | Twilio WhatsApp Sandbox Number |
| `USER_WHATSAPP_NUMBER` | `+919529883808` | Your WhatsApp Number (E.164) |
| `MATCH_SCORE_THRESHOLD` | `70` | Minimum match score (0-100) |
| `PYTHON_VERSION` | `3.11.9` | Recommended Python version |

### 4. Upload Gmail OAuth / Token Files (Secret Files on Render)
If using Gmail OAuth (`credentials.json` and `token.json`):
1. In Render, go to **Environment** → **Secret Files**.
2. Add a secret file named `credentials.json` and paste your Google Cloud OAuth credentials JSON.
3. Add a secret file named `token.json` and paste your generated access/refresh token JSON.
*(Alternatively, you can set `GMAIL_USER` and `GMAIL_APP_PASSWORD` for SMTP fallback).*

### 5. Keeping Free Render Alive for 9 AM & 9 PM
Because Render free instances spin down after 15 minutes of inactivity, use **[cron-job.org](https://cron-job.org)** or **[UptimeRobot](https://uptimerobot.com)** (both 100% free) to ping:
- `https://your-app-name.onrender.com/api/dashboard/stats` every 10 minutes, OR
- Ping at `09:00 AM` and `09:00 PM` IST to wake up the server right when the pipeline runs.

---

## Strategy 2: 100% Free Automated Cron with GitHub Actions (Recommended)

To guarantee the pipeline **always executes at 9:00 AM and 9:00 PM IST** without relying on a server being awake or paying for Render Cron:

### 1. Create Workflow File
Create `.github/workflows/cron_pipeline.yml`:

```yaml
name: 9 AM & 9 PM Daily Internship Pipeline

on:
  schedule:
    # 9:00 AM IST is 03:30 UTC
    - cron: '30 3 * * *'
    # 9:00 PM IST is 15:30 UTC
    - cron: '30 15 * * *'
  workflow_dispatch: # Allows manual trigger from GitHub UI anytime

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Create Token and Credentials Files
        env:
          GMAIL_CREDENTIALS: ${{ secrets.GMAIL_CREDENTIALS }}
          GMAIL_TOKEN: ${{ secrets.GMAIL_TOKEN }}
        run: |
          if [ -n "$GMAIL_CREDENTIALS" ]; then
            echo "$GMAIL_CREDENTIALS" > credentials.json
          fi
          if [ -n "$GMAIL_TOKEN" ]; then
            echo "$GMAIL_TOKEN" > token.json
          fi

      - name: Run 25-Target Internship Pipeline
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          GROQ_MODEL: "llama-3.1-8b-instant"
          DATABASE_URL: "sqlite:///data/agent.db"
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
          TWILIO_ACCOUNT_SID: ${{ secrets.TWILIO_ACCOUNT_SID }}
          TWILIO_AUTH_TOKEN: ${{ secrets.TWILIO_AUTH_TOKEN }}
          TWILIO_PHONE_NUMBER: ${{ secrets.TWILIO_PHONE_NUMBER }}
          USER_WHATSAPP_NUMBER: ${{ secrets.USER_WHATSAPP_NUMBER }}
          MATCH_SCORE_THRESHOLD: 70
        run: |
          python run_pipeline.py --target 25 --threshold 70
```

### 2. Add Secrets to GitHub
In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
- `GROQ_API_KEY`
- `RECIPIENT_EMAIL`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `USER_WHATSAPP_NUMBER`
- `GMAIL_CREDENTIALS` (contents of `credentials.json`)
- `GMAIL_TOKEN` (contents of `token.json`)

---

## Strategy 3: Render Paid Cron Job (If Upgraded)

If you have a paid Render plan or choose to add a Render Cron Job:
1. Go to **Render Dashboard** → **New +** → **Cron Job**.
2. Connect your repo.
3. **Schedule**: `30 3,15 * * *` (Runs twice daily at 09:00 AM and 09:00 PM IST / 03:30 and 15:30 UTC).
4. **Command**: `python run_pipeline.py --target 25 --threshold 70`.
5. Add the same Environment Variables as above.

---

## Summary Recommendation

| Requirement | Best Solution | Cost |
|---|---|---|
| **View Web Dashboard & CRM** | Render Web Service (Free Tier) | **$0 / month** |
| **9:00 AM & 9:00 PM Automated Runs** | GitHub Actions Cron Workflow | **$0 / month** (2,000 free mins) |
| **Email Delivery** | Gmail OAuth 2.0 API | **$0 / month** |
| **LLM Match Scoring** | Groq API Free Tier | **$0 / month** |
