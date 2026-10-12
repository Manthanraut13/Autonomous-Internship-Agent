"""
tools/csv_exporter.py
---------------------
Exports a list of jobs to a CSV file.
"""

import csv
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Cells that would be interpreted as formulas by Excel/Sheets (OWASP CSV injection)
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value: Any) -> Any:
    """Neutralize spreadsheet formula injection: a cell starting with =, +, -, @
    gets a leading apostrophe so spreadsheets treat it as plain text."""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


def export_jobs_to_csv(jobs: List[Dict[str, Any]], output_filename: str = "internships_latest.csv") -> str:
    """
    Exports jobs to a CSV file in the 'data' directory.
    Returns the absolute path to the generated CSV file.
    """
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    output_path = os.path.join(data_dir, output_filename)
    
    headers = [
        "Title", 
        "Company", 
        "Location", 
        "Role Type",
        "Work Mode",
        "Source", 
        "Match Score", 
        "Semantic Score",
        "Direct Apply Link", 
        "Job Listing Link", 
        "Posted At", 
        "Key Matches",
        "Match Reasoning",
        "Description (Truncated)"
    ]
    
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for job in jobs:
                # Truncate description to prevent Excel issues
                desc = job.get("description", "")
                if desc:
                    desc = (desc[:1000] + "...") if len(desc) > 1000 else desc
                
                key_matches = job.get("key_matches", [])
                if isinstance(key_matches, list):
                    key_matches = ", ".join(key_matches)
                    
                writer.writerow([
                    _sanitize_cell(job.get("title", "")),
                    _sanitize_cell(job.get("company", "")),
                    _sanitize_cell(job.get("location", "")),
                    job.get("role_type", "internship"),
                    job.get("work_mode", "onsite"),
                    _sanitize_cell(job.get("source", "")),
                    job.get("match_score", ""),
                    job.get("semantic_score", ""),
                    _sanitize_cell(job.get("apply_url", "")),
                    _sanitize_cell(job.get("link", "")),
                    _sanitize_cell(str(job.get("posted_at", ""))),
                    _sanitize_cell(key_matches),
                    _sanitize_cell(job.get("match_reasoning", "")),
                    _sanitize_cell(desc)
                ])
                
        logger.info(f"Successfully exported {len(jobs)} jobs to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export jobs to CSV: {e}")
        return ""
