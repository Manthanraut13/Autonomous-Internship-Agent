"""CSV export: formula-injection hardening (OWASP CSV injection)."""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.csv_exporter import export_jobs_to_csv, _sanitize_cell


def _read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_malicious_cells_are_neutralized(tmp_path, monkeypatch):
    job = {
        "title": "=cmd|'/c calc'!A0",
        "company": "@SUM(1+1)",
        "location": "+919999999999",
        "role_type": "internship",
        "work_mode": "remote",
        "source": "internshala",
        "match_score": 85,
        "semantic_score": 88.0,
        "apply_url": "https://example.com/apply",
        "link": "https://example.com/job",
        "posted_at": "2026-10-11T00:00:00",
        "match_reasoning": "- strong fit",
        "description": "We build LLM agents in Python.",
    }
    out = export_jobs_to_csv([job], "formula_test.csv")
    try:
        rows = _read_rows(out)
        header, data = rows[0], rows[1]
        assert data[header.index("Title")] == "'=cmd|'/c calc'!A0"
        assert data[header.index("Company")] == "'@SUM(1+1)"
        assert data[header.index("Location")] == "'+919999999999"
        assert data[header.index("Match Reasoning")] == "'- strong fit"
        # Non-triggering values pass through untouched
        assert data[header.index("Direct Apply Link")] == "https://example.com/apply"
        assert data[header.index("Match Score")] == "85"
    finally:
        os.remove(out)


def test_sanitize_cell_only_touches_trigger_strings():
    assert _sanitize_cell("=1+1") == "'=1+1"
    assert _sanitize_cell("@x") == "'@x"
    assert _sanitize_cell("-flag") == "'-flag"
    assert _sanitize_cell("+flag") == "'+flag"
    assert _sanitize_cell("AI Engineer") == "AI Engineer"
    assert _sanitize_cell(-5) == -5          # numbers pass through
    assert _sanitize_cell(None) is None
    assert _sanitize_cell("") == ""
