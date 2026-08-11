"""
tools/resume_parser.py
----------------------
Parses a resume (PDF or TXT) and extracts:
  - Full candidate contact profile (name, email, phone, github, linkedin)
  - Education details (degree, institution, CGPA, year)
  - Skills (categorized)
  - Work experience & projects
  - Professional summary

All extracted data is used by the Vision AI to fill job application forms
with accurate, complete information from the actual resume.
"""

import os
import re
from typing import Dict, List, Any

try:
    import fitz  # PyMuPDF — best quality text extraction
except ImportError:
    fitz = None

try:
    import PyPDF2  # fallback
except ImportError:
    PyPDF2 = None


# ──────────────────────────────────────────────────────────────────────────────
# Text Extraction
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF (fitz) with PyPDF2 fallback."""
    text = ""
    if fitz is not None:
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text() + "\n"
            if text.strip():
                return text
        except Exception:
            pass

    if PyPDF2 is not None:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                return text
        except Exception:
            pass

    raise ValueError(f"Could not extract text from PDF: {file_path}")


def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────────────────────────────────────
# Field Extractors
# ──────────────────────────────────────────────────────────────────────────────

def _extract_email(text: str) -> str:
    matches = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return matches[0] if matches else ""


def _extract_phone(text: str) -> str:
    # Match international and Indian formats
    matches = re.findall(r"(?:\+91[-\s]?)?[6-9]\d{9}|\+?\d[\d\s\-()]{9,14}\d", text)
    for m in matches:
        cleaned = re.sub(r"[\s\-()]", "", m)
        if len(cleaned) >= 10:
            return m.strip()
    return ""


def _extract_linkedin(text: str) -> str:
    match = re.search(r"linkedin\.com/in/[\w\-]+", text, re.IGNORECASE)
    if match:
        url = match.group(0)
        return f"https://{url}" if not url.startswith("http") else url
    return ""


def _extract_github(text: str) -> str:
    match = re.search(r"github\.com/[\w\-]+", text, re.IGNORECASE)
    if match:
        url = match.group(0)
        return f"https://{url}" if not url.startswith("http") else url
    return ""


def _extract_name(text: str) -> str:
    """
    Resume name is almost always the first non-empty line at the top.
    Filter out lines that look like headers/keywords.
    Returns Title-cased name.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    skip_keywords = ["resume", "curriculum vitae", "cv", "email", "phone",
                     "linkedin", "github", "address", "www.", "http"]
    for line in lines[:5]:
        lower = line.lower()
        if any(k in lower for k in skip_keywords):
            continue
        # A name: 2-4 words, mostly letters
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r"[A-Za-z'\-]+$", w) for w in words):
            # Normalize to Title Case (handles ALL CAPS resumes)
            return " ".join(w.capitalize() for w in words)
    return ""


