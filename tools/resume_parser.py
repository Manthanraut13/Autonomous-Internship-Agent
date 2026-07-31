"""
tools/resume_parser.py
----------------------
Parses a resume (PDF or TXT) and extracts key sections using simple
heuristic string matching.

Returns a structured dictionary:
{
    "skills": [...],
    "experience": [...],
    "education": [...],
    "projects": [...]
}
"""

import os
import re
from typing import Dict, List

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
        except Exception as e:
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
        except Exception as e:
            pass

    if not text.strip():
        raise ValueError(f"Could not extract text from PDF: {file_path}")

    return text


def extract_text_from_txt(file_path: str) -> str:
    """Extracts raw text from a TXT file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def parse_resume(file_path: str) -> Dict[str, List[str]]:
    """
    Reads a resume (PDF or TXT), extracts its text, and heuristically
    chunks it into skills, experience, education, and projects.
    
    Args:
        file_path (str): The absolute or relative path to the resume file.
        
    Returns:
        Dict[str, List[str]]: Structured data containing sections.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found at: {file_path}")

    ext = file_path.lower().split('.')[-1]
    
    if ext == "pdf":
        raw_text = extract_text_from_pdf(file_path)
    elif ext == "txt":
        raw_text = extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Please provide a .pdf or .txt file.")

    return segment_resume_text(raw_text)


def segment_resume_text(raw_text: str) -> Dict[str, List[str]]:
    """
    Chunks raw text into predefined sections using regex headers.
    """
    # Structure we want to return
    structured_data: Dict[str, List[str]] = {
        "skills": [],
        "experience": [],
        "education": [],
        "projects": []
    }

    # Common section header synonyms
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

        # Check if the line matches any known header
        lower_line = cleaned_line.lower()
        matched_header = None
        
        for section_key, regex_pattern in headers_regex.items():
            if re.search(regex_pattern, lower_line):
                matched_header = section_key
                break
        
        if matched_header:
            current_section = matched_header
            continue
            
        # If we are under a recognised section, append the line
        if current_section:
            structured_data[current_section].append(cleaned_line)

    # Some basic cleanup (remove empty strings if any crept in)
    for key in structured_data:
        structured_data[key] = [item for item in structured_data[key] if item.strip()]

    return structured_data
