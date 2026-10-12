"""
Tests for is_explicit_tech_job in tools/semantic_matcher.py (issue: dead
substring pre-filter).

The old gate used `k in text`, so "ai" matched "email", "available" and
"maintain", and "intern" matched "international" — practically every listing
was "explicit tech" and the semantic pre-filter never ran. The fix anchors
every keyword with word boundaries; these tests pin both directions: the old
false positives must now be rejected, and legitimate tech phrasings (including
plural/gerund forms the old substring covered) must still pass.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.semantic_matcher import is_explicit_tech_job


# ── The core bug: substring false positives must be gone ─────────────────────

def test_ai_substring_in_email_does_not_match():
    assert not is_explicit_tech_job("Office Coordinator", "Manage the shared email inbox and calendars")


def test_ai_substring_in_available_does_not_match():
    assert not is_explicit_tech_job("Retail Associate", "Weekend shifts available, staff discounts included")


def test_ai_substring_in_maintain_does_not_match():
    assert not is_explicit_tech_job("Facilities Technician", "Maintain building systems and equipment")


def test_ml_substring_in_html_does_not_match():
    assert not is_explicit_tech_job("Content Writer", "Write and edit html pages for the blog")


def test_intern_substring_in_international_does_not_match():
    assert not is_explicit_tech_job("International Sales Manager", "Grow enterprise accounts across EMEA")


# ── Legitimate tech listings must still pass (no coverage regression) ────────

def test_plain_ai_word_matches():
    assert is_explicit_tech_job("AI Engineer Intern", "Build ML pipelines")


def test_capitalized_ai_matches():
    assert is_explicit_tech_job("Software Engineer", "Work on our AI platform team")


def test_ai_hyphenated_matches():
    assert is_explicit_tech_job("Developer", "Build AI-powered agents for customers")


def test_ml_whole_word_matches_but_not_html():
    assert is_explicit_tech_job("Research Assistant", "Train ML models on multimodal data")


def test_python_matches():
    assert is_explicit_tech_job("Backend Intern", "Python services with FastAPI")


def test_llm_genai_nlp_match():
    assert is_explicit_tech_job("GenAI Intern", "Fine-tune LLMs; NLP experience is a plus")


def test_software_engineering_gerund_matches():
    # Old substring covered "software engineering"; keep that coverage.
    assert is_explicit_tech_job("Software Engineering Intern", "Rotational program")


def test_engineer_plural_and_gerund_match():
    assert is_explicit_tech_job("Deep Learning Engineer", "Deploy vision models")
    assert is_explicit_tech_job("Graduate", "Join our engineering rotation program")


def test_data_scientist_matches():
    # Old substring "data science" missed "data scientist"; the fix covers both.
    assert is_explicit_tech_job("Data Scientist Intern", "Experimentation and A/B testing")


def test_description_only_mention_matches():
    assert is_explicit_tech_job("Research Analyst", "Support teams deploying machine learning models in production")


# ── Non-tech roles must now be filterable ────────────────────────────────────

def test_hr_role_is_not_explicit_tech():
    assert not is_explicit_tech_job(
        "Senior HR Business Partner",
        "Drive talent strategy, employee engagement and performance management cycles."
    )


def test_sales_role_is_not_explicit_tech():
    assert not is_explicit_tech_job(
        "Sales Manager",
        "Own the CRM pipeline, quarterly quotas and territory planning for enterprise accounts."
    )


def test_empty_inputs_are_not_tech():
    assert not is_explicit_tech_job("", "")
    assert not is_explicit_tech_job(None, None)
