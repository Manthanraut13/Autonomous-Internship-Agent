"""
Smoke tests for the shared pipeline core (tools/pipeline_core.py, issue #5):
one implementation of scrape → dedup → guardrail → score → deliver, consumed
by both the CLI and the SSE dashboard.

All external seams (scrapers, LLM, embedder, DB, CSV, email, WhatsApp) are
monkeypatched, so these tests run fully offline and fast.
"""

import contextlib
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.pipeline_core as core
from db.models import Job
from tools.pipeline_core import passes_date_gate, build_job_card


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


class FakeEmbedder:
    def __init__(self, resume_path):
        self.chunks = ["section-1", "section-2"]

    def compute_semantic_score(self, desc, title):
        return 88.0


def make_job(company, link, desc, posted_at=None, title="AI Engineer Intern", location="Bengaluru, India"):
    return {
        "title": title,
        "company": company,
        "link": link,
        "apply_url": link,
        "description": desc,
        "location": location,
        "source": "fakeboard",
        "posted_at": posted_at or datetime.now(timezone.utc).replace(tzinfo=None),
    }


GOOD_DESC = "Build LLM agents in Python. " * 20        # >400 chars → scored
SYNTHETIC_DESC = "AI Intern position at Beta. Location: India."  # <400 chars → unscored


@pytest.fixture
def patched(monkeypatch, tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-fake")

    fake_db = FakeDB()
    csv_calls = {}

    @contextlib.contextmanager
    def fake_db_context():
        yield fake_db

    def fake_match(resume_text, desc):
        if len(desc.strip()) < core.MIN_LLM_DESCRIPTION_CHARS:
            return {"score": None, "reasoning": "Unscored — no real job description available.",
                    "key_matches": [], "gaps": []}
        return {"score": 85, "reasoning": "Strong fit.", "key_matches": ["python"], "gaps": []}

    def fake_csv(jobs, filename):
        csv_calls["jobs"] = list(jobs)
        csv_calls["filename"] = filename
        return os.path.join("data", filename)

    monkeypatch.setattr(core, "find_resume", lambda: str(resume))
    monkeypatch.setattr(core, "get_resume_text", lambda p: "Python developer building LLM agents")
    monkeypatch.setattr(core, "ResumeEmbedder", FakeEmbedder)
    monkeypatch.setattr(core, "get_search_queries_from_resume", lambda p: ["AI Intern"])
    monkeypatch.setattr(core, "cleanup_expired_rejected_jobs", lambda max_age_hours=24: 0)
    monkeypatch.setattr(core, "get_existing_db_signatures", lambda: ({"https://old/1"}, set(), set()))
    monkeypatch.setattr(core, "fetch_full_job_description", lambda link: None)
    monkeypatch.setattr(core, "match_resume_to_job", fake_match)
    monkeypatch.setattr(core, "export_jobs_to_csv", fake_csv)
    monkeypatch.setattr(core, "send_csv_email", lambda path, count: True)
    monkeypatch.setattr(core, "send_whatsapp_summary", lambda phone, jobs: True)
    monkeypatch.setattr(core, "get_db_context", fake_db_context)
    monkeypatch.setattr(core, "settings", SimpleNamespace(
        whatsapp_from="+1000", user_whatsapp_number="+2000", recipient_email="me@example.com"))
    monkeypatch.setattr(core.time, "sleep", lambda s: None)  # no 1.5s LLM rate-limit waits

    def run_with(jobs, **kwargs):
        pending = {"jobs": list(jobs)}

        def primary_fn(query, limit, days, offset):
            # Each query gets its own page; this fake serves one page total.
            page = pending["jobs"]
            pending["jobs"] = []
            return page

        platforms = [{"name": "FakeBoard", "source": "fakeboard", "fn": primary_fn, "quota": 10}]
        monkeypatch.setattr(core, "get_scraper_platforms", lambda: platforms)
        monkeypatch.setattr(core, "fetch_linkedin_jobs", lambda **kw: [])
        events = list(core.process_jobs(target_matches=5, threshold=70, **kwargs))
        return events, fake_db, csv_calls

    return run_with


# ── The run: scored + unscored + stale-dropped ───────────────────────────────

def test_mixed_run_outcome(patched):
    events, fake_db, csv_calls = patched([
        make_job("Acme", "https://j/good", GOOD_DESC),
        make_job("Beta", "https://j/short", SYNTHETIC_DESC, title="AI Intern"),
        make_job("OldCo", "https://j/stale", GOOD_DESC, title="ML Intern",
                 posted_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)),
    ])

    last = events[-1]
    assert last["step"] == "complete"
    data = last["data"]
    assert data["status"] == "success"
    assert data["jobs_matched"] == 1
    assert data["jobs_unscored"] == 1
    assert data["total_scraped"] == 3
    assert data["email_sent"] is True
    assert data["whatsapp_sent"] is True
    assert data["csv_path"] == os.path.join("data", csv_calls["filename"])

    # Stale job was dropped by the 24h date gate before scoring
    assert not any("OldCo" in e["message"] for e in events)

    # DB: scored + unscored saved; stale not saved
    saved_jobs = [o for o in fake_db.added if isinstance(o, Job)]
    assert len(saved_jobs) == 2
    by_score = {j.company: j.match_score for j in saved_jobs}
    assert by_score["Acme"] == 85
    assert by_score["Beta"] is None

    # CSV receives both delivered listings
    assert sorted(j["company"] for j in csv_calls["jobs"]) == ["Acme", "Beta"]


