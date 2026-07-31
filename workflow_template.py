# LangGraph Internship Agent Workflow Template

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from typing import TypedDict, Optional, List
from datetime import datetime
import json

# ============ STATE DEFINITION ============
class JobData(TypedDict):
    job_id: str
    title: str
    company: str
    description: str
    link: str

class ApplicationSummary(TypedDict):
    job_id: str
    company: str
    title: str
    match_score: float
    status: str  # pending, approved, rejected, applied

class AgentState(TypedDict):
    resume: str  # user's resume text
    portfolio_link: str
    github_link: str
    linkedin_link: str
    jobs_to_process: List[JobData]
    current_job: Optional[JobData]
    match_score: float
    match_reasoning: str
    user_approval: Optional[bool]  # from WhatsApp
    application_status: str
    applications_today: List[ApplicationSummary]
    errors: List[str]

# ============ TOOLS ============
@tool
def scrape_internships() -> List[JobData]:
    """Scrape internships from Indeed, LinkedIn, etc."""
    # Placeholder implementation
    return [
        {
            "job_id": "1",
            "title": "Python Backend Intern",
            "company": "TechCorp",
            "description": "Looking for Python dev with FastAPI experience...",
            "link": "https://example.com/job1"
        }
    ]

@tool
def calculate_match_score(resume: str, job_description: str) -> dict:
    """Calculate resume-JD match using LLM."""
    # Returns {"score": 85, "reasoning": "...", "key_matches": [...], "gaps": [...]}
    pass

@tool
def send_whatsapp_approval(user_phone: str, job_title: str, company: str, match_score: float) -> str:
    """Send WhatsApp message requesting approval."""
    # Use Twilio API
    pass

@tool
def auto_apply_to_job(job_link: str, resume: str, portfolio: str, github: str, linkedin: str) -> dict:
    """Auto-fill and submit application."""
    # Use Selenium/Playwright
    # Returns {"status": "submitted", "application_id": "..."}
    pass

@tool
def send_email_summary(recipient_email: str, applications: List[ApplicationSummary]) -> bool:
    """Send daily email summary."""
    pass

@tool
def send_whatsapp_summary(user_phone: str, applications: List[ApplicationSummary]) -> bool:
    """Send daily WhatsApp summary."""
    pass

# ============ NODES ============

def scraper_node(state: AgentState) -> AgentState:
    """Node 1: Fetch daily internships."""
    try:
        jobs = scrape_internships()
        state["jobs_to_process"] = jobs
        print(f"[SCRAPER] Found {len(jobs)} jobs")
    except Exception as e:
        state["errors"].append(f"Scraper error: {str(e)}")
    return state

def matcher_node(state: AgentState) -> AgentState:
    """Node 2: Match resume to current job."""
    if not state["jobs_to_process"]:
        return state
    
    state["current_job"] = state["jobs_to_process"][0]
    state["jobs_to_process"] = state["jobs_to_process"][1:]
    
    try:
        result = calculate_match_score(state["resume"], state["current_job"]["description"])
        state["match_score"] = result["score"]
        state["match_reasoning"] = result["reasoning"]
        print(f"[MATCHER] Score for {state['current_job']['title']}: {state['match_score']}%")
    except Exception as e:
        state["errors"].append(f"Matcher error: {str(e)}")
    
    return state

def approval_node(state: AgentState) -> AgentState:
    """Node 3: Request WhatsApp approval if score > 70."""
    if state["match_score"] < 70:
        state["application_status"] = "rejected_low_score"
        return state
    
    try:
        # Send WhatsApp message (webhook will handle response)
        send_whatsapp_approval(
            user_phone="+1234567890",  # Get from config
            job_title=state["current_job"]["title"],
            company=state["current_job"]["company"],
            match_score=state["match_score"]
        )
        state["application_status"] = "pending_approval"
        print(f"[APPROVAL] Sent WhatsApp for {state['current_job']['company']}")
    except Exception as e:
        state["errors"].append(f"Approval node error: {str(e)}")
    
    return state

def applicant_node(state: AgentState) -> AgentState:
    """Node 4: Auto-apply if approved."""
    if state["user_approval"] is not True:
        state["application_status"] = "rejected_by_user"
        return state
    
    try:
        result = auto_apply_to_job(
            job_link=state["current_job"]["link"],
            resume=state["resume"],
            portfolio=state["portfolio_link"],
            github=state["github_link"],
            linkedin=state["linkedin_link"]
        )
        state["application_status"] = "applied"
        
        # Log to applications_today
        state["applications_today"].append({
            "job_id": state["current_job"]["job_id"],
            "company": state["current_job"]["company"],
            "title": state["current_job"]["title"],
            "match_score": state["match_score"],
            "status": "applied"
        })
        print(f"[APPLICANT] Applied to {state['current_job']['company']}")
    except Exception as e:
        state["errors"].append(f"Applicant error: {str(e)}")
        state["application_status"] = "application_failed"
    
    return state

def summary_node(state: AgentState) -> AgentState:
    """Node 5: Generate and send daily summary."""
    try:
        send_email_summary(
            recipient_email="user@example.com",
            applications=state["applications_today"]
        )
        send_whatsapp_summary(
            user_phone="+1234567890",
            applications=state["applications_today"]
        )
        print(f"[SUMMARY] Sent report with {len(state['applications_today'])} applications")
    except Exception as e:
        state["errors"].append(f"Summary error: {str(e)}")
    
    return state

# ============ CONDITIONAL EDGES ============

def should_process_more_jobs(state: AgentState) -> str:
    """Decide: continue to next job or finish."""
    if state["jobs_to_process"]:
        return "matcher"
    return END

def should_request_approval(state: AgentState) -> str:
    """Decide: if score > 70, request approval."""
    if state["match_score"] >= 70:
        return "approval"
    return "check_more_jobs"

# ============ BUILD GRAPH ============

graph = StateGraph(AgentState)

# Add nodes
graph.add_node("scraper", scraper_node)
graph.add_node("matcher", matcher_node)
graph.add_node("approval", approval_node)
graph.add_node("applicant", applicant_node)
graph.add_node("summary", summary_node)

# Add edges
graph.set_entry_point("scraper")
graph.add_edge("scraper", "matcher")
graph.add_conditional_edges("matcher", should_request_approval, {
    "approval": "approval",
    "check_more_jobs": "matcher"  # Loop back (via check_more_jobs logic)
})
graph.add_edge("approval", "applicant")
graph.add_conditional_edges("applicant", should_process_more_jobs, {
    "matcher": "matcher",
    END: "summary"
})
graph.add_edge("summary", END)

# Compile
agent_workflow = graph.compile()

# ============ EXECUTION ============

if __name__ == "__main__":
    initial_state = AgentState(
        resume="""[Your resume text here]""",
        portfolio_link="https://portfolio.com",
        github_link="https://github.com/user",
        linkedin_link="https://linkedin.com/in/user",
        jobs_to_process=[],
        current_job=None,
        match_score=0,
        match_reasoning="",
        user_approval=None,
        application_status="",
        applications_today=[],
        errors=[]
    )
    
    # Run agent
    result = agent_workflow.invoke(initial_state)
    print("\n=== FINAL RESULT ===")
    print(f"Applications sent: {len(result['applications_today'])}")
    print(f"Errors: {len(result['errors'])}")
    if result["errors"]:
        for error in result["errors"]:
            print(f"  - {error}")

# ============ LANGSMITH INTEGRATION ============
# Add to environment:
# export LANGCHAIN_TRACING_V2=true
# export LANGCHAIN_API_KEY=your_key
# export LANGCHAIN_PROJECT=internship-agent
