# Quick Start Checklist & Timeline

## PHASE 1: SETUP (1-2 days)

- [ ] Create project folder & git repo
- [ ] Setup Python venv & install requirements
- [ ] Configure PostgreSQL database locally
- [ ] Create `.env` file with API keys:
  - [ ] OpenAI API key
  - [ ] LangSmith API key
  - [ ] Twilio SID & token
  - [ ] SendGrid API key
  - [ ] Database connection string
- [ ] Test all API connections (run test scripts)
- [ ] Setup LangSmith project & enable tracing

## PHASE 2: CORE WORKFLOW (2-3 days)

- [ ] Create LangGraph state definition
- [ ] Build job scraper node (test with 1-2 jobs)
- [ ] Build resume matcher node (test LLM matching)
- [ ] Compile and test workflow end-to-end
- [ ] Add error handling & retry logic
- [ ] Test LangSmith traces

## PHASE 3: INTEGRATIONS (3-4 days)

**WhatsApp:**
- [ ] Create FastAPI server for webhooks
- [ ] Implement send_whatsapp_message()
- [ ] Implement webhook receiver for responses
- [ ] Test approval/rejection flow
- [ ] Add approval timeout logic (24h auto-reject)

**Auto-Apply:**
- [ ] Download Playwright browsers
- [ ] Implement Indeed form filling
- [ ] Implement generic form filling
- [ ] Test on 2-3 real job postings
- [ ] Setup fallback (email link if auto-apply fails)

**Email:**
- [ ] Implement daily summary generator
- [ ] Test SendGrid email sending
- [ ] Create HTML email template

## PHASE 4: AUTOMATION (1-2 days)

- [ ] Setup APScheduler for daily 9 AM execution
- [ ] Create database migrations
- [ ] Build resume upload endpoint
- [ ] Create basic dashboard (view applications)
- [ ] Setup error alerts (Sentry or LangSmith)

## PHASE 5: TESTING & DEPLOYMENT (2-3 days)

- [ ] Run full end-to-end test
- [ ] Test with your actual resume
- [ ] Validate WhatsApp messages & responses
- [ ] Verify email summaries
- [ ] Load test (simulate 50+ jobs)
- [ ] Deploy to server/cloud:
  - [ ] Docker containerization
  - [ ] AWS/Heroku/DigitalOcean setup
  - [ ] Environment variables configured
  - [ ] Database backup configured

---

## CRITICAL API KEYS TO OBTAIN

| Service | How to Get | Cost |
|---------|-----------|------|
| OpenAI | openai.com → API keys | $0-20/month |
| LangSmith | smith.langchain.com → Settings | Free tier OK |
| Twilio | twilio.com → Console | $0.01/msg |
| SendGrid | sendgrid.com → API keys | Free tier (100 emails/day) |
| Indeed API | developer.indeed.com | FREE (web scraping) |

---

## RECOMMENDED DEVELOPMENT ORDER

```
1. Resume Parser
   └─ Can work offline, test with sample resume

2. Job Scraper
   └─ Test with 5-10 jobs, no API calls needed

3. Matcher Node
   └─ Test with sample resume + job desc

4. WhatsApp Handler
   └─ Test message sending to personal number

5. Applicant Node
   └─ Test on 1 live job posting (careful!)

6. Summary Generator & Email
   └─ Integration test with all above

7. Scheduler
   └─ Full end-to-end daily run
```

---

## TESTING SCRIPTS

### Test Matcher
```bash
python -c "
from tools.resume_parser import parse_resume
from agents.nodes.matcher_node import calculate_match_score

resume = parse_resume('path/to/resume.pdf')
jd = 'Python developer needed...'
result = calculate_match_score(resume, jd)
print(f'Score: {result[\"score\"]}')
"
```

### Test WhatsApp
```bash
python -c "
from tools.whatsapp_handler import send_whatsapp_message
send_whatsapp_message(
    '+1234567890', 
    'Python Intern @TechCorp', 
    85
)
print('Message sent!')
"
```

