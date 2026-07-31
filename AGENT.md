# Agent.md - Autonomous Internship Agent Project Guide

**Purpose:** This file serves as the master guide for coding agents to autonomously build the Internship Application Agent system. It defines roles, skills, workflows, and processes.

**Version:** 1.0  
**Last Updated:** January 2024  
**Project:** Autonomous Internship Application Agent  
**Duration:** 8 weeks  

---

## 🤖 Agent Architecture & Roles

The agent operates with multiple specialized skills (like a team of professionals):

```
┌─────────────────────────────────────────────────────────┐
│                  PRODUCT MANAGER ROLE                   │
│           (Main Agent - Orchestrates all work)          │
└────────────────┬────────────────────────────────────────┘
                 │
         ┌───────┴───────┬───────────────┬──────────────┐
         │               │               │              │
    ┌────▼────┐    ┌─────▼──────┐ ┌────▼────┐  ┌──────▼───┐
    │ Backend  │    │ DevOps &   │ │  QA &   │  │  ERROR   │
    │ Developer│    │ Infra Eng  │ │ Testing │  │ Handler  │
    └──────────┘    └────────────┘ └─────────┘  └──────────┘
```

---

## 👥 Skill Roles & Responsibilities

### 1. **Product Manager Role** (Main Agent)
**Responsibility:** Orchestrate entire project execution, make decisions, coordinate between teams

**Key Responsibilities:**
- Execute phase workflows
- Make architectural decisions
- Track progress and milestones
- Update documentation
- Handle escalations
- Review phase completions

**When to Use:** For overall project coordination and decision-making

---

### 2. **Backend/Full-Stack Developer Skill**
**Responsibility:** Implement all backend code, APIs, and business logic

**Capabilities:**
- ✅ Create Python files with complete implementations
- ✅ Write FastAPI endpoints
- ✅ Implement database models (SQLAlchemy)
- ✅ Write business logic (scraping, matching, etc.)
- ✅ Create utility functions and helpers
- ✅ Add type hints and documentation
- ✅ Follow PEP 8 style guidelines

**Code Quality Standards:**
```python
# Example of well-written code (ALWAYS follow this):

def search_internships(keyword: str, location: str) -> List[Dict]:
    """
    Search for internship listings using multiple sources.
    
    This function searches LinkedIn, Indeed, and other job platforms
    for internship positions matching the given criteria.
    
    Args:
        keyword (str): Job search keyword (e.g., "Python", "Data Science")
        location (str): Geographic location or "Remote"
    
    Returns:
        List[Dict]: List of job listings with structure:
            {
                'id': int,
                'title': str,
                'company': str,
                'location': str,
                'url': str,
                'description': str,
                'match_score': float (0-100)
            }
    
    Raises:
        ValueError: If keyword or location is empty
        RequestException: If API calls fail
    
    Example:
        >>> jobs = search_internships("Python", "Bangalore")
        >>> print(f"Found {len(jobs)} internships")
        Found 15 internships
    """
    # Validate input parameters
    if not keyword or not location:
        raise ValueError("Keyword and location cannot be empty")
    
    logger.info(f"Searching for internships: {keyword} in {location}")
    
    try:
        # Implementation here
        results = []
        # ... code ...
        logger.info(f"Found {len(results)} internships")
        return results
    
    except Exception as e:
        logger.error(f"Error searching internships: {e}", exc_info=True)
        raise
```

**Commenting Guidelines:**
- ✅ Add docstrings to all functions (Google style)
- ✅ Add inline comments for complex logic
- ✅ Document assumptions and edge cases
- ✅ Include type hints on all functions
- ✅ Add examples in docstrings

---

### 3. **DevOps & Infrastructure Engineer Skill**
**Responsibility:** Database, Docker, deployment, infrastructure setup

**Capabilities:**
- ✅ Create Docker files and docker-compose.yml
- ✅ Create database migrations (Alembic)
- ✅ Setup PostgreSQL schemas
- ✅ Create CI/CD pipelines (GitHub Actions)
- ✅ Create environment configuration files
- ✅ Setup logging and monitoring
- ✅ Create deployment scripts

**Infrastructure Standards:**
- Use parameterized queries (prevent SQL injection)
- Use connection pooling
- Add health checks
- Implement circuit breakers
- Add logging to all infrastructure code

---

### 4. **QA & Testing Engineer Skill**
**Responsibility:** Write tests, ensure code quality, validate functionality

**Capabilities:**
- ✅ Write unit tests (pytest)
- ✅ Write integration tests
- ✅ Write test fixtures and mocks
- ✅ Create test data
- ✅ Run coverage reports
- ✅ Validate API endpoints
- ✅ Performance testing

**Testing Standards:**
- Minimum 80% code coverage target
- All critical paths tested
- Edge cases covered
- Error scenarios tested
- Integration tests for APIs

---

### 5. **Error Handler & Problem Solver Skill**
**Responsibility:** Handle errors gracefully, troubleshoot issues, provide solutions

**Capabilities:**
- ✅ Catch and log errors
- ✅ Provide meaningful error messages
- ✅ Implement retry logic
- ✅ Implement fallback mechanisms
- ✅ Debug failing tests
- ✅ Troubleshoot environment issues
- ✅ Document known issues

**Error Handling Standard:**
```python
# ALWAYS implement error handling like this:

try:
    # Main operation
    result = perform_operation()
    
except SpecificError as e:
    # Handle specific errors
    logger.error(f"Specific error occurred: {e}", exc_info=True)
    # Implement retry logic or fallback
    return fallback_value
    
except Exception as e:
    # Handle unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Always provide meaningful error message
    raise CustomException(f"Operation failed: {str(e)}") from e

finally:
    # Cleanup resources
    cleanup()
```

---

## 📋 Phase-by-Phase Execution Guide

Each phase follows this workflow:

```
PHASE START
    ↓
[1] Read Phase Requirements
    ↓
[2] Setup/Verify Environment
    ↓
[3] Create Implementation Plan
    ↓
[4] Code Implementation
    ↓
[5] Testing & Validation
    ↓
[6] Error Handling Review
    ↓
[7] Documentation
    ↓
[8] Phase Completion Report
    ↓
[9] Update README
    ↓
PHASE COMPLETE
```

---

## 🎯 Phase 1: Foundation & Setup (Week 1-2)

### Phase Overview
**Objective:** Setup all infrastructure, database, and API foundation

**Deliverables:**
- ✅ Docker environment ready
- ✅ PostgreSQL database created
- ✅ FastAPI application structure
- ✅ Health check endpoints
- ✅ Logging setup
- ✅ Database models defined

### Step 1: Create Project Structure

**Task:** Create all necessary directories and files

**Files to Create:**
```
internship-agent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── connection.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── utils/
│       ├── __init__.py
│       └── logger.py
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

**Implementation Steps:**
1. Use Backend Developer skill to create Python files
2. Use DevOps skill to create Docker files
3. Ensure all files have proper headers and docstrings
4. Create proper .gitignore

### Step 2: Setup Database Models

**Task:** Create SQLAlchemy models for database

**Models to Create:**
- User model (with resume, preferences)
- Job model (with details from all sources)
- ApplicationRecord model (track applications)
- DailyReport model (store summaries)

**Code Template to Follow:**
```python
# ALWAYS use this template for models:

