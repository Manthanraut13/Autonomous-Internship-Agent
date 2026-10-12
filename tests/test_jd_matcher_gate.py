"""
Tests for the LLM scoring gate in tools/jd_matcher.py (issue: fake precision).

match_resume_to_job must refuse to score listings whose description is still
shorter than MIN_LLM_DESCRIPTION_CHARS after enrichment — those descriptions
are synthetic one-liners built by the scrapers, and letting the LLM score them
produces fabricated match scores. Unscored listings return score=None
("apply link only") and never reach the Groq API.

All tests here exercise the gate path only (returns before any model is
constructed), so no network access or API key is needed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.jd_matcher import match_resume_to_job, MIN_LLM_DESCRIPTION_CHARS


def test_constant_is_400():
    assert MIN_LLM_DESCRIPTION_CHARS == 400


def test_empty_description_is_unscored():
    result = match_resume_to_job("Python developer with LangChain experience", "")
    assert result["score"] is None
    assert "Unscored" in result["reasoning"]
    assert "apply link" in result["reasoning"].lower()
    assert result["key_matches"] == []


def test_none_description_is_unscored():
    result = match_resume_to_job("Python developer with LangChain experience", None)
    assert result["score"] is None


def test_whitespace_only_is_unscored():
    assert match_resume_to_job("resume text", "   \n\t  ")["score"] is None


def test_typical_synthetic_one_liner_is_unscored():
    # The exact kind of scraper template that previously scored 94/100.
    synthetic = "AI Engineer position at Acme Corp. Location: Bengaluru. Apply now."
    result = match_resume_to_job("Python developer with LangChain experience", synthetic)
    assert result["score"] is None


def test_just_below_threshold_is_unscored():
    desc = "x" * (MIN_LLM_DESCRIPTION_CHARS - 1)
    assert match_resume_to_job("resume text", desc)["score"] is None


def test_unscored_result_shape_is_safe_for_callers():
    # Callers do result.get("score") / .get("reasoning") / .get("key_matches").
    result = match_resume_to_job("resume text", "short synthetic description")
    assert set(result) >= {"score", "reasoning", "key_matches", "gaps"}
    assert isinstance(result["reasoning"], str) and result["reasoning"]
