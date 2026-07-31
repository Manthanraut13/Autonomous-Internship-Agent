# tools/apply_indeed.py
"""
apply_indeed.py
----------------
Placeholder implementation for applying to an Indeed job.
The real implementation would POST the application data to Indeed's API or
automate a browser submission. For the free‑tier demo we simply return ``True``
to indicate success.
"""

from typing import Dict, Any

def apply_to_indeed(job: Dict[str, Any]) -> bool:
    """Pretend to apply to an Indeed job.

    Args:
        job: Dictionary containing at least a ``link`` field.
    Returns:
        ``True`` if the dummy apply succeeded.
    """
    # In a production version we would perform HTTP requests or use Playwright.
    # Here we just log and return success.
    return True