from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    """
    User model to store user information and preferences.
    
    This model stores basic user info, resume data, and user preferences
    for job searching and application automation.
    
    Attributes:
        id: Primary key, unique user identifier
        phone_number: User's WhatsApp phone number (unique)
        email: User's email address (unique, indexed for fast lookup)
        resume_text: Full resume text extracted from PDF
        skills: JSON array of extracted skills from resume
        preferences: JSON object with user preferences
        created_at: Timestamp when user registered
        updated_at: Timestamp of last update
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Contact Information
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Resume Data
    resume_text = Column(String, nullable=True)  # Full text extracted from PDF
    
    # Preferences
    skills = Column(JSON, default={})  # {skill: level, ...}
    preferences = Column(JSON, default={})  # User preferences for job search
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for common queries
    __table_args__ = (
        # Index on email for fast lookups
        # Index on created_at for date range queries
    )
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<User(id={self.id}, email={self.email}, phone={self.phone_number})>"
```

### Step 3: Setup FastAPI Application

**Task:** Create main FastAPI application with health checks

**Use Backend Developer skill to create app/main.py**

**Implementation Checklist:**
- ✅ Import FastAPI and create app instance
- ✅ Add health check endpoints
- ✅ Setup CORS if needed
- ✅ Add logging middleware
- ✅ Create database connection on startup
- ✅ Include proper error handling

### Step 4: Setup Docker Environment

**Task:** Create Docker configuration

**Use DevOps skill to create:**
- Dockerfile (with Python 3.11, dependencies, proper layers)
- docker-compose.yml (PostgreSQL, Redis, App services)

**Checklist:**
- ✅ Multi-stage Docker build
- ✅ Environment variables in compose
- ✅ Volume mounting for development
- ✅ Health checks defined

### Step 5: Testing & Validation

**Use QA skill to:**
1. Create tests for database connection
2. Create tests for API health endpoints
3. Run pytest to validate
4. Check test coverage (target: 80%+)

**Run Commands:**
```bash
pytest tests/ -v --cov=app --cov-report=html
```

### Step 6: Documentation & Phase Completion

**Use Backend Developer skill to create PHASE_1_COMPLETION.md**

**Template for Phase Completion Report:**

```markdown
# Phase 1: Foundation & Setup - Completion Report

## ✅ What Was Built

### 1. Project Structure
- Created directory structure with proper organization
- Setup for scalability and team collaboration
- Clear separation of concerns (app, tests, docker, etc.)

### 2. Database Layer
- Designed and created SQLAlchemy models
- Created 4 main models: User, Job, ApplicationRecord, DailyReport
- Setup with proper indexes for query performance
- Implemented timestamps for data tracking

### 3. API Foundation
- Created FastAPI application with health endpoints
- Implemented logging system
- Setup error handling framework
- Created database connection pool

### 4. Infrastructure
- Created Dockerfile with best practices
- Setup docker-compose with PostgreSQL and Redis
- Created environment configuration system
- Setup development environment

## 🛠️ Technical Approach (In Simple Terms)

**What is FastAPI?**
- A modern Python web framework that makes building APIs easy
- Automatically creates documentation (Swagger)
- Very fast due to async support
- Perfect for our job of handling multiple jobs simultaneously

**What is SQLAlchemy?**
- A tool that talks to databases in Python
- We define what data looks like (models)
- SQLAlchemy handles the actual database operations
- Makes code safer from SQL injection attacks

**What is Docker?**
- Packages our entire application with all dependencies
- Everyone on the team can run identical environments
- Easy to deploy to production servers
- No more "works on my machine" problems

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Files Created | 15 |
| Lines of Code | ~500 |
| Test Coverage | 85% |
| Database Models | 4 |
| API Endpoints | 3 (health checks) |

## ✨ Key Features Implemented

1. **Health Check System**
   - API health endpoint
   - Database connection health check
   - Service status monitoring

2. **Logging System**
   - Structured logging with levels
   - File and console output
   - Error tracking ready

3. **Database Design**
   - Proper indexing for performance
   - Relationships between tables
   - Data validation at model level

4. **Error Handling Framework**
   - Try-catch blocks implemented
   - Custom exceptions created
   - Meaningful error messages

## 🚀 What's Next?

**Phase 2 (Week 2-3):** Job Scraping
- Will implement scrapers for 4 job platforms
- Will aggregate and deduplicate jobs
- Will test with 100+ real job listings

## 📝 Code Quality

- ✅ All functions documented with docstrings
- ✅ Type hints on all parameters
- ✅ Error handling in place
- ✅ Logging at appropriate levels
- ✅ Tests written for core functionality

## 🔧 Running Phase 1 Output

```bash
# Start the application
docker-compose up -d

# Run tests
docker-compose exec app pytest tests/

# Check API
curl http://localhost:8000/health

# Check database
docker-compose exec db psql -U internship_user -d internship_agent -c "SELECT version();"
```

## 📋 Phase 1 Checklist

- [x] Project structure created
- [x] Database models designed
- [x] FastAPI application created
- [x] Docker setup complete
- [x] Tests written and passing
- [x] Documentation complete
- [x] All code properly commented
- [x] Error handling implemented
- [x] README updated

## 🎯 Success Criteria Met

- ✅ Application starts without errors
- ✅ All health checks pass
- ✅ Database connections work
- ✅ Tests have 80%+ coverage
- ✅ Code follows PEP 8 standards
- ✅ Documentation is complete

---

**Phase 1 Status:** ✅ COMPLETE

**Ready for Phase 2:** Yes ✅

**Date Completed:** [Auto-fill with today's date]
```

### Step 7: Update README

**Update main README.md with Phase 1 section**

---

## 🔄 Phase 2-8 Template

For each subsequent phase, follow this same pattern:

### Phase [X]: [Name] (Week [Y])

#### A. Phase Overview
- Objective
- Deliverables
- Key components

#### B. Implementation Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]
... etc

#### C. Code Implementation
- Files to create
- Code templates
- Quality standards

#### D. Testing
- Tests to write
- Coverage targets
- Validation steps

#### E. Completion Report
- What was built
- Technical explanation (simple)
- Statistics
- What's next

#### F. README Update
- Update progress section
- Add new section
- Update architecture diagram

---

## 🛡️ Error Handling Across All Phases

### Common Errors & How Agent Should Handle Them

#### 1. **Database Connection Errors**
```python
# IMPLEMENT THIS:

def get_db_connection():
    """Get database connection with error handling."""
    try:
        logger.info("Attempting database connection...")
        connection = create_connection()
        logger.info("Database connection successful")
        return connection
        
    except ConnectionError as e:
        logger.error(f"Database connection failed: {e}")
        # Provide helpful error message
        raise Exception(
            "Cannot connect to database. Please check:\n"
            "1. PostgreSQL is running\n"
            "2. DATABASE_URL is correct in .env\n"
            "3. Network connectivity\n"
            f"Error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected database error: {e}", exc_info=True)
        raise
```

#### 2. **API Key Missing Errors**
```python
# IMPLEMENT THIS:

def validate_api_keys():
    """Validate all required API keys are present."""
    required_keys = {
        'CLAUDE_API_KEY': 'Claude API (for AI matching)',
        'TWILIO_ACCOUNT_SID': 'Twilio (for WhatsApp)',
        'INDEED_API_KEY': 'Indeed API (for job scraping)',
    }
    
    missing_keys = []
    for key, description in required_keys.items():
        if not os.getenv(key):
            missing_keys.append(f"- {key} ({description})")
    
    if missing_keys:
        error_msg = "Missing required API keys:\n"
        error_msg += "\n".join(missing_keys)
        error_msg += "\n\nPlease add these to your .env file"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("All required API keys present")
```

#### 3. **Import Errors**
```python
# IMPLEMENT THIS:

def safe_import(module_name: str, package_name: str):
    """Safely import packages with helpful error messages."""
    try:
        return __import__(module_name)
    except ImportError:
        raise ImportError(
            f"Package '{package_name}' not installed.\n"
            f"Install with: pip install {package_name}"
        )
```

#### 4. **File Not Found Errors**
```python
# IMPLEMENT THIS:

def load_config_file(filepath: str) -> dict:
    """Load config file with error handling."""
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"Config file not found at {filepath}\n"
                f"Create one from template: cp {filepath}.example {filepath}"
            )
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in config file {filepath}\n"
            f"Error: {str(e)}"
        )
```

### Error Handling Checklist for Each Phase

- [ ] Try-catch blocks around external API calls
- [ ] Meaningful error messages (not just stack traces)
- [ ] Logging at ERROR level for failures
- [ ] Retry logic for transient failures
- [ ] Fallback mechanisms where possible
- [ ] User-friendly error messages
- [ ] Error recovery procedures documented

---

## 🔑 Manual Tasks That Agent Cannot Automate

Agent should recognize these tasks and provide step-by-step guides:

### Manual Task 1: Create Claude API Key
**Agent Output:**

```
⚠️ MANUAL TASK REQUIRED: Create Claude API Key

This requires human interaction with web browser.
Follow these steps:

1. Visit: https://console.anthropic.com
2. Click "Create New Secret Key"
3. Copy the generated key (starts with sk-proj-)
4. Add to your .env file:
   CLAUDE_API_KEY=sk-proj-xxxxxxxxxxxxx
5. Verify with: echo $CLAUDE_API_KEY
6. Report back when complete

✅ VERIFIED: [Human confirms API key added]
```

### Manual Task 2: Create LinkedIn API Access
**Agent Output:**

```
⚠️ MANUAL TASK REQUIRED: Request LinkedIn API Access

Steps:

1. Go to: https://www.linkedin.com/developers/apps
2. Click "Create an app"
3. Fill in application details:
   - App name: Internship Agent
   - Application URL: http://localhost:8000
   - Legal agreement: Agree
4. Request API access for:
   - Job Search API
   - Admin API
5. Wait 5-7 days for LinkedIn approval
6. Once approved, get your API key
7. Add to .env:
   LINKEDIN_API_KEY=your_key_here

⏱️ NOTE: This takes 5-7 days. Use Indeed in the meantime.
```

### Manual Task 3: Setup Twilio WhatsApp Sandbox
**Agent Output:**

```
⚠️ MANUAL TASK REQUIRED: Setup Twilio WhatsApp

Steps:

1. Create Twilio account: https://www.twilio.com
2. Verify phone number
3. Get $15 free credit
4. Navigate to WhatsApp Sandbox
5. Save your Twilio phone number (e.g., +1234567890)
6. Enable WhatsApp sandbox:
   - Save the connection string: "join [random]"
   - Send that to your WhatsApp number
   - Reply "join [random]" to activate
7. Get credentials:
   TWILIO_ACCOUNT_SID = ACxxxxx
   TWILIO_AUTH_TOKEN = xxxxx
   TWILIO_PHONE_NUMBER = +1234567890
8. Add to .env file

✅ When done, your WhatsApp sandbox is active!
```

### Manual Task 4: Generate Gmail App Password
**Agent Output:**

```
⚠️ MANUAL TASK REQUIRED: Setup Gmail App Password

Steps:

1. Enable 2-Factor Authentication on your Gmail:
   - Go to: https://myaccount.google.com/security
   - Click "2-Step Verification"
   - Follow the setup process

2. Generate App Password:
   - Go to: https://myaccount.google.com/apppasswords
   - Select: Mail
   - Select: Windows (or your OS)
   - Click "Generate"
   - Copy the 16-character password

3. Add to .env:
   GMAIL_ADDRESS=your-email@gmail.com
   GMAIL_PASSWORD=xxxx xxxx xxxx xxxx

4. Verify with test:
   python -c "
   from app.reporting.email_sender import EmailSender
   sender = EmailSender('email', 'password')
   sender.send_test_email('recipient@example.com')
   print('✅ Email sending works!')
   "
```

---

## 📖 Code Documentation Standards

Agent MUST follow these standards:

### 1. Function/Method Documentation
```python
def calculate_job_match_score(resume: Dict, job: Dict) -> float:
    """
    Calculate match score between resume and job.
    
    Algorithm:
    1. Extract skills from resume
    2. Extract required skills from job
    3. Calculate overlap percentage
    4. Adjust for experience level
    5. Return score 0-100
    
    Args:
        resume (Dict): Parsed resume data with keys:
            - skills: List[str] - Skills extracted from resume
            - experience_years: int - Total years of experience
            - education: List[str] - Educational background
        job (Dict): Job listing data with keys:
            - title: str - Job title
            - description: str - Full job description
            - required_skills: List[str] - Required skills
    
    Returns:
        float: Match score from 0-100, where:
            - 0-40: Poor match
            - 40-70: Moderate match
            - 70-100: Good match
    
    Raises:
        ValueError: If resume or job data is incomplete
        TypeError: If inputs are not dictionaries
    
    Example:
        >>> resume = {
        ...     'skills': ['Python', 'Django', 'PostgreSQL'],
        ...     'experience_years': 2,
        ...     'education': ['BS Computer Science']
        ... }
        >>> job = {
        ...     'title': 'Junior Developer',
        ...     'required_skills': ['Python', 'Django'],
        ...     'description': '...'
        ... }
        >>> score = calculate_job_match_score(resume, job)
        >>> print(score)
        85.5
    
    Note:
        - Scores above 70 are typically approved by user
        - Scores below 40 are auto-rejected
        - Machine learning adjustments applied in future versions
    """
    # Validate inputs
    if not isinstance(resume, dict) or not isinstance(job, dict):
        raise TypeError("resume and job must be dictionaries")
    
    if 'skills' not in resume or 'required_skills' not in job:
        raise ValueError("Missing required fields")
    
    # Extract skills
    resume_skills = set(skill.lower() for skill in resume.get('skills', []))
    job_skills = set(skill.lower() for skill in job.get('required_skills', []))
    
    # Calculate base score
    if not job_skills:
        return 50.0  # Default if no required skills
    
    matching_skills = resume_skills & job_skills
    skill_match = (len(matching_skills) / len(job_skills)) * 100
    
    # Adjust for experience
    experience_adjustment = min(resume.get('experience_years', 0) * 5, 20)
    
    # Final score
    final_score = min(skill_match + experience_adjustment, 100)
    
    logger.debug(f"Match score calculated: {final_score}")
    return final_score
```

### 2. Class Documentation
```python
class JobScraper:
    """
    Base class for job scraping from different platforms.
    
    This class provides common functionality for scraping job listings
    from various job platforms. Subclasses implement platform-specific logic.
    
    Attributes:
        platform_name (str): Name of the job platform (e.g., "LinkedIn")
        base_url (str): Base URL of the platform
        api_key (str): API key for authentication
        timeout (int): Request timeout in seconds
        
    Raises:
        ValueError: If platform_name is not recognized
        ConnectionError: If cannot connect to platform
    
    Example:
        >>> scraper = LinkedInScraper(api_key='your_key')
        >>> jobs = scraper.search('Python', 'Bangalore')
        >>> print(f"Found {len(jobs)} jobs")
        Found 25 jobs
    
    Note:
        - Implement rate limiting to avoid API blocks
        - Cache results to reduce API calls
        - Log all API calls for debugging
    """
    
    def __init__(self, platform_name: str, api_key: str, timeout: int = 30):
        """Initialize scraper."""
        self.platform_name = platform_name
        self.api_key = api_key
        self.timeout = timeout
        logger.info(f"Initialized {platform_name} scraper")
```

### 3. Inline Comments for Complex Logic
```python
def apply_job_filters(jobs: List[Dict], filters: Dict) -> List[Dict]:
    """Apply user filters to job listings."""
    
    filtered_jobs = []
    
    for job in jobs:
        # Check location filter
        if filters.get('locations'):
            # Split location string and check if any matches
            job_location = job['location'].lower()
            location_match = any(
                loc.lower() in job_location 
                for loc in filters['locations']
            )
            if not location_match:
                continue  # Skip this job
        
        # Check experience requirement
        if filters.get('min_experience'):
            # Regex pattern to extract years from description
            years_pattern = r'(\d+)\+?\s*years?'
            match = re.search(years_pattern, job['description'])
            required_years = int(match.group(1)) if match else 0
            
            # User's experience must meet requirement
            if get_user_experience() < required_years:
                continue
        
        # All filters passed, add to results
        filtered_jobs.append(job)
    
    logger.info(f"Filtered {len(jobs)} jobs to {len(filtered_jobs)}")
    return filtered_jobs
```

---

## ✅ Phase Completion Checklist

After each phase, Agent must verify:

### Code Quality
- [ ] All functions have docstrings
- [ ] Type hints on all parameters
- [ ] Error handling for all external calls
- [ ] Logging at appropriate levels
- [ ] No hardcoded values (use config)
- [ ] Code follows PEP 8 (run black formatter)

### Testing
- [ ] All tests passing
- [ ] Coverage > 80%
- [ ] Edge cases tested
- [ ] Error scenarios tested
- [ ] Integration tests pass

### Documentation
- [ ] README updated
- [ ] Phase completion report written
- [ ] API documentation updated
- [ ] Database schema documented
- [ ] Code comments clear and helpful

### Deployment Ready
- [ ] Docker builds successfully
- [ ] Environment variables documented
- [ ] Health checks pass
- [ ] Database migrations ready
- [ ] Logging configured

### Phase Report Submitted
- [ ] What was built (simple explanation)
- [ ] Technical approach explained
- [ ] Statistics provided
- [ ] Success criteria met
- [ ] Next phase planned

---

## 🎯 Agent Decision Tree

Agent uses this flowchart for decision making:

```
START
  ↓
Is task in "Manual Tasks" list?
├─ YES → Provide step-by-step guide
├─ NO → Continue
  ↓
Can task be done with code?
├─ YES → Use Backend Developer skill
├─ NO → Use appropriate skill
  ↓
Is error handling needed?
├─ YES → Add error handling
├─ NO → Continue
  ↓
Is testing needed?
├─ YES → Create tests first (TDD)
├─ NO → Create code
  ↓
Does code need documentation?
├─ YES → Add docstrings & comments
├─ NO → Continue
  ↓
Task Complete?
├─ YES → Move to next task
├─ NO → Debug and fix
  ↓
PHASE COMPLETE?
├─ YES → Create completion report
├─ NO → Continue phase
  ↓
END
```

---

## 📝 README Update Template

After each phase, update README with:

```markdown
## Progress

### Phase 1: Foundation & Setup ✅ COMPLETE
- ✅ Database schema created
- ✅ API foundation setup
- ✅ Docker environment ready
- Completion Date: [Date]
- Tests Coverage: 85%

### Phase 2: Job Scraping 🟡 IN PROGRESS
- Current: Implementing Indeed scraper
- Expected Completion: [Date]
- Tests Coverage: 60%

### Phase 3: AI Matching 🔴 NOT STARTED
- Expected Start: [Date]
- Estimated Duration: 2 weeks

## Architecture

[Updated diagram showing completed components]

## Current Status

- **Overall Progress:** 12.5% (Phase 1 of 8)
- **Latest Update:** Phase 1 completion report
- **Team:** 2 Backend Developers, 1 DevOps Engineer
- **Next Milestone:** 100+ jobs scraped

## Quick Start

[Updated setup instructions]
```

---

## 🚨 Agent Safety Guardrails

Agent must respect these boundaries:

### Boundaries Agent Should Follow
1. ✅ **Only create files in project directory**
   - Don't modify system files
   - Don't write outside project folder

2. ✅ **Never commit secrets**
   - Don't commit .env files
   - Don't log API keys
   - Use .gitignore properly

3. ✅ **Follow security best practices**
   - Use parameterized queries
   - Validate all inputs
   - No hardcoded credentials

4. ✅ **Test before claiming completion**
   - Run pytest
   - Run linting
   - Check code coverage
   - Validate functionality

5. ✅ **Document everything**
   - Every function documented
   - Every complex logic explained
   - Every error case handled

### When Agent Gets Stuck

If Agent encounters blocker:
1. **Log the error clearly**
2. **Document what was attempted**
3. **Suggest solutions**
4. **Wait for human guidance**
5. **Don't skip steps**

---

## 🔄 Phase Execution Workflow

### For Each Phase:

#### 1. **PLAN** (Read & Understand)
```
- Read phase requirements from main plan
- Understand deliverables
- Identify dependencies
- Check prerequisites
```

#### 2. **PREPARE** (Setup Environment)
```
- Verify all tools available
- Check for blockers
- Prepare data/mocks
- Setup test environment
```

#### 3. **BUILD** (Implement)
```
- Create files in order
- Write code with comments
- Add error handling
- Follow standards
```

#### 4. **TEST** (Validate)
```
- Write unit tests
- Write integration tests
- Run coverage report
- Fix failures
```

#### 5. **DOCUMENT** (Explain)
```
- Write docstrings
- Add inline comments
- Create completion report
- Update README
```

#### 6. **VERIFY** (Quality Check)
```
- Check code quality
- Verify test coverage
- Validate functionality
- Review documentation
```

#### 7. **REPORT** (Communicate)
```
- Create phase report
- Explain what was built
- Provide statistics
- Plan next phase
```

---

## 📊 Progress Tracking

Agent should maintain this tracking:

```
PHASE 1: Foundation & Setup
├─ Status: ✅ COMPLETE
├─ Start Date: Jan 1, 2024
├─ End Date: Jan 14, 2024
├─ Duration: 2 weeks
├─ Files Created: 15
├─ Lines of Code: 500
├─ Test Coverage: 85%
├─ Issues Found: 0
└─ Deployable: ✅ YES

PHASE 2: Job Scraping
├─ Status: 🟡 IN PROGRESS (30%)
├─ Start Date: Jan 15, 2024
├─ Expected End: Jan 28, 2024
├─ Files Created: 8
├─ Lines of Code: 1200
├─ Test Coverage: 65%
├─ Issues Found: 2
└─ Deployable: 🔴 NO (not complete)
```

---

## 🎓 Agent Learning & Improvement

After each phase, Agent should:

1. **Review what worked well**
   - Which approaches were effective?
   - What sped up development?

2. **Identify improvements**
   - What was difficult?
   - How to improve next time?

3. **Update processes**
   - Modify templates if needed
   - Improve error messages
   - Better documentation

4. **Share learnings**
   - Update AGENT.md with new patterns
   - Document solutions to new problems
   - Create reusable code snippets

---

## 🎯 Success Metrics

Agent tracks these KPIs:

| Metric | Target | How Measured |
|--------|--------|---|
| Code Coverage | > 80% | pytest --cov |
| Documentation | 100% | Every function documented |
| Test Pass Rate | 100% | pytest results |
| Error Handling | 100% | Code review |
| Code Quality | PEP 8 | black + flake8 |
| Phase Completion | On Time | vs. planned schedule |
| Comments Quality | Clear | Readability review |

---

## 🚀 Starting the Agent

### Command to Start Phase 1

```bash
# Agent should start with:
python -m agent.orchestrator \
  --phase 1 \
  --project internship-agent \
  --team-size 2 \
  --start-date $(date) \
  --verbose
```

### What Agent Does Next

1. Reads this AGENT.md file
2. Reads implementation plan from Internship_Agent_Implementation_Plan.md
3. Reads quick reference from Quick_Reference_Guide.md
4. Starts Phase 1 execution
5. Reports progress and blockers
6. Completes phase with report
7. Updates README
8. Moves to Phase 2

---

## 📞 Getting Agent Help

If Agent is stuck, provide:
- Specific error message
- What was being attempted
- Which phase
- Previous successful steps

Agent will then:
- Analyze the issue
- Provide diagnosis
- Suggest solutions
- Continue execution

---

## 🎉 Final Notes for Agent

**Remember:**
- ✅ Quality over speed
- ✅ Test everything
- ✅ Document clearly
- ✅ Handle errors gracefully
- ✅ Report progress honestly
- ✅ Ask for help when needed

**You are building a real, production-grade system. Act like a professional development team.**

---

**This AGENT.md is your guide. Reference it constantly.**

**Let's build something amazing! 🚀**

---

## 🔧 Advanced Implementation Patterns

### Pattern 1: Database Operation Pattern

**Use this pattern for ALL database operations:**

```python
from app.database import get_db
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

def create_user(
    phone_number: str,
    email: str,
    resume_text: str,
    db: Session
) -> User:
    """
    Create a new user in the database.
    
    This function handles all database operations safely:
    - Validates input data
    - Checks for duplicates
    - Commits transaction
    - Handles errors gracefully
    
    Args:
        phone_number (str): User's WhatsApp phone number
        email (str): User's email address
        resume_text (str): Extracted resume text
        db (Session): SQLAlchemy database session
    
    Returns:
        User: Created user object with ID
    
    Raises:
        ValueError: If phone or email already exists
        IntegrityError: If database constraint violated
    
    Example:
        >>> db = get_db()
        >>> user = create_user("+919876543210", "user@example.com", resume_text, db)
        >>> print(f"Created user {user.id}")
        Created user 1
    """
    
    try:
        # Step 1: Validate inputs
        logger.info(f"Creating user: {email}")
        
        if not phone_number or not email:
            raise ValueError("Phone number and email required")
        
        if not isinstance(resume_text, str):
            raise TypeError("Resume text must be string")
        
        # Step 2: Check for duplicates
        existing_user = db.query(User).filter(
            (User.phone_number == phone_number) | 
            (User.email == email)
        ).first()
        
        if existing_user:
            error_msg = f"User already exists with email: {email}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        # Step 3: Create new user object
        new_user = User(
            phone_number=phone_number,
            email=email,
            resume_text=resume_text,
            # Parse resume and extract skills
            skills=parse_resume_skills(resume_text),
            preferences={}  # Default empty preferences
        )
        
        # Step 4: Add to session and commit
        db.add(new_user)
        db.flush()  # Get the ID without committing
        
        # Step 5: Log successful creation
        logger.info(f"User created with ID: {new_user.id}")
        
        db.commit()
        
        # Step 6: Return the created object
        return new_user
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {e}")
        raise ValueError("Duplicate user data") from e
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise
```

**Checklist for database operations:**
- [ ] Input validation at start
- [ ] Meaningful variable names
- [ ] Logging before and after
- [ ] Proper error handling
- [ ] Transaction management (commit/rollback)
- [ ] Docstring with example
- [ ] Type hints

---

### Pattern 2: API Endpoint Pattern

**Use this pattern for ALL FastAPI endpoints:**

```python
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

@router.get(
    "/search",
    response_model=JobSearchResponse,
    summary="Search for internship jobs",
    description="Search for internship listings by keyword and location"
)
async def search_jobs(
    keyword: str = Query(..., min_length=2, description="Job search keyword"),
    location: str = Query(..., min_length=2, description="Job location or Remote"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    min_score: int = Query(60, ge=0, le=100, description="Minimum match score"),
    db: Session = Depends(get_db)
) -> JobSearchResponse:
    """
    Search for internship job listings.
    
    This endpoint searches across all job sources (LinkedIn, Indeed, AngelList)
    and returns matching internship positions filtered by user preferences.
    
    Query Parameters:
        keyword: The job search keyword (e.g., "Python Developer")
        location: Geographic location or "Remote"
        limit: Max results to return (1-100, default 20)
        offset: Pagination offset (default 0)
        min_score: Minimum match score 0-100 (default 60)
    
    Returns:
        JobSearchResponse object containing:
            - jobs: List of matching job listings
            - total: Total number of matches
            - offset: Pagination offset used
            - limit: Limit used
    
    Raises:
        HTTPException 400: If validation fails
        HTTPException 500: If database error
        HTTPException 503: If job scraper unavailable
    
    Example:
        GET /api/v1/jobs/search?keyword=python&location=Bangalore&limit=10
        
        Response:
        {
            "jobs": [
                {
                    "id": 1,
                    "title": "Python Developer Intern",
                    "company": "TechCorp",
                    "location": "Bangalore",
                    "match_score": 85
                }
            ],
            "total": 45,
            "offset": 0,
            "limit": 10
        }
    """
    
    try:
        # Step 1: Log request
        logger.info(f"Job search: keyword={keyword}, location={location}")
        
        # Step 2: Validate parameters
        if not keyword or len(keyword) < 2:
            raise HTTPException(
                status_code=400,
                detail="Keyword must be at least 2 characters"
            )
        
        # Step 3: Query database
        query = db.query(Job)
        
        # Apply filters
        query = query.filter(
            Job.title.ilike(f"%{keyword}%") |
            Job.description.ilike(f"%{keyword}%")
        )
        
        if location.lower() != "remote":
            query = query.filter(Job.location.ilike(f"%{location}%"))
        
        # Step 4: Get total count
        total_count = query.count()
        
        # Step 5: Apply pagination
        jobs = query.limit(limit).offset(offset).all()
        
        # Step 6: Log results
        logger.info(f"Found {len(jobs)} jobs (total: {total_count})")
        
        # Step 7: Return response
        return JobSearchResponse(
            jobs=[JobResponse.from_orm(job) for job in jobs],
            total=total_count,
            offset=offset,
            limit=limit
        )
    
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error searching jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while searching for jobs"
        )
```

**Checklist for API endpoints:**
- [ ] Proper URL and method
- [ ] Input validation with Query parameters
- [ ] Type hints on all parameters
- [ ] Response model defined
- [ ] Comprehensive docstring
- [ ] Error handling (400, 500, etc.)
- [ ] Logging at start, success, and error
- [ ] Example in docstring

---

### Pattern 3: External API Call Pattern

**Use this pattern for ALL external API calls:**

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class ExternalAPIClient:
    """
    Client for making external API calls with retry logic.
    
    This class handles:
    - Connection pooling
    - Automatic retries for transient failures
    - Timeout management
    - Request/response logging
    - Error handling
    """
    
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        """
        Initialize API client.
        
        Args:
            api_key: API authentication key
            base_url: Base URL for API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        
        # Create session with retry strategy
        self.session = self._create_session()
        
        logger.info(f"Initialized API client for {base_url}")
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.
        
        Returns:
            Configured requests.Session object
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # Total retries
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these
            allowed_methods=["GET", "POST"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make GET request with error handling.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            requests.RequestException: If request fails after retries
        """
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # Log request
            logger.debug(f"GET {url} with params {params}")
            
            # Make request with timeout
            response = self.session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Log success
            logger.debug(f"Response status: {response.status_code}")
            
            # Return JSON response
            return response.json()
        
        except requests.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise requests.RequestException(
                f"Request to {url} timed out after {self.timeout}s"
            ) from e
        
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e}")
            
            if e.response.status_code == 401:
                raise requests.RequestException(
                    "Authentication failed. Check API key."
                ) from e
            elif e.response.status_code == 429:
                raise requests.RequestException(
                    "Rate limit exceeded. Please wait before retrying."
                ) from e
            else:
                raise requests.RequestException(
                    f"API returned {e.response.status_code}: {e.response.text}"
                ) from e
        
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
        
        except ValueError as e:
            logger.error(f"Invalid response JSON: {e}")
            raise requests.RequestException(
                "API returned invalid JSON response"
            ) from e
```

**Checklist for external API calls:**
- [ ] Retry logic implemented
- [ ] Timeout specified
- [ ] Error handling for common errors (timeout, 429, 401, 500)
- [ ] Request/response logging
- [ ] Meaningful error messages
- [ ] Docstring with example
- [ ] No hardcoded API keys

---

### Pattern 4: Scheduler Job Pattern

**Use this pattern for ALL scheduled jobs:**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

class JobScheduler:
    """
    Manages all scheduled jobs for the application.
    
    Jobs run at specific times:
    - 6 AM: Scrape new jobs
    - 7 AM: Match jobs with users
    - 12 PM: Process applications
    - 6 PM: Send daily reports
    """
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = BackgroundScheduler()
        logger.info("Scheduler initialized")
    
    def register_jobs(self):
        """Register all scheduled jobs."""
        
        # Job 1: Scrape jobs at 6 AM
        self.scheduler.add_job(
            func=self.job_scrape_and_aggregate,
            trigger=CronTrigger(hour=6, minute=0),
            id="scrape_jobs",
            name="Scrape and aggregate job listings",
            replace_existing=True,
            max_instances=1  # Only one instance at a time
        )
        logger.info("Registered job: scrape_jobs at 06:00")
        
        # Job 2: Match jobs at 7 AM
        self.scheduler.add_job(
            func=self.job_match_and_notify,
            trigger=CronTrigger(hour=7, minute=0),
            id="match_jobs",
            name="Match jobs and send WhatsApp",
            replace_existing=True,
            max_instances=1
        )
        logger.info("Registered job: match_jobs at 07:00")
        
        # Job 3: Process applications at 12 PM
        self.scheduler.add_job(
            func=self.job_apply_approved,
            trigger=CronTrigger(hour=12, minute=0),
            id="apply_approved",
            name="Apply to approved jobs",
            replace_existing=True,
            max_instances=1
        )
        logger.info("Registered job: apply_approved at 12:00")
        
        # Job 4: Send daily reports at 6 PM
        self.scheduler.add_job(
            func=self.job_send_reports,
            trigger=CronTrigger(hour=18, minute=0),
            id="send_reports",
            name="Send daily summary reports",
            replace_existing=True,
            max_instances=1
        )
        logger.info("Registered job: send_reports at 18:00")
    
    def job_scrape_and_aggregate(self):
        """
        Scrape jobs from all sources and aggregate.
        
        Runs daily at 6 AM.
        Scrapes LinkedIn, Indeed, AngelList, and career pages.
        Deduplicates and stores in database.
        """
        
        job_id = "scrape_jobs"
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting job scraping at {start_time}")
            
            from app.scrapers.job_aggregator import JobAggregator
            from app.database import get_db
            
            db = next(get_db())
            
            # Run aggregation
            aggregator = JobAggregator(db)
            total_jobs = aggregator.scrape_all_sources()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[{job_id}] ✅ COMPLETED in {duration:.2f}s. "
                f"Scraped {total_jobs} jobs"
            )
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"[{job_id}] ❌ FAILED after {duration:.2f}s: {e}",
                exc_info=True
            )
            # Send alert to admin
            self._send_job_failure_alert(job_id, str(e))
    
    def job_match_and_notify(self):
        """
        Match scraped jobs with users and send WhatsApp.
        
        Runs daily at 7 AM.
        Scores jobs against user resumes.
        Sends top 10 matches via WhatsApp.
        """
        
        job_id = "match_jobs"
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting job matching at {start_time}")
            
            from app.matching.job_matcher import JobMatcher
            from app.approval.whatsapp_bot import WhatsAppBot
            from app.database import get_db
            
            db = next(get_db())
            matcher = JobMatcher()
            whatsapp = WhatsAppBot()
            
            # Get all users
            users = db.query(User).all()
            total_sent = 0
            
            for user in users:
                # Get unmatched jobs for today
                jobs = self._get_unmatched_jobs(db, user)
                
                # Match and send
                for job in jobs[:10]:  # Top 10 per user
                    score = matcher.calculate_score(user, job)
                    
                    if score['overall_score'] >= 60:
                        # Send WhatsApp
                        whatsapp.send_job_alert(user.phone_number, job, score)
                        total_sent += 1
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[{job_id}] ✅ COMPLETED in {duration:.2f}s. "
                f"Sent {total_sent} notifications"
            )
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"[{job_id}] ❌ FAILED after {duration:.2f}s: {e}",
                exc_info=True
            )
            self._send_job_failure_alert(job_id, str(e))
    
    def job_apply_approved(self):
        """
        Apply to all user-approved jobs.
        
        Runs daily at 12 PM.
        Finds approved jobs waiting for application.
        Uses Selenium to auto-fill and submit applications.
        """
        
        job_id = "apply_approved"
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting auto-apply at {start_time}")
            
            from app.applications.auto_apply import AutoApplier
            from app.database import get_db
            
            db = next(get_db())
            applier = AutoApplier()
            
            # Get approved jobs
            approved_apps = db.query(ApplicationRecord).filter_by(
                status='approved',
                application_timestamp=None
            ).all()
            
            successful = 0
            failed = 0
            
            for app in approved_apps:
                try:
                    result = applier.apply(app.job.url)
                    if result['status'] == 'success':
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.warning(f"Failed to apply: {e}")
                    failed += 1
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[{job_id}] ✅ COMPLETED in {duration:.2f}s. "
                f"Successful: {successful}, Failed: {failed}"
            )
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"[{job_id}] ❌ FAILED after {duration:.2f}s: {e}",
                exc_info=True
            )
            self._send_job_failure_alert(job_id, str(e))
    
    def job_send_reports(self):
        """
        Send daily summary reports to users.
        
        Runs daily at 6 PM.
        Generates daily report for each user.
        Sends via email and WhatsApp.
        """
        
        job_id = "send_reports"
        start_time = datetime.now()
        
        try:
            logger.info(f"[{job_id}] Starting report generation at {start_time}")
            
            from app.reporting.daily_report import DailyReportGenerator
            from app.database import get_db
            
            db = next(get_db())
            generator = DailyReportGenerator()
            
            users = db.query(User).all()
            reports_sent = 0
            
            for user in users:
                try:
                    report = generator.generate_report(user)
                    generator.send_report(user, report)
                    reports_sent += 1
                except Exception as e:
                    logger.warning(f"Failed to send report for {user.email}: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"[{job_id}] ✅ COMPLETED in {duration:.2f}s. "
                f"Reports sent: {reports_sent}"
            )
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"[{job_id}] ❌ FAILED after {duration:.2f}s: {e}",
                exc_info=True
            )
            self._send_job_failure_alert(job_id, str(e))
    
    def _send_job_failure_alert(self, job_id: str, error: str):
        """
        Send alert to admin when job fails.
        
        Args:
            job_id: ID of failed job
            error: Error message
        """
        try:
            logger.warning(f"Sending failure alert for job {job_id}")
            # Send email to admin
            # Implementation depends on your email setup
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def _get_unmatched_jobs(self, db, user):
        """Get jobs not yet matched to user."""
        from app.database import JobMatch
        
        matched_jobs = db.query(JobMatch.job_id).filter_by(
            user_id=user.id
        ).all()
        
        matched_ids = [jm[0] for jm in matched_jobs]
        
        return db.query(Job).filter(
            ~Job.id.in_(matched_ids)
        ).limit(50).all()
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.register_jobs()
            self.scheduler.start()
            logger.info("✅ Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time)
                }
                for job in self.scheduler.get_jobs()
            ]
        }
```

**Checklist for scheduled jobs:**
- [ ] Job ID and name defined
- [ ] Cron schedule correct
- [ ] max_instances=1 (prevent overlap)
- [ ] Try-catch block with logging
- [ ] Success and failure logging
- [ ] Duration tracking
- [ ] Failure alert system
- [ ] Docstring with run time

---

## 📝 Testing Patterns

### Pattern: Unit Test Template

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.scrapers.indeed_scraper import IndeedScraper
from app.database.models import User, Job

class TestIndeedScraper:
    """Test suite for Indeed job scraper."""
    
    @pytest.fixture
    def scraper(self):
        """Create scraper instance for testing."""
        return IndeedScraper(api_key="test_key")
    
    @pytest.fixture
    def sample_job_response(self):
        """Sample Indeed API response."""
        return {
            "jobs": [
                {
                    "job_key": "12345",
                    "job_title": "Python Developer Intern",
                    "company": "TechCorp",
                    "job_city": "Bangalore",
                    "job_state": "KA",
                    "snippet": "We are looking for...",
                    "job_url": "https://indeed.com/job/12345",
                    "job_description": "Full description..."
                }
            ]
        }
    
    def test_scraper_initialization(self, scraper):
        """Test scraper initializes with correct attributes."""
        assert scraper.api_key == "test_key"
        assert scraper.base_url == "https://indeed-api.p.rapidapi.com/jobs"
        assert scraper.timeout == 30
    
    @patch('requests.get')
    def test_search_success(self, mock_get, scraper, sample_job_response):
        """Test successful job search."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = sample_job_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Execute
        jobs = scraper.search("Python", "Bangalore")
        
        # Assert
        assert len(jobs) == 1
        assert jobs[0]['title'] == "Python Developer Intern"
        assert jobs[0]['company'] == "TechCorp"
        assert jobs[0]['source'] == "indeed"
        
        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "python" in call_args.kwargs['params']['query'].lower()
    
    @patch('requests.get')
    def test_search_empty_results(self, mock_get, scraper):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {"jobs": []}
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        jobs = scraper.search("NonExistent", "Mars")
        
        assert len(jobs) == 0
    
    @patch('requests.get')
    def test_search_api_error(self, mock_get, scraper):
        """Test search when API returns error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception):
            scraper.search("Python", "Bangalore")
    
    @patch('requests.get')
    def test_search_timeout(self, mock_get, scraper):
        """Test search when request times out."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timeout")
        
        with pytest.raises(requests.Timeout):
            scraper.search("Python", "Bangalore")
    
    def test_parse_job_correctly(self, scraper, sample_job_response):
        """Test job parsing from API response."""
        job_data = sample_job_response['jobs'][0]
        parsed = scraper._parse_job(job_data)
        
        assert parsed['title'] == "Python Developer Intern"
        assert parsed['source'] == "indeed"
        assert parsed['url'] == "https://indeed.com/job/12345"
        assert 'skills' in parsed or 'description' in parsed
