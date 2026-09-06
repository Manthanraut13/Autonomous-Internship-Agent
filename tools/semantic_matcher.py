"""
tools/semantic_matcher.py
-------------------------
Embedding-based semantic matching engine for resume-to-JD comparison.

Architecture:
  1. Chunks the resume into semantic sections (summary, skills, experience, projects, education)
  2. For long sections (> 800 chars), creates overlapping sub-chunks (window=800, overlap=100)
  3. Generates embeddings for every sub-chunk using sentence-transformers (all-MiniLM-L6-v2)
  4. For each job description, computes cosine similarity against all sub-chunks
  5. Scores each section using MAX pooling across its sub-chunks (best match, not average)
  6. Returns a weighted semantic score (0-100)

BUG-9 FIXED:
  Old code truncated BOTH resume chunks and job descriptions to 512 characters
  before encoding, cutting off most of the content in long Skills/Projects sections.
  Fix: no manual pre-truncation. sentence-transformers handles tokenization internally.
  For very long sections, use sliding-window sub-chunking so all content is embedded.

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
# Sliding-window sub-chunking
# BUG-9 FIX: replaces hard [:512] truncation
# ──────────────────────────────────────────────────────────────────────────────

# all-MiniLM-L6-v2 processes ~256 WordPiece tokens (~800-1000 chars of English text).
# We window at 800 chars with 100-char overlap to preserve boundary context.
_SUBCHUNK_WINDOW = 800
_SUBCHUNK_OVERLAP = 100


def _make_sub_chunks(section: str, text: str) -> List[Dict[str, str]]:
    """
    Splits a section's text into overlapping sub-chunks if it exceeds the window size.
    Short texts are returned as a single chunk.
    Each sub-chunk retains its parent section label.
    """
    if len(text) <= _SUBCHUNK_WINDOW:
        return [{"section": section, "text": text}]

    sub_chunks = []
    start = 0
    while start < len(text):
        end = min(start + _SUBCHUNK_WINDOW, len(text))
        sub_chunks.append({"section": section, "text": text[start:end]})
        if end == len(text):
            break
        start += (_SUBCHUNK_WINDOW - _SUBCHUNK_OVERLAP)
    return sub_chunks


# ──────────────────────────────────────────────────────────────────────────────
# Resume Chunking
# ──────────────────────────────────────────────────────────────────────────────

def _chunk_resume_text(raw_text: str) -> List[Dict[str, str]]:
    """
    Splits resume text into semantic sections.
    Returns list of {"section": <label>, "text": <content>} dicts.
    Long sections are further split into overlapping sub-chunks.
    """
    section_patterns = {
        "summary": r"(?:SUMMARY|OBJECTIVE|ABOUT\s+ME|PROFILE)\b",
        "skills": r"(?:TECHNICAL\s+SKILLS?|SKILLS?|CORE\s+COMPETENCIES?)\b",
        "experience": r"(?:EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT)\b",
        "projects": r"(?:SELECTED\s+PROJECTS?|PROJECTS?|PERSONAL\s+PROJECTS?)\b",
        "education": r"(?:EDUCATION|ACADEMIC|ACADEMICS)\b",
    }

    # First pass: split raw text into sections
    sections: List[Dict[str, str]] = []
    lines = raw_text.split("\n")
    current_section = "summary"
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched_section = None
        for sec_name, pattern in section_patterns.items():
            if re.search(pattern, stripped, re.IGNORECASE) and len(stripped) < 60:
                matched_section = sec_name
                break

        if matched_section:
            if current_lines:
                text = " ".join(current_lines).strip()
                if len(text) > 20:
                    sections.append({"section": current_section, "text": text})
            current_section = matched_section
            current_lines = []
        else:
            current_lines.append(stripped)

    # Save last section
    if current_lines:
        text = " ".join(current_lines).strip()
        if len(text) > 20:
            sections.append({"section": current_section, "text": text})

    # If no sections found, treat entire text as summary
    if not sections:
        sections.append({"section": "summary", "text": raw_text})

    # Second pass: apply sliding-window sub-chunking to long sections
    all_sub_chunks: List[Dict[str, str]] = []
    for sec in sections:
        all_sub_chunks.extend(_make_sub_chunks(sec["section"], sec["text"]))

    return all_sub_chunks


# ──────────────────────────────────────────────────────────────────────────────
# ResumeEmbedder — compute once, match many
# ──────────────────────────────────────────────────────────────────────────────

# Section weights for final score computation
SECTION_WEIGHTS = {
    "skills":     0.40,
    "experience": 0.25,
    "projects":   0.20,
    "summary":    0.10,
    "education":  0.05,
}


class ResumeEmbedder:
    """
    Pre-computes resume section embeddings once.
    Call compute_semantic_score(jd_text) for each job description.

    BUG-9 FIX applied:
    - Resume sub-chunks are embedded WITHOUT [:512] truncation.
    - sentence-transformers handles tokenization internally (256-token limit
      per call, which covers ~800 chars of English text naturally).
    - Job description is embedded in full (no pre-truncation) — sentence-transformers
      internally truncates to its token limit.
    - Scoring uses MAX pooling per section (best sub-chunk match wins),
      not averaging of truncated averages.
    """

    def __init__(self, resume_path: str):
        from tools.resume_parser import extract_text_from_pdf

        self.resume_path = resume_path
        raw_text = extract_text_from_pdf(resume_path)
        self.chunks = _chunk_resume_text(raw_text)

        model = _get_model()
        self.chunk_embeddings: List[Dict[str, Any]] = []

        for chunk in self.chunks:
            # BUG-9 FIX: NO [:512] truncation — pass full sub-chunk text
            embedding = model.encode(chunk["text"], convert_to_numpy=True)
            self.chunk_embeddings.append({
                "section": chunk["section"],
                "text": chunk["text"],
                "embedding": embedding,
            })

        unique_sections = set(c["section"] for c in self.chunks)
        logger.info(
            f"ResumeEmbedder initialized: {len(self.chunks)} sub-chunks from "
            f"sections: {', '.join(sorted(unique_sections))}"
        )

    def compute_semantic_score(self, job_description: str) -> float:
        """
        Computes weighted cosine similarity between job description and resume sub-chunks.
        Uses MAX pooling per section (best sub-chunk match, not average of truncated chunks).
        Returns score 0-100.

        BUG-9 FIX: job_description is NOT pre-truncated to 512 chars.
        """
        if not job_description or len(job_description.strip()) < 20:
            return 0.0

        model = _get_model()
        # BUG-9 FIX: no [:512] truncation on job description
        jd_embedding = model.encode(job_description, convert_to_numpy=True)

        # Collect per-sub-chunk similarities, grouped by section
        section_sims: Dict[str, List[float]] = {}
        for chunk_data in self.chunk_embeddings:
            section = chunk_data["section"]
            sim = _cosine_similarity(jd_embedding, chunk_data["embedding"])
            section_sims.setdefault(section, []).append(sim)

        # MAX pooling: take the BEST sub-chunk match per section
        # (A long Skills section split into 3 sub-chunks → score = best of 3)
        section_max_sim: Dict[str, float] = {
            sec: max(sims) for sec, sims in section_sims.items()
        }

        # Weighted sum across sections
        weighted_score = 0.0
        total_weight = 0.0
        for section, weight in SECTION_WEIGHTS.items():
            if section in section_max_sim:
                weighted_score += section_max_sim[section] * weight
                total_weight += weight

        # Normalize if not all sections were present
        if total_weight > 0:
            weighted_score /= total_weight

        # Map cosine similarity range (0.15–0.70) → 0–100 score
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

    # Sources that are inherently internship/fellowship programs
    internship_sources = {"mlh", "gsoc", "outreachy", "internshala", "pittcsc", "simplifyjobs"}
    if source in internship_sources:
        return "internship"

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

    intern_score = sum(1 for kw in internship_keywords if kw in combined)
    ft_score = sum(1 for kw in fulltime_keywords if kw in combined)

    if intern_score > ft_score:
        return "internship"
    elif ft_score > intern_score:
        return "full-time"

    # Default: entry-level clues
    if "entry" in combined or "junior" in combined or "associate" in combined:
        return "internship"

    # Default to internship since the agent targets internships
    return "internship"
