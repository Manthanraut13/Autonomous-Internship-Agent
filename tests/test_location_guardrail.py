"""
Tests for the India location guardrail (tools/job_api.py).

Rules under test:
  - A job passes only with real India evidence: an Indian place in the
    location field, or (when location is empty/generic) an Indian place
    in the TITLE.
  - A missing / unknown location is NEVER treated as India.
  - Platform names and synthetic descriptions are NOT evidence.

Note: importing tools.job_api loads config/settings, so a .env (or real
environment variables) with GROQ_API_KEY etc. must be present — same
requirement as running the pipeline itself.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.job_api import is_located_in_india, _india_place_from_text  # noqa: E402


def _job(**kwargs):
    base = {"title": "AI Engineer Intern", "company": "Acme", "description": "", "source": "greenhouse"}
    base.update(kwargs)
    return base


# ── Location field carries real India evidence ──────────────────────────────

def test_indian_city_in_location_passes():
    assert is_located_in_india(_job(location="Bengaluru"))

def test_india_country_in_location_passes():
    assert is_located_in_india(_job(location="India"))

def test_remote_in_india_passes():
    assert is_located_in_india(_job(location="Remote, India"))

def test_india_remote_parentheses_passes():
    assert is_located_in_india(_job(location="India (Remote)"))

def test_state_in_location_passes():
    assert is_located_in_india(_job(location="Maharashtra, India"))


# ── Foreign locations are rejected ──────────────────────────────────────────

def test_new_york_rejected():
    assert not is_located_in_india(_job(location="New York, United States"))

def test_san_francisco_rejected():
    assert not is_located_in_india(_job(location="San Francisco Bay Area"))

def test_london_rejected():
    assert not is_located_in_india(_job(location="London, UK"))

def test_ambiguous_remote_rejected():
    assert not is_located_in_india(_job(location="Remote"))

def test_empty_location_rejected():
    assert not is_located_in_india(_job(location=""))


# ── The old loopholes stay closed ───────────────────────────────────────────

def test_internshala_source_no_longer_bypasses_guardrail():
    # Previously: source == "internshala" returned True for any location.
    assert not is_located_in_india(_job(location="", source="internshala"))
    assert not is_located_in_india(_job(location="New York", source="internshala"))
    # ...but a genuine Indian location from Internshala still passes:
    assert is_located_in_india(_job(location="Delhi", source="internshala"))

def test_synthetic_description_is_not_india_evidence():
    # Several scrapers build descriptions like "... Listed on Internshala India."
    # — description text must never smuggle a job past the guardrail.
    j = _job(location="", description="AI Engineer position at X. Listed on Internshala India.")
    assert not is_located_in_india(j)

def test_generic_remote_with_india_in_title_passes():
    # Title is real listing data, so it is valid evidence.
    assert is_located_in_india(_job(location="Remote", title="AI Intern - Bangalore (Remote)"))

def test_generic_remote_with_india_only_in_description_rejected():
    j = _job(location="Remote", title="AI Engineer Intern",
             description="This role is open to candidates located in India only.")
    assert not is_located_in_india(j)


# ── _india_place_from_text (used for HN titles, which have no location) ────

def test_place_extractor_finds_country():
    assert _india_place_from_text("Hiring ML Engineers, India").lower() == "india"

def test_place_extractor_finds_city():
    assert _india_place_from_text("AI Intern — Bangalore (YC W24)").lower() in ("bangalore", "bengaluru")

def test_place_extractor_finds_state():
    assert _india_place_from_text("Remote role for candidates in Karnataka").lower() == "karnataka"

def test_place_extractor_returns_empty_when_nothing_found():
    assert _india_place_from_text("Senior Engineer, San Francisco") == ""

def test_place_extractor_handles_empty_input():
    assert _india_place_from_text("") == ""