```

**Checklist for unit tests:**
- [ ] Use pytest fixtures
- [ ] Mock external dependencies
- [ ] Test success case
- [ ] Test empty/edge cases
- [ ] Test error scenarios
- [ ] Test with invalid input
- [ ] Assert return values
- [ ] Verify API calls made

---

## 🔍 Integration Testing Pattern

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.database.models import User, Job

@pytest.fixture
def db():
    """Create test database."""
    Base.metadata.create_all(bind=engine)
    yield SessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

class TestJobSearchAPI:
    """Integration tests for job search API."""
    
    def test_search_jobs_endpoint(self, client, db):
        """Test complete job search flow."""
        
        # Setup: Add test data
        test_job = Job(
            title="Python Developer",
            company="TechCorp",
            location="Bangalore",
            url="https://example.com/job1",
            description="Test job"
        )
        db.add(test_job)
        db.commit()
        
        # Execute: Call API
        response = client.get(
            "/api/v1/jobs/search",
            params={
                "keyword": "Python",
                "location": "Bangalore",
                "limit": 10
            }
        )
        
        # Assert: Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data['jobs']) == 1
        assert data['total'] == 1
        assert data['jobs'][0]['title'] == "Python Developer"
    
    def test_search_with_invalid_keyword(self, client):
        """Test search validation."""
        response = client.get(
            "/api/v1/jobs/search",
            params={"keyword": "a", "location": "Bangalore"}
        )
        
        assert response.status_code == 400
        assert "Keyword" in response.json()['detail']
```

