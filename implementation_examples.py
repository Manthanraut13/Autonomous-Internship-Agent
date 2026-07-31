# Key Implementation Examples

# ============ 1. RESUME-JD MATCHING (LangChain Agent) ============

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import json

class MatchResult(BaseModel):
    score: int = Field(description="Match score 0-100")
    reasoning: str = Field(description="Why this score")
    key_matches: list[str] = Field(description="Matching skills/experience")
    gaps: list[str] = Field(description="Missing skills/experience")

def create_matcher_agent():
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    parser = JsonOutputParser(pydantic_object=MatchResult)
    
    prompt = ChatPromptTemplate.from_template("""You are a resume-job matching expert.
    
Resume:
{resume}

Job Description:
{job_description}

Analyze and provide match score 0-100. Consider:
- Skills overlap
- Experience relevance
- Educational fit
- Project alignment

{format_instructions}""")
    
    chain = prompt | llm | parser
    return chain

# Usage:
matcher = create_matcher_agent()
result = matcher.invoke({
    "resume": "[user resume text]",
    "job_description": "[job description]",
    "format_instructions": MatchResult.schema()
})

print(f"Score: {result['score']}")
print(f"Key matches: {result['key_matches']}")

# ============ 2. WHATSAPP APPROVAL HANDLER (Twilio) ============

from twilio.rest import Client
from fastapi import FastAPI, Request
from pydantic import BaseModel
import os

app = FastAPI()

class WhatsAppMessage(BaseModel):
    job_id: str
    title: str
    company: str
    match_score: float

def send_whatsapp_message(phone: str, message: WhatsAppMessage):
    """Send WhatsApp message with approval options."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
    
    client = Client(account_sid, auth_token)
    
    body = f"""🎯 New Internship Match!

Title: {message.title}
Company: {message.company}
Match Score: {message.match_score}%

Reply with:
✅ = Apply
❌ = Skip"""
    
    msg = client.messages.create(
        from_=f"whatsapp:{twilio_phone}",
        body=body,
        to=f"whatsapp:{phone}"
    )
    
    # Store message SID for tracking
    return msg.sid

# Webhook to receive WhatsApp responses
@app.post("/webhook/whatsapp")
async def handle_whatsapp_response(request: Request):
    """Handle user approval/rejection via WhatsApp."""
    form_data = await request.form()
    
    user_message = form_data.get("Body", "").strip().upper()
    from_number = form_data.get("From", "").replace("whatsapp:", "")
    message_sid = form_data.get("MessageSid")
    
    # Parse response
    approval = None
    if user_message in ["✅", "YES", "APPLY", "APPROVE"]:
        approval = True
    elif user_message in ["❌", "NO", "SKIP", "REJECT"]:
        approval = False
    else:
        return {"status": "invalid"}
    
    # Store in DB
    from db.models import WhatsAppResponse
    from db.database import SessionLocal
    
    db = SessionLocal()
    response = WhatsAppResponse(
        job_id=extract_job_id(message_sid),  # Map SID to job_id
        user_approval=approval,
        responded_at=datetime.now()
    )
    db.add(response)
    db.commit()
    
    return {"status": "success", "approval": approval}

# ============ 3. AUTO-APPLY (Selenium + Playwright) ============

from playwright.async_api import async_playwright
import asyncio

async def auto_apply_to_job(job_link: str, resume_pdf_path: str, github: str, linkedin: str):
    """Auto-fill and submit job application."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(job_link, wait_until="networkidle", timeout=30000)
            
            # Detect platform and fill accordingly
            if "indeed.com" in job_link:
                await apply_indeed(page, resume_pdf_path, github, linkedin)
            elif "linkedin.com" in job_link:
                await apply_linkedin(page, resume_pdf_path, github, linkedin)
            else:
                # Generic form filling
                await apply_generic(page, resume_pdf_path, github, linkedin)
            
            return {"status": "applied", "platform": "auto"}
            
        except Exception as e:
            # Fallback: Generate email application
            print(f"Auto-apply failed: {e}. Sending manual email link.")
            return {"status": "email_sent", "link": job_link}
        finally:
            await browser.close()

async def apply_indeed(page, resume_pdf_path: str, github: str, linkedin: str):
    """Apply on Indeed."""
    # Wait for and click "Apply" button
    apply_button = page.locator('button:has-text("Easy Apply"), button:has-text("Apply")')
    await apply_button.click()
    await page.wait_for_timeout(1000)
    
    # Fill email if needed
    email_input = page.locator('input[type="email"]')
    if await email_input.is_visible():
        await email_input.fill("user@example.com")
    
    # Upload resume
    file_input = page.locator('input[type="file"]')
    if await file_input.is_visible():
        await file_input.set_input_files(resume_pdf_path)
    
    # Fill cover letter
    textarea = page.locator('textarea')
    if await textarea.is_visible():
        cover_letter = f"Check my portfolio: {linkedin} | GitHub: {github}"
        await textarea.fill(cover_letter)
    
    # Submit
    submit_button = page.locator('button:has-text("Submit"), button:has-text("Send")')
    await submit_button.click()
    await page.wait_for_timeout(2000)

