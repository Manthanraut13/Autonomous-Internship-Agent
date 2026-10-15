"""
Tests for the role guardrails (spec: internships only, targeted AI families only)
in tools/job_api.py, plus the internship-first precedence of
classify_role_type() in tools/semantic_matcher.py and the word-boundary fix in
_matches_query() (term "ai" must never substring-match "detail"/"maintain").

Everything here is pure regex/classification logic — no network, no keys.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.job_api as ja
from tools.semantic_matcher import classify_role_type


# ── is_internship_title ───────────────────────────────────────────────────────

@pytest.mark.parametrize("title", [
    "AI Engineer Intern",
    "Machine Learning Internship",
    "GenAI Developer Co-op",
    "AI Automation Trainee",
    "AI Generalist - Fellowship",
    "Working Student - AI Tools",
])
def test_internship_titles_pass(title):
    assert ja.is_internship_title(title)


@pytest.mark.parametrize("title", [
    "International Sales Manager",   # must NOT match "intern"
    "Internal Audit Analyst",        # must NOT match "intern"
    "Senior AI Engineer",
    "Full Time AI Consultant",
    "",
])
def test_non_internship_titles_rejected(title):
    assert not ja.is_internship_title(title)


# ── is_ai_role (the five targeted families) ──────────────────────────────────

@pytest.mark.parametrize("title", [
    "AI Engineer Intern",
    "GenAI Developer Intern",
    "AI Generalist Intern",
    "AI Consultant Intern",
    "AI Automation Specialist",
    "Machine Learning Intern",
    "LLM Engineering Intern",
    "Agentic AI Intern",
])
def test_ai_family_titles_pass(title):
    assert ja.is_ai_role(title)


def test_generic_title_with_ai_body_passes():
    assert ja.is_ai_role("Software Engineer Intern",
                         "Build LLM agents in Python with LangChain.")


@pytest.mark.parametrize("title,desc", [
    # "ai" as substring must never match: detail/maintain/retail
    ("Sales Executive", "Detail-oriented retail role with email outreach."),
    ("Software Engineer Intern", "Maintain retail POS systems and detail invoices."),
    ("Data Analyst Intern", "Build dashboards in SQL and Excel; reporting only."),
    ("Frontend Intern", "Write HTML/CSS for the marketing site."),
])
def test_non_ai_roles_rejected(title, desc):
    assert not ja.is_ai_role(title, desc)


# ── classify_role_type precedence + query matching ────────────────────────────

def test_internship_outranks_contract():
    # 'AI Consultant Intern' contains the contract keyword "consultant";
    # the declared internship must still win.
    assert classify_role_type(
        {"title": "AI Consultant Intern", "description": "consulting engagements"}) == "internship"
    assert classify_role_type(
        {"title": "Data Engineer", "description": "contract role, 6 months"}) == "contract"


def test_matches_query_uses_word_boundaries():
    assert not ja._matches_query("maintain detail email", ["ai"])
    assert ja._matches_query("AI Engineer Intern", ["ai", "engineer"])
    assert ja._matches_query("GenAI Developer", ["genai"])
