#!/usr/bin/env python
"""
run_scheduler.py
================
Automated background scheduler for the Autonomous Internship Agent.

Schedules the pipeline to execute automatically twice every day:
  1. Morning Run: 09:00 AM (9:00)
  2. Evening Run: 09:00 PM (21:00)

Usage:
    python run_scheduler.py
    python run_scheduler.py --now   # Run immediately once, then keep scheduling
"""

import sys
import os
import time
import logging
from datetime import datetime

# Ensure project root is on the import path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from run_pipeline import run as execute_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  [SCHEDULER] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def scheduled_job():
    """Wrapper invoked by the APScheduler trigger."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"⏰ Triggering scheduled Autonomous Internship Agent pipeline run at {now_str}…")
    try:
        res = execute_pipeline(target_matches=25, threshold=settings.match_score_threshold)
        logger.info(f"✅ Scheduled run completed successfully: {res}")
    except Exception as e:
        logger.error(f"❌ Scheduled pipeline run failed: {e}", exc_info=True)


def start_scheduler(run_immediately: bool = False):
    """Initializes and runs the blocking scheduler."""
    scheduler = BlockingScheduler()

    # Schedule 1: Morning Run at 09:00 AM
    scheduler.add_job(
        scheduled_job,
        trigger=CronTrigger(hour=9, minute=0),
        id="morning_pipeline_run",
        name="Morning Internship Pipeline (09:00 AM)",
        replace_existing=True,
    )

    # Schedule 2: Evening Run at 09:00 PM (21:00)
    scheduler.add_job(
        scheduled_job,
        trigger=CronTrigger(hour=21, minute=0),
        id="evening_pipeline_run",
        name="Evening Internship Pipeline (09:00 PM)",
        replace_existing=True,
    )

    print("=" * 65)
    print("  🕒  AUTONOMOUS INTERNSHIP AGENT — DUAL CRON SCHEDULER")
    print("=" * 65)
    print("  Active Cron Jobs:")
    print("    • Morning Run : Every day at 09:00 AM")
    print("    • Evening Run : Every day at 09:00 PM")
    print("    • Target      : 25 Unique AI Internship Listings per run")
    print("    • Deduplication: Strict (Cross-run SQLite lookup)")
    print("=" * 65)

    if run_immediately:
        print("\n🚀 '--now' flag passed — running pipeline once immediately...\n")
        scheduled_job()

    jobs = scheduler.get_jobs()
    for j in jobs:
        print(f"  📅 Next scheduled run for '{j.name}': {j.next_run_time}")

    print("\nScheduler running. Press CTRL+C to stop.\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    run_now = "--now" in sys.argv
    start_scheduler(run_immediately=run_now)
