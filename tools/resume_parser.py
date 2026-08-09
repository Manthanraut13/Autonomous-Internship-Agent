"""
tools/resume_parser.py
----------------------
Parses a resume (PDF or TXT) and extracts raw text, candidate contact profile,
and section chunks (skills, experience, education, projects).
"""

import os
import re
from typing import Dict, List, Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


def extract_text_from_pdf(file_path: str) -> str:
    """Extracts raw text from a PDF file using PyMuPDF (fitz) or PyPDF2 as fallback."""
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
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                return text
        except Exception:
            pass

    if not text.strip():
        raise ValueError(f"Could not extract text from PDF: {file_path}")

    return text


def extract_text_from_txt(file_path: str) -> str:
    """Extracts raw text from a TXT file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def get_candidate_profile_from_resume(file_path: str) -> Dict[str, Any]:
    """
    Parses candidate profile dynamically from resume PDF or TXT.
    Falls back to settings if regex extraction misses a field.
    """
    profile = {
        "name": "Manthan Raut",
        "first_name": "Manthan",
        "last_name": "Raut",
        "email": "manthanr141@gmail.com",
        "phone": "+919529883808",
        "github": "https://github.com/Manthanraut13",
        "linkedin": "https://linkedin.com/in/manthan-raut",
        "location": "India",
        "summary": "Software Engineer & AI Application Developer specializing in Python, FastAPI, React, and LLMs.",
        "skills": ["Python", "FastAPI", "React", "SQL", "PostgreSQL", "Docker", "Git", "AI/LLM"],
        "resume_pdf": os.path.abspath(file_path) if file_path and os.path.exists(file_path) else "",
    }

    try:
        from config.settings import settings
        profile["name"] = settings.candidate_name or profile["name"]
        profile["email"] = settings.candidate_email or profile["email"]
        profile["phone"] = settings.candidate_phone or profile["phone"]
        profile["github"] = settings.candidate_github or profile["github"]
        profile["linkedin"] = settings.candidate_linkedin or profile["linkedin"]

        parts = profile["name"].split()
        profile["first_name"] = parts[0]
        profile["last_name"] = parts[-1] if len(parts) > 1 else ""
    except Exception:
        pass

    if file_path and os.path.exists(file_path):
        try:
            ext = file_path.lower().split(".")[-1]
            raw_text = extract_text_from_pdf(file_path) if ext == "pdf" else extract_text_from_txt(file_path)

            # Email extraction
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw_text)
            if emails:
                profile["email"] = emails[0]

            # Phone extraction
            phones = re.findall(r"\+?\d[\d\s\-()]{8,}\d", raw_text)
            if phones:
                profile["phone"] = phones[0].strip()

            # Name from top line
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if lines and len(lines[0].split()) <= 4:
                top_line = lines[0]
                if not any(k in top_line.lower() for k in ["resume", "curriculum", "email", "phone"]):
                    profile["name"] = top_line
                    p_parts = top_line.split()
                    profile["first_name"] = p_parts[0]
                    profile["last_name"] = p_parts[-1] if len(p_parts) > 1 else ""

            profile["summary"] = raw_text[:500]
        except Exception:
            pass

    return profile


def parse_resume(file_path: str) -> Dict[str, Any]:
    """
    Reads a resume (PDF or TXT), extracts its text, and heuristically
    chunks it into skills, experience, education, and projects.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found at: {file_path}")

    ext = file_path.lower().split('.')[-1]
    raw_text = extract_text_from_pdf(file_path) if ext == "pdf" else extract_text_from_txt(file_path)
    segmented = segment_resume_text(raw_text)
    segmented["raw_text"] = raw_text
    return segmented


def segment_resume_text(raw_text: str) -> Dict[str, List[str]]:
    """Chunks raw text into predefined sections using regex headers."""
    structured_data: Dict[str, List[str]] = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": []
    }

    headers_regex = {
        "skills": r"^(?:skills|technical skills|core competencies)\b",
        "experience": r"^(?:experience|work experience|employment history|professional experience)\b",
        "education": r"^(?:education|academic background|academics)\b",
        "projects": r"^(?:projects|personal projects|academic projects)\b"
    }

    current_section = None
    lines = raw_text.split('\n')

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        lower_line = cleaned_line.lower()
        matched_header = None

        for section_key, regex_pattern in headers_regex.items():
            if re.search(regex_pattern, lower_line):
                matched_header = section_key
                break

        if matched_header:
            current_section = matched_header
            continue

        if current_section:
            structured_data[current_section].append(cleaned_line)

    for key in structured_data:
        structured_data[key] = [item for item in structured_data[key] if item.strip()]

    return structured_data
