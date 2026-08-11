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
        "Source", 
        "Match Score", 
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
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("source", ""),
                    job.get("match_score", ""),
                    job.get("apply_url", ""),
                    job.get("link", ""),
                    job.get("posted_at", ""),
                    key_matches,
                    job.get("match_reasoning", ""),
                    desc
                ])
                
        logger.info(f"Successfully exported {len(jobs)} jobs to {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Failed to export jobs to CSV: {e}")
        return ""