def test_duplicate_and_guardrail_still_apply(patched):
    # The dup link is pre-seeded as an existing DB signature; Indore, India passes
    # the location guardrail, but "New York, USA" must be filtered out.
    events, fake_db, _ = patched([
        make_job("DupeCo", "https://old/1", GOOD_DESC),          # exact DB link duplicate
        make_job("USCo", "https://j/us", GOOD_DESC, title="AI Intern",
                 location="New York, USA"),                      # fails India guardrail
    ])
    last = events[-1]
    assert last["step"] == "complete"
    assert last["data"]["jobs_matched"] == 0
    assert last["data"]["jobs_unscored"] == 0
    assert last["data"]["duplicate_skipped"] == 1
    assert not any(o for o in fake_db.added if isinstance(o, Job))


def test_unscored_only_run_saves_but_never_emails(patched):
    events, fake_db, csv_calls = patched([
        make_job("Beta", "https://j/short", SYNTHETIC_DESC, title="AI Intern"),
    ])
    last = events[-1]
    assert last["step"] == "complete"
    data = last["data"]
    assert data["jobs_matched"] == 0
    assert data["jobs_unscored"] == 1
    assert data["email_sent"] is False          # no qualified matches → no email
    assert data["csv_path"]                    # but CSV still exported
    saved_jobs = [o for o in fake_db.added if isinstance(o, Job)]
    assert len(saved_jobs) == 1 and saved_jobs[0].match_score is None


def test_dry_run_skips_email_and_whatsapp(patched):
    events, _, _ = patched(
        [make_job("Acme", "https://j/good", GOOD_DESC)],
        dry_run=True,
    )
    data = events[-1]["data"]
    assert data["email_sent"] is False
    assert data["whatsapp_sent"] is False
    assert data["jobs_matched"] == 1
    assert any("DRY RUN" in e["message"] for e in events)


def test_abort_saves_nothing(patched):
    calls = {"n": 0}

    def abort_after_two():
        calls["n"] += 1
        return calls["n"] > 2

    events, fake_db, _ = patched(
        [make_job("Acme", "https://j/good", GOOD_DESC)],
        should_abort=abort_after_two,
    )
    assert events[-1]["step"] == "aborted"
    assert events[-1]["data"]["status"] == "aborted"
    assert not any(isinstance(o, Job) for o in fake_db.added)


def test_missing_resume_yields_error_event(monkeypatch):
    monkeypatch.setattr(core, "find_resume",
                        lambda: (_ for _ in ()).throw(FileNotFoundError("No resume found. Place Manthan_Raut.pdf in the project root.")))
    events = list(core.process_jobs())
    assert events[-1]["step"] == "error"
    assert "No resume found" in events[-1]["message"]


# ── Pure helpers ─────────────────────────────────────────────────────────────

def test_date_gate_fresh_naive_passes():
    assert passes_date_gate(datetime.now(timezone.utc).replace(tzinfo=None), 24)


def test_date_gate_old_naive_fails():
    assert not passes_date_gate(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48), 24)


def test_date_gate_old_aware_fails():
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    assert not passes_date_gate(old, 24)


def test_date_gate_naive_treated_as_utc():
    # A naive timestamp 25h old must fail (naive == UTC), not pass as "local".
    assert not passes_date_gate(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25), 24)


def test_date_gate_parseable_strings_are_checked():
    fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    assert passes_date_gate(fresh, 24)
    assert not passes_date_gate(stale, 24)


def test_date_gate_unparseable_string_is_rejected():
    # Recency cannot be verified → must not slip through (issue #11).
    assert not passes_date_gate("sometime last year", 24)
    assert not passes_date_gate("N/A", 24)


def test_date_gate_missing_date_passes():
    # No date published at all → cannot be stale by date; keep the listing.
    assert passes_date_gate(None, 24)
    assert passes_date_gate("", 24)
    assert passes_date_gate("   ", 24)


def test_job_card_shape():
    j = make_job("Acme", "https://j/good", GOOD_DESC)
    card = build_job_card(j, 85, "fit", 88.0, "internship", "remote", 3)
    assert card["id"] == -3
    assert card["match_score"] == 85
    assert card["work_mode"] == "remote"
    assert card["status"] == "saved"