---

## 🛠️ Debugging & Troubleshooting Guide

### How to Debug When Tests Fail

```python
# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run with verbose output
pytest tests/ -vv -s

# Run specific test
pytest tests/test_scrapers.py::TestIndeedScraper::test_search_success -vv

# Run with print statements
pytest tests/ -s  # Captures print output

# Generate HTML coverage report
pytest --cov=app --cov-report=html tests/
# Open htmlcov/index.html
```

### Common Agent Errors & Solutions

#### Error 1: "ModuleNotFoundError: No module named 'app'"

**Cause:** Python path not set correctly

**Solution:**
```bash
# Add to .env or startup script
export PYTHONPATH="${PYTHONPATH}:/path/to/project"

# Or run from project root
python -m app.main
```

#### Error 2: "psycopg2.OperationalError: cannot connect to server"

**Cause:** PostgreSQL not running

**Solution:**
```bash
# Check if PostgreSQL is running
psql --version
sudo service postgresql start  # Linux
brew services start postgresql  # macOS

# Check connection
psql -U postgres -c "SELECT version();"
```

#### Error 3: "API returned 401: Unauthorized"

**Cause:** API key invalid or missing

**Solution:**
```bash
# Verify API key in .env
echo $CLAUDE_API_KEY

# Test API key directly
curl -H "Authorization: Bearer $CLAUDE_API_KEY" \
     https://api.anthropic.com/v1/models
```

