#!/usr/bin/env python
"""
run_pipeline.py
===============
CLI frontend for the shared pipeline core (tools/pipeline_core.py).

All scraping, filtering, scoring and delivery logic lives in the core and is
shared with the SSE dashboard stream in main.py; this file only renders the
progress events for the terminal.

Usage:
    python run_pipeline.py
    python run_pipeline.py --target 25 --threshold 70
    python run_pipeline.py --dry-run
"""

import argparse
import logging
import sys
import os
from typing import Any, Dict

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.settings import settings
from db.database import init_db
from tools.pipeline_core import process_jobs

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Ensure tables exist
init_db()


def run(target_matches: int = 25, threshold: int = 70, dry_run: bool = False) -> Dict[str, Any]:
    """
    Executes the shared pipeline (tools.pipeline_core.process_jobs) and prints
    its progress events. Returns the final outcome dict from the pipeline.
    """
    print("\n" + "=" * 65)
    print("  🚀  AUTONOMOUS INTERNSHIP AGENT — SEMANTIC MATCHING PIPELINE")
    print("=" * 65)

    outcome: Dict[str, Any] = {"status": "error", "message": "Pipeline did not run."}

    for event in process_jobs(target_matches=target_matches, threshold=threshold,
                              source="cli", dry_run=dry_run):
        step = event.get("step", "?")
        print(f"[{step.upper()}] {event.get('message', '')}")
        if step in ("complete", "aborted", "error"):
            outcome = event.get("data") or {"status": step}

    print(f"\n{'━' * 65}")
    print("📊 Pipeline Execution Summary:")
    print(f"   • Status: {outcome.get('status', 'unknown')}")
    print(f"   • Total Scraped Across All Portals: {outcome.get('total_scraped', 0)}")
    print(f"   • Cross-run Duplicates Filtered: {outcome.get('duplicate_skipped', 0)}")
    print(f"   • Low Semantic Match Pre-filtered (<15): {outcome.get('semantic_filtered', 0)}")
    print(f"   • Qualified Matches ({threshold}+ score): {outcome.get('jobs_matched', 0)}")
    print(f"   • Unscored (no real JD — apply link only): {outcome.get('jobs_unscored', 0)}")
    breakdown = outcome.get("platform_breakdown") or {}
    if breakdown:
        print(f"   • Platform Breakdown: {breakdown}")
    if outcome.get("csv_path"):
        print(f"   • CSV report: {outcome['csv_path']}")
    print(f"{'━' * 65}")

    status = outcome.get("status", "error")
    if status == "success":
        print(f"\n  ✅  PIPELINE COMPLETE — {outcome.get('jobs_matched', 0)} QUALIFIED + "
              f"{outcome.get('jobs_unscored', 0)} UNSCORED (APPLY LINK ONLY) LISTINGS DELIVERED")
    elif status == "aborted":
        print("\n  ⛔  PIPELINE ABORTED")
    else:
        print(f"\n  ❌  PIPELINE FAILED — {outcome.get('message', 'unknown error')}")

    return outcome


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the autonomous AI internship agent pipeline"
    )
    parser.add_argument(
        "--target", "-t",
        type=int,
        default=25,
        help="Target number of unique matched jobs to return (default: 25)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=settings.match_score_threshold,
        help=f"Minimum match score threshold (default: {settings.match_score_threshold})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute scraping and matching without sending email or WhatsApp notifications",
    )
    args = parser.parse_args()

    run(
        target_matches=args.target,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )
