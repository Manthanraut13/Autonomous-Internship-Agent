"""
tools/semantic_matcher.py
-------------------------
Embedding-based semantic matching engine for resume-to-JD comparison.

Architecture:
  1. Chunks the resume into semantic sections (summary, skills, experience, projects, education)
  2. Generates embeddings once using sentence-transformers (all-MiniLM-L6-v2)
  3. For each job description, computes cosine similarity against resume chunks
  4. Returns a weighted semantic score (0-100)

Also provides role type classification (internship vs full-time).
"""

import re
import logging
from typing import List, Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid import-time overhead
_model = None


def _get_model():
    """Lazy-load the sentence-transformers model (first call downloads ~80MB)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: all-MiniLM-L6-v2 ...")
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ──────────────────────────────────────────────────────────────────────────────
# Resume Chunking
# ──────────────────────────────────────────────────────────────────────────────

def _chunk_resume_text(raw_text: str) -> List[Dict[str, str]]:
    """
    Splits resume text into semantic sections.
    Returns list of {"section": <label>, "text": <content>} dicts.
    """
    section_patterns = {
        "summary": r"(?:SUMMARY|OBJECTIVE|ABOUT\s+ME|PROFILE)\b",
        "skills": r"(?:TECHNICAL\s+SKILLS?|SKILLS?|CORE\s+COMPETENCIES?)\b",
        "experience": r"(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT)\b",
        "projects": r"(?:SELECTED\s+PROJECTS?|PROJECTS?|PERSONAL\s+PROJECTS?)\b",
        "education": r"(?:EDUCATION|ACADEMIC|ACADEMICS)\b",
    }

    chunks: List[Dict[str, str]] = []
    lines = raw_text.split("\n")
    current_section = "summary"  # Default: everything before first header is summary
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line is a section header
        matched_section = None
        for sec_name, pattern in section_patterns.items():
            if re.search(pattern, stripped, re.IGNORECASE) and len(stripped) < 60:
                matched_section = sec_name
                break

        if matched_section:
            # Save previous section
            if current_lines:
                text = " ".join(current_lines).strip()
                if len(text) > 20:
                    chunks.append({"section": current_section, "text": text})
            current_section = matched_section
            current_lines = []
        else:
            current_lines.append(stripped)

    # Save last section
    if current_lines:
        text = " ".join(current_lines).strip()
        if len(text) > 20:
            chunks.append({"section": current_section, "text": text})

    # If no sections found, treat entire text as one chunk
    if not chunks:
        chunks.append({"section": "summary", "text": raw_text[:2000]})

    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# ResumeEmbedder — compute once, match many
# ──────────────────────────────────────────────────────────────────────────────

# Section weights for final score computation
SECTION_WEIGHTS = {
    "skills": 0.40,
    "experience": 0.25,
    "projects": 0.20,
    "summary": 0.10,
    "education": 0.05,
}


class ResumeEmbedder:
    """
    Pre-computes resume section embeddings once.
    Call compute_semantic_score(jd_text) for each job description.
    """

    def __init__(self, resume_path: str):
        from tools.resume_parser import extract_text_from_pdf

        self.resume_path = resume_path
        raw_text = extract_text_from_pdf(resume_path)
        self.chunks = _chunk_resume_text(raw_text)

        model = _get_model()
        self.chunk_embeddings: List[Dict[str, Any]] = []

        for chunk in self.chunks:
            embedding = model.encode(chunk["text"][:512], convert_to_numpy=True)
            self.chunk_embeddings.append({
                "section": chunk["section"],
                "text": chunk["text"],
                "embedding": embedding,
            })

        logger.info(
            f"ResumeEmbedder initialized: {len(self.chunks)} chunks from "
            f"{', '.join(set(c['section'] for c in self.chunks))}"
        )

    def compute_semantic_score(self, job_description: str) -> float:
        """
        Computes weighted cosine similarity between job description and resume chunks.
        Returns score 0-100.
        """
        if not job_description or len(job_description.strip()) < 20:
            return 0.0

        model = _get_model()
        jd_embedding = model.encode(job_description[:512], convert_to_numpy=True)

        section_scores: Dict[str, List[float]] = {}
        for chunk_data in self.chunk_embeddings:
            section = chunk_data["section"]
            sim = _cosine_similarity(jd_embedding, chunk_data["embedding"])
            section_scores.setdefault(section, []).append(sim)

        # Average similarity per section, then weighted sum
        weighted_score = 0.0
        total_weight = 0.0

        for section, weight in SECTION_WEIGHTS.items():
            if section in section_scores:
                avg_sim = sum(section_scores[section]) / len(section_scores[section])
                weighted_score += avg_sim * weight
                total_weight += weight

        # Normalize if not all sections were present
        if total_weight > 0:
            weighted_score /= total_weight

        # Convert to 0-100 scale (cosine similarity for these models typically ranges 0.1-0.8)
        # Map 0.2-0.7 range to 20-95 for more usable scores
        normalized = max(0.0, min(1.0, (weighted_score - 0.15) / 0.55))
        return round(normalized * 100, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Role Type Classifier
# ──────────────────────────────────────────────────────────────────────────────

def classify_role_type(job: Dict[str, Any]) -> str:
    """
    Classifies a job as 'internship' or 'full-time' based on title and description.
    """
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    source = (job.get("source") or "").lower()
    combined = f"{title} {desc}"

    # Strong internship signals
    internship_keywords = [
        "intern", "internship", "co-op", "coop", "trainee",
        "fellow", "fellowship", "apprentice", "apprenticeship",
        "student", "graduate program", "graduate trainee",
        "summer program", "summer associate", "working student",
    ]

    # Strong full-time signals
    fulltime_keywords = [
        "full-time", "full time", "permanent", "regular position",
        "senior", "lead", "staff", "principal", "director",
        "5+ years", "8+ years", "10+ years", "3+ years",
        "mid-level", "experienced professional",
    ]

    # Sources that are inherently internship/fellowship programs
    internship_sources = {"mlh", "gsoc", "outreachy", "levelsfyi"}

    if source in internship_sources:
        return "internship"

    intern_score = sum(1 for kw in internship_keywords if kw in combined)
    ft_score = sum(1 for kw in fulltime_keywords if kw in combined)

    if intern_score > ft_score:
        return "internship"
    elif ft_score > intern_score:
        return "full-time"

    # Default: if title is short and ambiguous, check for entry-level clues
    if "entry" in combined or "junior" in combined or "associate" in combined:
        return "internship"

    return "internship"  # Default for ambiguous roles (user wants internships)