#### Error 4: "Tests failing with 'connection pool overflow'"

**Cause:** Database connections not being closed

**Solution:**
```python
# Always close database sessions
from app.database import get_db

db = next(get_db())
try:
    # Do work
    pass
finally:
    db.close()  # Always close
```

---

## 📊 Monitoring & Logging Best Practices

### Setup Logging Throughout Application

```python
# app/utils/logger.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Setup comprehensive logging for module.
    
    Args:
        name: Module name for logger
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with rotation
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler(
        f'logs/{name}.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# Usage in your modules
logger = setup_logging(__name__)

def important_function():
    logger.info("Function started")
    try:
        # Do work
        logger.debug("Step 1 completed")
        logger.debug("Step 2 completed")
        logger.info("Function completed successfully")
    except Exception as e:
        logger.error(f"Function failed: {e}", exc_info=True)
        raise
```

---

## 🎯 Performance Optimization Patterns

### Caching Pattern

```python
from functools import lru_cache
from datetime import datetime, timedelta
import json

class CacheManager:
    """
    Simple caching for expensive operations.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            ttl_seconds: Cache time-to-live in seconds
        """
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str):
        """Get cached value if exists and not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                logger.debug(f"Cache hit for {key}")
                return data
            else:
                del self.cache[key]  # Expired
                logger.debug(f"Cache expired for {key}")
        
        return None
    
    def set(self, key: str, value):
        """Cache a value."""
        self.cache[key] = (value, datetime.now())
        logger.debug(f"Cached {key}")
    
    def clear(self):
        """Clear all cached values."""
        self.cache.clear()
        logger.info("Cache cleared")

# Usage
cache = CacheManager(ttl_seconds=3600)

def get_user_profile(user_id: int):
    """Get user profile with caching."""
    cache_key = f"user_{user_id}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Fetch from database
    db = get_db()
    user = db.query(User).get(user_id)
    
    # Cache result
    cache.set(cache_key, user)
    
    return user
```