async def apply_generic(page, resume_pdf_path: str, github: str, linkedin: str):
    """Generic form filling for unknown platforms."""
    # Fill text inputs
    inputs = await page.locator('input[type="text"], input[type="email"]').all()
    
    for inp in inputs:
        placeholder = await inp.get_attribute("placeholder") or ""
        name = await inp.get_attribute("name") or ""
        
        if "email" in placeholder.lower() or "email" in name.lower():
            await inp.fill("user@example.com")
        elif "name" in placeholder.lower():
            await inp.fill("User Name")
        elif "phone" in placeholder.lower():
            await inp.fill("+1234567890")
    
    # Upload resume
    file_inputs = await page.locator('input[type="file"]').all()
    for fi in file_inputs:
        try:
            await fi.set_input_files(resume_pdf_path)
            break
        except:
            pass
    
    # Fill textarea (cover letter)
    textareas = await page.locator('textarea').all()
    if textareas:
        cover = f"Interested in this role. Portfolio: {linkedin} | GitHub: {github}"
        await textareas[0].fill(cover)
    
    # Submit form
    submit = page.locator('button[type="submit"]').first
    if await submit.is_visible():
        await submit.click()

# ============ 4. EMAIL SUMMARY ============

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content
from datetime import datetime

def send_daily_summary(recipient: str, applications: list):
    """Send email summary of day's applications."""
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    
    # Build HTML
    html_body = f"""
    <h2>📊 Internship Agent Report - {datetime.now().strftime('%B %d, %Y')}</h2>
    <p><strong>Applied Today: {len(applications)}</strong></p>
    <table border="1" cellpadding="10">
        <tr>
            <th>Company</th>
            <th>Position</th>
            <th>Match Score</th>
            <th>Status</th>
        </tr>
    """
    
    for app in applications:
        html_body += f"""
        <tr>
            <td>{app['company']}</td>
            <td>{app['title']}</td>
            <td>{app['match_score']}%</td>
            <td>{app['status']}</td>
        </tr>
        """
    
    html_body += """
    </table>
    <p><a href="https://your-dashboard.com">View all applications →</a></p>
    """
    
    message = Mail(
        from_email=os.getenv("SENDER_EMAIL"),
        to_emails=recipient,
        subject=f"Daily Internship Agent Report - {datetime.now().strftime('%Y-%m-%d')}",
        html_content=Content("text/html", html_body)
    )
    
    response = sg.send(message)
    return response.status_code == 202

# ============ 5. JOB SCRAPER ============

import requests
from bs4 import BeautifulSoup

def scrape_indeed_internships(search_query: str = "internship", pages: int = 1):
    """Scrape internships from Indeed."""
    jobs = []
    base_url = "https://www.indeed.com/jobs"
    
    for page in range(pages):
        params = {
            "q": search_query,
            "start": page * 10,
            "radius": 25,
            "jt": "internship"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        job_cards = soup.find_all("div", class_="job_seen_beacon")
        
        for card in job_cards:
            try:
                title = card.find("h2", class_="jobTitle").text.strip()
                company = card.find("span", class_="companyName").text.strip()
                link = card.find("a")["href"]
                description = card.find("div", class_="job-snippet").text.strip()
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "link": f"https://www.indeed.com{link}",
                    "description": description,
                    "source": "indeed"
                })
            except:
                continue
    
    return jobs

# ============ 6. SCHEDULER ============

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

def schedule_daily_agent():
    """Schedule agent to run daily at 9 AM."""
    scheduler = BackgroundScheduler()
    
    def run_agent():
        from agents.workflow import agent_workflow
        initial_state = {...}  # Initialize state
        result = agent_workflow.invoke(initial_state)
        print(f"Agent executed: {len(result['applications_today'])} apps sent")
    
    scheduler.add_job(
        run_agent,
        trigger=CronTrigger(hour=9, minute=0),  # 9 AM daily
        id="daily_internship_agent"
    )
    
    scheduler.start()
    return scheduler

# ============ 7. DATABASE MODELS ============

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(255), unique=True)
    title = Column(String(255))
    company = Column(String(255))
    description = Column(Text)
    link = Column(String(500))
    source = Column(String(50))  # indeed, linkedin
    scraped_at = Column(DateTime, default=datetime.utcnow)
    match_score = Column(Float)
    status = Column(String(50))  # pending, applied, rejected
    
    applications = relationship("Application", back_populates="job")
    responses = relationship("WhatsAppResponse", back_populates="job")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    applied_at = Column(DateTime, default=datetime.utcnow)
    application_id = Column(String(255))
    status = Column(String(50))  # submitted, pending
    application_link = Column(String(500))
    
    job = relationship("Job", back_populates="applications")

class WhatsAppResponse(Base):
    __tablename__ = "whatsapp_responses"
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    user_approval = Column(Boolean)
    responded_at = Column(DateTime, default=datetime.utcnow)
    message_sid = Column(String(255))
    
    job = relationship("Job", back_populates="responses")