### Test Auto-Apply
```bash
python -c "
import asyncio
from tools.application_filler import auto_apply_to_job

result = asyncio.run(auto_apply_to_job(
    'https://indeed.com/viewjob?jk=xyz',
    'resume.pdf',
    'github.com/user',
    'linkedin.com/in/user'
))
print(result)
"
```

### Test Full Workflow
```bash
python -c "
from agents.workflow import agent_workflow
from datetime import datetime

result = agent_workflow.invoke({
    'resume': open('resume.txt').read(),
    'portfolio_link': 'https://portfolio.com',
    'github_link': 'https://github.com/user',
    'linkedin_link': 'https://linkedin.com/in/user',
    'jobs_to_process': [],
    'applications_today': [],
    'errors': []
})

print(f'Applications: {len(result[\"applications_today\"])}')
print(f'Errors: {result[\"errors\"]}')
"
```

---

## COMMON ISSUES & FIXES

**Issue: "No module named 'langgraph'"**
→ `pip install langgraph --upgrade`

**Issue: WhatsApp messages not arriving**
→ Check Twilio phone number is configured correctly
→ Verify TWILIO_ACCOUNT_SID & AUTH_TOKEN in .env

**Issue: Indeed login required**
→ Use web scraping instead of API (BeautifulSoup works)
→ Rotate user agents & add delays between requests

**Issue: Form filling timeout**
→ Increase timeout: `page.goto(..., timeout=60000)`
→ Use slower navigation: `wait_until="networkidle"`

**Issue: LangSmith traces not showing**
→ Set `LANGCHAIN_TRACING_V2=true` in .env
→ Check `LANGCHAIN_API_KEY` is valid
→ Verify project name in `LANGCHAIN_PROJECT`

---

## PERFORMANCE TARGETS

- Job scraping: < 5 seconds per source
- Resume matching: < 2 seconds per job (LLM call)
- WhatsApp send: < 1 second per message
- Auto-apply: 30-60 seconds per job (Playwright)
- Daily run (50 jobs): ~15-20 minutes total

---

## SECURITY BEST PRACTICES

- [ ] Never commit .env file (use `.env.example`)
- [ ] Encrypt stored resume PDFs (use AES-256)
- [ ] Use separate DB credentials for production
- [ ] Rate limit WhatsApp webhook (5 req/second)
- [ ] Validate job URLs before opening (prevent XSS)
- [ ] Use API keys from environment, never hardcode
- [ ] Enable HTTPS for all endpoints
- [ ] Add input validation (SQLAlchemy validators)

---

## NEXT: BUILD TIMELINE (Realistic)

| Week | Focus | Hours |
|------|-------|-------|
| 1 | Setup + Core workflow | 20-25 |
| 2 | WhatsApp + Auto-apply | 25-30 |
| 3 | Testing + Deployment | 15-20 |

**Total: 60-75 hours (~2-3 weeks part-time)**

---

## SUCCESS METRICS

✅ Agent successfully sends 5+ job matches per day
✅ User approval rate > 50% (good matching)
✅ Auto-apply success rate > 80% (most forms filled)
✅ Zero WhatsApp delivery failures
✅ Email summaries delivered by 9:30 AM
✅ LangSmith shows avg latency < 5 seconds per job

---

## QUESTIONS TO ANSWER BEFORE BUILDING

1. Where should I store resumes? (S3, local disk, encrypted DB)
2. How many internships to scrape daily? (5, 10, 25?)
3. Auto-apply to all ≥70% matches or ask first? (WhatsApp approval)
4. What if Indeed requires login? (Use backup: internship.com, LinkedIn)
5. Should I cache job listings to avoid duplicates? (Yes, deduplicate by link)
6. How long to keep WhatsApp approval window open? (24 hours default)
7. Should I rate limit job applications? (Yes, 2/minute to avoid flags)