---

## 🚀 Deployment Verification Checklist

Before deploying to production, Agent must verify:

### Code Quality Checks
```bash
# Run all quality checks
black app/  # Format code
flake8 app/  # Lint
mypy app/  # Type checking
pytest --cov=app --cov-report=term-missing  # Test coverage
bandit -r app/  # Security check
```

### Environment Verification
```bash
# Check all required env vars
python -c "
import os
required = [
    'CLAUDE_API_KEY',
    'DATABASE_URL',
    'TWILIO_ACCOUNT_SID',
    'TWILIO_AUTH_TOKEN',
]
for var in required:
    if var not in os.environ:
        print(f'❌ Missing: {var}')
    else:
        print(f'✅ Found: {var}')
"
```

### Database Verification
```bash
# Check database connectivity
python -c "
from app.database import get_db
db = next(get_db())
result = db.execute('SELECT 1')
print('✅ Database connected')
"
```

### Application Startup
```bash
# Start app and verify health
timeout 10 python -m app.main &
sleep 3
curl http://localhost:8000/health
```

---

## 📋 Phase Completion Template (Extended)

After each phase, create detailed report:

```markdown
# Phase [X]: [Name] - Complete Analysis

## Executive Summary
[2-3 sentence overview of what was built]

## What Was Built

### Components Delivered
- [ ] Component 1: [Description]
- [ ] Component 2: [Description]
- [ ] Component 3: [Description]

### Code Statistics
- Total Files Created: X
- Total Lines of Code: XXXX
- Documentation Lines: XXX
- Test Lines: XXX
- Comments Density: X%

## Technical Explanation (Simple)

### Architecture Decisions
1. **Decision 1: Why we chose X**
   - Pro: Fast, simple
   - Con: Limited scalability
   - Alternative: Y
   - Why not: Too complex for MVP

2. **Decision 2: Why we chose Z**
   - Pro: Reliable, battle-tested
   - Con: Slower
   - Alternative: W
   - Why not: Too new, risky

### Implementation Approach
[Explain in simple terms how system works]

### Key Algorithms/Patterns Used
1. Pattern 1: Used for [purpose]
2. Pattern 2: Used for [purpose]

## Code Quality Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Test Coverage | >80% | 85% | ✅ |
| Linting (PEP 8) | 0 errors | 0 errors | ✅ |
| Type Hints | 100% | 95% | 🟡 |
| Documentation | 100% | 100% | ✅ |

## Testing Summary

### Unit Tests
- Total: X
- Passing: X
- Failing: 0
- Coverage: X%

### Integration Tests
- Total: X
- Passing: X
- Scenarios Covered: [List]

### Manual Testing
- [Feature tested manually]
- [Feature tested manually]

## Error Handling

### Errors Handled
1. [Error type]: [How handled]
2. [Error type]: [How handled]
3. [Error type]: [How handled]

### Retry Logic
- [Implemented where]
- Retry count: X
- Backoff strategy: [Type]

## Performance

| Aspect | Value | Target | Status |
|--------|-------|--------|--------|
| API Response | 150ms | <500ms | ✅ |
| DB Query | 50ms | <200ms | ✅ |
| Job Scraping | 30s | <60s | ✅ |

## Known Limitations & Future Work

### Current Limitations
1. [Limitation]: [Why/Impact]
2. [Limitation]: [Why/Impact]

### Future Improvements
1. [Improvement]: Phase [X]
2. [Improvement]: Phase [X]

## Deployment Status

- [ ] Code reviewed and approved
- [ ] Tests passing (100%)
- [ ] Documentation complete
- [ ] Staging environment tested
- [ ] Ready for production

## Lessons Learned

### What Went Well
- [Achievement]
- [Achievement]

### What Could Be Better
- [Area for improvement]
- [Area for improvement]

### Team Notes
- [Important note]
- [Important note]

## Next Steps

### Immediate (This Week)
1. [Task]
2. [Task]

### Short Term (This Month)
1. [Task]
2. [Task]

### Long Term (This Quarter)
1. [Task]
2. [Task]

## Sign-Off

**Phase Completed:** [Date]
**Approved By:** [Agent]
**Quality Score:** [90/100]
**Ready for Phase [X+1]:** ✅ YES
```

---

**Remember:**
- 🤖 You are an autonomous agent acting as a professional development team
- 📝 Document everything thoroughly
- 🧪 Test rigorously
- ✅ Verify quality constantly
- 🚀 Build production-grade code
- 🔄 Follow patterns consistently

**This is your complete playbook. Use it to build an exceptional system!**