def _extract_location(text: str) -> str:
    """Extract city/country from common resume patterns."""
    patterns = [
        r"Location:\s*(.+)",
        r"Based in\s+([A-Za-z ,]+)",
        r"\|\s*([A-Za-z ,]{3,30})\s*\|",   # e.g. | India |
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip("|").strip()
            if len(loc) < 40:
                return loc
    return "India"


def _extract_summary(text: str) -> str:
    """Extract Professional Summary / Objective section."""
    patterns = [
        r"(?:PROFESSIONAL\s+SUMMARY|OBJECTIVE|ABOUT\s+ME|PROFILE)\s*\n([\s\S]{50,600}?)(?:\n[A-Z]{3,}|\Z)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            summary = m.group(1).strip()
            # Clean bullet chars
            summary = re.sub(r"^[•\-\*\uf0b7]\s*", "", summary, flags=re.MULTILINE)
            return " ".join(summary.split())[:600]
    # Fallback: first 400 chars after contact line
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "@" in line and i < 10:
            block = " ".join(lines[i+1:i+8])
            cleaned = re.sub(r"[•\-\*\uf0b7]", " ", block).strip()
            return " ".join(cleaned.split())[:500]
    return ""


def _extract_skills(text: str) -> List[str]:
    """Extract skills from the TECHNICAL SKILLS section."""
    # Find skills section
    skill_match = re.search(
        r"(?:TECHNICAL\s+SKILLS?|SKILLS?|CORE\s+COMPETENCIES?)\s*\n([\s\S]{20,800}?)(?:\n[A-Z]{3,}|\Z)",
        text, re.IGNORECASE
    )
    raw = skill_match.group(1) if skill_match else text[:800]

    # Extract individual skill tokens
    # Remove category labels like "Programming Languages:", "Backend Frameworks:"
    raw = re.sub(r"[A-Za-z &/]+:\s*", " ", raw)
    # Remove bullet chars (including Unicode/special chars like 🔷, •, -, *, \uf0b7)
    raw = re.sub(r"[•\-\*\uf0b7\U0001F300-\U0001F9FF\U00002700-\U000027BF]", ",", raw)
    # Remove any remaining non-ASCII non-alphanumeric chars that aren't tech symbols
    raw = re.sub(r"[^\x00-\x7F,\n|/#+.]", " ", raw)

    tokens = re.split(r"[,\n|/]", raw)
    skills = []
    seen = set()
    for tok in tokens:
        tok = tok.strip().strip("()")
        # Keep tokens that look like a technology name (2-40 chars, letters/dots/+#)
        if 2 <= len(tok) <= 40 and re.search(r"[A-Za-z]", tok):
            clean = tok.strip()
            if clean.lower() not in seen and not any(
                k in clean.lower() for k in ["language", "framework", "database", "tool", "automation"]
            ):
                skills.append(clean)
                seen.add(clean.lower())

    return skills[:30]  # cap at 30 skills


def _extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education entries: degree, institution, year, CGPA."""
    edu_section_match = re.search(
        r"EDUCATION\s*\n([\s\S]{20,600}?)(?:\n[A-Z]{4,}|\Z)",
        text, re.IGNORECASE
    )
    if not edu_section_match:
        return []

    edu_text = edu_section_match.group(1)
    entries = []

    # CGPA / GPA / Percentage
    cgpa_match = re.search(r"(?:CGPA|GPA|CPI|Percentage)[:\s]*([\d.]+\s*(?:/\s*[\d.]+)?%?)", edu_text, re.IGNORECASE)
    cgpa = cgpa_match.group(1).strip() if cgpa_match else ""

    # Year range
    year_match = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2}|Present|current)", edu_text, re.IGNORECASE)
    year = f"{year_match.group(1)}–{year_match.group(2)}" if year_match else ""

    # Degree
    degree_patterns = [
        r"(Bachelor['\s]s?\s+of\s+[\w\s&/]+?)(?:\s*\n|\s*\||\s*,)",
        r"(B\.?Tech\.?|BE|B\.E\.?|B\.Sc\.?|M\.Tech\.?|ME|MCA|MBA)[\w\s&/,]*",
        r"(Bachelor|Master|Associate|Ph\.?D\.?)[\w\s&/,]+(?:Technology|Science|Engineering|Arts|Commerce)",
    ]
    degree = ""
    for dp in degree_patterns:
        dm = re.search(dp, edu_text, re.IGNORECASE)
        if dm:
            degree = dm.group(0).strip()
            break

    # Institution
    # Usually the line after the degree line or a standalone proper-noun line
    lines = [l.strip() for l in edu_text.split("\n") if l.strip()]
    institution = ""
    for line in lines:
        if any(k in line.lower() for k in ["university", "college", "institute", "school", "iit", "nit", "bits"]):
            institution = line
            break

    if degree or institution:
        entries.append({
            "degree": degree,
            "institution": institution,
            "year": year,
            "cgpa": cgpa,
        })

    # Coursework
    coursework_match = re.search(r"(?:Relevant\s+Coursework|Coursework)[:\s]*([\w\s,&]+)", edu_text, re.IGNORECASE)
    if coursework_match and entries:
        entries[0]["coursework"] = coursework_match.group(1).strip()

    return entries


def _extract_experience_and_projects(text: str) -> List[Dict[str, str]]:
    """Extract project and work experience entries."""
    section_match = re.search(
        r"(?:PROJECTS?\s*&?\s*EXPERIENCE|WORK\s+EXPERIENCE|EXPERIENCE|PROJECTS?)\s*\n([\s\S]{50,1500}?)(?:\n[A-Z]{4,}|\Z)",
        text, re.IGNORECASE
    )
    if not section_match:
        return []

    section_text = section_match.group(1)
    entries = []

    # Split into individual project/role blocks by detecting title lines
    # (lines with tech stack in parentheses or bold-like capitalization)
    blocks = re.split(r"\n(?=[A-Z][A-Za-z\s\-&]+ \()", section_text)
    if len(blocks) == 1:
        # Fallback: split by double newline
        blocks = section_text.split("\n\n")

    for block in blocks:
        block = block.strip()
        if len(block) < 20:
            continue

        # Title line (first line of block)
        title_line = block.split("\n")[0].strip()

        # Extract tech stack from parentheses
        tech_match = re.search(r"\(([^)]+)\)", title_line)
        tech_stack = tech_match.group(1) if tech_match else ""

        # Clean title
        title = re.sub(r"\s*\([^)]+\)", "", title_line).strip()

        # Bullet points = description
        bullets = re.findall(r"[•\-\*\uf0b7]\s*(.+)", block)
        description = ". ".join(b.strip() for b in bullets[:4]) if bullets else ""

        if title:
            entries.append({
                "title": title,
                "tech": tech_stack,
                "description": description,
            })

    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Public: Full Candidate Profile
# ──────────────────────────────────────────────────────────────────────────────

def get_candidate_profile_from_resume(file_path: str) -> Dict[str, Any]:
    """
    Full candidate profile extracted from resume PDF.
    Returns everything a job application form could ask for:
      name, email, phone, github, linkedin, location, summary,
      skills (list), education (list), experience/projects (list),
      degree, institution, cgpa, year_of_graduation.
    Falls back gracefully to settings or hardcoded defaults.
    """

    # ── Defaults from settings ────────────────────────────────────────────────
    profile: Dict[str, Any] = {
        "name": "Manthan Raut",
        "first_name": "Manthan",
        "last_name": "Raut",
        "email": "manthanr141@gmail.com",
        "phone": "+919529883808",
        "github": "https://github.com/Manthanraut13",
        "linkedin": "https://linkedin.com/in/manthan-raut",
        "location": "India",
        "summary": (
            "Enthusiastic Software Engineer with expertise in Python, Full Stack Web Development, "
            "REST APIs, and AI/LLM Application Development. Experienced in FastAPI, React, "
            "PostgreSQL, LangChain, and browser automation."
        ),
        "skills": ["Python", "FastAPI", "React", "SQL", "PostgreSQL", "Docker", "Git",
                   "LangChain", "OpenAI API", "Playwright", "JavaScript", "TypeScript"],
        "education": [],
        "experience": [],
        "degree": "Bachelor of Technology in Computer Science",
        "institution": "",
        "cgpa": "",
        "year_of_graduation": "",
        "years_of_experience": "1",
        "notice_period": "Immediately",
        "expected_salary": "Negotiable",
        "work_authorization": "Yes",
        "requires_sponsorship": "No",
        "resume_pdf": os.path.abspath(file_path) if file_path and os.path.exists(file_path) else "",
    }

    # Override with settings values
    try:
        from config.settings import settings
        if settings.candidate_name:
            profile["name"] = settings.candidate_name
        if settings.candidate_email:
            profile["email"] = settings.candidate_email
        if settings.candidate_phone:
            profile["phone"] = settings.candidate_phone
        if settings.candidate_github:
            profile["github"] = settings.candidate_github
        if settings.candidate_linkedin:
            profile["linkedin"] = settings.candidate_linkedin
    except Exception:
        pass

    parts = profile["name"].split()
    profile["first_name"] = parts[0]
    profile["last_name"] = parts[-1] if len(parts) > 1 else ""

    # ── Parse PDF ─────────────────────────────────────────────────────────────
    if not (file_path and os.path.exists(file_path)):
        return profile

    try:
        ext = file_path.lower().rsplit(".", 1)[-1]
        raw_text = extract_text_from_pdf(file_path) if ext == "pdf" else extract_text_from_txt(file_path)

        # Contact info
        email = _extract_email(raw_text)
        if email:
            profile["email"] = email

        phone = _extract_phone(raw_text)
        if phone:
            profile["phone"] = phone

        github = _extract_github(raw_text)
        if github:
            profile["github"] = github

        linkedin = _extract_linkedin(raw_text)
        if linkedin:
            profile["linkedin"] = linkedin

        name = _extract_name(raw_text)
        if name:
            profile["name"] = name
            parts = name.split()
            profile["first_name"] = parts[0]
            profile["last_name"] = parts[-1] if len(parts) > 1 else ""

        location = _extract_location(raw_text)
        if location:
            profile["location"] = location

        summary = _extract_summary(raw_text)
        if summary:
            profile["summary"] = summary

        skills = _extract_skills(raw_text)
        if skills:
            profile["skills"] = skills

        education = _extract_education(raw_text)
        if education:
            profile["education"] = education
            edu = education[0]
            if edu.get("degree"):
                profile["degree"] = edu["degree"]
            if edu.get("institution"):
                profile["institution"] = edu["institution"]
            if edu.get("cgpa"):
                profile["cgpa"] = edu["cgpa"]
            if edu.get("year"):
                profile["year_of_graduation"] = edu["year"]

        experience = _extract_experience_and_projects(raw_text)
        if experience:
            profile["experience"] = experience

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Resume parse partial failure: {e}")

    return profile


# ──────────────────────────────────────────────────────────────────────────────
# Legacy helpers (used by run_pipeline.py)
# ──────────────────────────────────────────────────────────────────────────────

def parse_resume(file_path: str) -> Dict[str, Any]:
    """Reads a resume file and returns segmented sections + raw_text."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")
    ext = file_path.lower().rsplit(".", 1)[-1]
    raw_text = extract_text_from_pdf(file_path) if ext == "pdf" else extract_text_from_txt(file_path)
    segmented = segment_resume_text(raw_text)
    segmented["raw_text"] = raw_text
    return segmented


def segment_resume_text(raw_text: str) -> Dict[str, List[str]]:
    """Chunks raw text into predefined sections using regex headers."""
    structured: Dict[str, List[str]] = {
        "skills": [], "experience": [], "education": [], "projects": []
    }
    headers_regex = {
        "skills":     r"^(?:skills?|technical skills?|core competencies)\b",
        "experience": r"^(?:experience|work experience|employment|professional experience|projects? & experience)\b",
        "education":  r"^(?:education|academic background|academics)\b",
        "projects":   r"^(?:projects?|personal projects?|academic projects?)\b",
    }
    current_section = None
    for line in raw_text.split("\n"):
        cleaned = line.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        matched = None
        for key, pattern in headers_regex.items():
            if re.search(pattern, lower):
                matched = key
                break
        if matched:
            current_section = matched
            continue
        if current_section:
            structured[current_section].append(cleaned)

    for key in structured:
        structured[key] = [i for i in structured[key] if i.strip()]
    return structured


def get_search_queries_from_resume(file_path: str, max_queries: int = 6) -> List[str]:
    """
    Dynamically generates relevant internship/job search queries based on the candidate's
    resume skills, projects, and professional background.

    Examples:
      - 'Software Engineer Intern'
      - 'Python Developer Intern'
      - 'Full Stack Developer Intern'
      - 'AI ML Intern'
      - 'Backend Developer Intern'
    """
    profile = get_candidate_profile_from_resume(file_path)
    skills = [s.lower() for s in profile.get("skills", [])]
    summary = profile.get("summary", "").lower()
    exp_titles = [e.get("title", "").lower() for e in profile.get("experience", [])]
    
    all_context = f"{' '.join(skills)} {summary} {' '.join(exp_titles)}"

    queries: List[str] = []

    def _add_query(q: str):
        if q not in queries:
            queries.append(q)

    # Core high-level titles
    _add_query("Software Engineer Intern")

    # Skill-based dynamic titles
    if any(k in all_context for k in ["python", "django", "fastapi", "flask"]):
        _add_query("Python Developer Intern")
        _add_query("Backend Developer Intern")

    if any(k in all_context for k in ["react", "javascript", "typescript", "frontend", "full stack", "fullstack"]):
        _add_query("Full Stack Developer Intern")

    if any(k in all_context for k in ["ai", "llm", "machine learning", "ml", "langchain", "deep learning", "nlp"]):
        _add_query("AI ML Intern")
        _add_query("Machine Learning Intern")

    if any(k in all_context for k in ["data", "sql", "analytics", "postgresql"]):
        _add_query("Data Science Intern")

    if any(k in all_context for k in ["devops", "docker", "cloud", "aws", "linux"]):
        _add_query("Cloud DevOps Intern")

    # Always ensure at least 3 relevant queries
    if len(queries) < 3:
        _add_query("Software Developer Intern")
        _add_query("Web Developer Intern")

    return queries[:max_queries]

