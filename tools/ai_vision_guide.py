"""
tools/ai_vision_guide.py
------------------------
AI Vision Guide using Groq's qwen/qwen3.6-27b (free, vision-capable).

Takes a screenshot of the current browser state and asks the LLM:
  "What do you see? What should Playwright do next to fill/submit this job application?"

Returns a structured action dict that the Playwright loop executes.

Supported page states:
  listing        - Job description/listing page (need to find Apply button)
  apply_form     - Single-page application form
  multi_step     - Multi-step form (Next/Continue buttons)
  modal          - Popup/modal dialog (e.g. LinkedIn Easy Apply)
  login_wall     - Sign-in gate blocking access
  upload_page    - Resume/document upload step
  submitted      - Confirmation/success page
  error          - Error or blocked page
  captcha        - CAPTCHA challenge
  unknown        - Cannot determine state

Supported action types:
  click          - Click a button or element
  fill           - Type text into an input/textarea
  select         - Choose from a dropdown/select
  upload         - Upload a file (resume PDF)
  scroll         - Scroll down/up to reveal content
  close_modal    - Close an unwanted popup/modal
  navigate       - Go to a different URL
  submit         - Submit the form
  wait           - Wait for page to settle
  done           - Application complete, stop loop
"""

import base64
import json
import logging
import re
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Free Groq vision model confirmed working
VISION_MODEL = "qwen/qwen3.6-27b"

SYSTEM_PROMPT = """\
You are an expert job application AI assistant. You look at browser screenshots and decide what action to take next to fill and submit a job application on behalf of the candidate.

RULES:
1. Respond with ONLY a valid JSON object. No markdown fences, no explanation text, no <think> tags — raw JSON only.
2. Always pick the single most important next action.
3. If you see a "Sign in" wall or login gate, set page_state to "login_wall" and action type to "done".
4. If you see a confirmation/success message (Applied!, Application submitted, Thank you for applying), set page_state to "submitted" and action type to "done".
5. For form fields, match the field label to candidate data as closely as possible.
6. If there is a Next/Continue/Submit button visible, prefer clicking it only after all visible fields are filled.

JSON structure (use exactly these keys):
{
  "page_state": "listing|apply_form|multi_step|modal|login_wall|upload_page|submitted|error|captcha|unknown",
  "description": "One sentence describing what you see on the page",
  "all_visible_fields": ["field label 1", "field label 2"],
  "next_action": {
    "type": "click|fill|select|upload|scroll|close_modal|navigate|submit|wait|done",
    "target": "Exact visible text label or description of the element to interact with",
    "value": "Text to type or option to select (empty string for click/scroll actions)",
    "selector_hints": ["button text", "placeholder text", "aria-label", "name attribute"]
  },
  "confidence": 0.85
}
"""


def _build_candidate_summary(candidate: dict) -> str:
    """Build a compact candidate summary string for the vision prompt."""
    skills = candidate.get("skills", [])
    if isinstance(skills, list):
        skills_str = ", ".join(skills[:12])
    else:
        skills_str = str(skills)[:200]

    return (
        f"Candidate Info:\n"
        f"  Full Name: {candidate.get('name', 'Manthan Raut')}\n"
        f"  First Name: {candidate.get('first_name', 'Manthan')}\n"
        f"  Last Name: {candidate.get('last_name', 'Raut')}\n"
        f"  Email: {candidate.get('email', 'manthanr141@gmail.com')}\n"
        f"  Phone: {candidate.get('phone', '+919529883808')}\n"
        f"  GitHub: {candidate.get('github', 'https://github.com/Manthanraut13')}\n"
        f"  LinkedIn: {candidate.get('linkedin', 'https://linkedin.com/in/manthan-raut')}\n"
        f"  Location: {candidate.get('location', 'India')}\n"
        f"  Skills: {skills_str}\n"
        f"  Summary: {candidate.get('summary', 'Software Engineer specializing in Python, FastAPI, React, AI/ML.')}"
    )


def _extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Robustly extract JSON from model response.
    Handles: raw JSON, JSON inside ```json blocks, JSON with surrounding text.
    """
    if not text:
        return None

    # 1. Strip think tags (qwen reasoning)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 2. Try raw parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Extract from code fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 4. Find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def analyze_screenshot(
    screenshot_path: str,
    candidate: dict,
    job_url: str = "",
    step_history: Optional[List[dict]] = None,
    filled_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send a browser screenshot to Groq Vision (qwen/qwen3.6-27b) and get the
    next Playwright action to take for job application.

    Args:
        screenshot_path: Path to the PNG screenshot file.
        candidate:       Dict with candidate profile (name, email, phone, etc.).
        job_url:         Current job listing URL (for context).
        step_history:    List of previous steps taken (to avoid repetition).
        filled_fields:   Fields already filled in this session.

    Returns:
        Action dict with keys: page_state, description, next_action, confidence.
        On failure returns a safe "scroll_down" or "done" fallback.
    """
    FALLBACK = {
        "page_state": "unknown",
        "description": "Could not analyze screenshot — using fallback",
        "all_visible_fields": [],
        "next_action": {
            "type": "scroll",
            "target": "page",
            "value": "down",
            "selector_hints": [],
        },
        "confidence": 0.0,
    }

    # ── Load screenshot ───────────────────────────────────────────────────────
    if not os.path.exists(screenshot_path):
        logger.warning(f"[Vision] Screenshot not found: {screenshot_path}")
        return FALLBACK

    try:
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.warning(f"[Vision] Failed to read screenshot: {e}")
        return FALLBACK

    # ── Build context for the AI ──────────────────────────────────────────────
    candidate_summary = _build_candidate_summary(candidate)
    history_str = ""
    if step_history:
        recent = step_history[-5:]  # only last 5 steps to save tokens
        history_str = "\nRecent actions taken:\n" + "\n".join(
            f"  Step {s['step']}: [{s['page_state']}] {s['action']} → {s.get('target', '')}"
            for s in recent
        )

    filled_str = ""
    if filled_fields:
        filled_str = f"\nAlready filled fields: {', '.join(filled_fields)}"

    user_prompt = (
        f"I am automating a job application. Here is the current browser screenshot.\n\n"
        f"Job URL: {job_url}\n\n"
        f"{candidate_summary}"
        f"{history_str}"
        f"{filled_str}\n\n"
        f"Analyze the screenshot and tell me the SINGLE BEST next action to take "
        f"to progress the job application. Respond with ONLY raw JSON."
    )

    # ── Call Groq Vision API ──────────────────────────────────────────────────
    try:
        from groq import Groq
        from config.settings import settings

        client = Groq(api_key=settings.groq_api_key)

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                },
            ],
            max_tokens=600,
            reasoning_effort="none",   # disable CoT for speed & token savings
            temperature=0.1,
        )

        raw_content = response.choices[0].message.content or ""
        logger.debug(f"[Vision] Raw response: {raw_content[:300]}")

        parsed = _extract_json_from_response(raw_content)
        if parsed and "next_action" in parsed:
            action_type = parsed["next_action"].get("type", "scroll")
            target = parsed["next_action"].get("target", "")
            state = parsed.get("page_state", "unknown")
            confidence = parsed.get("confidence", 0.5)
            logger.info(
                f"[Vision] State: {state} | Action: {action_type} → '{target}' "
                f"(confidence: {confidence:.0%})"
            )
            return parsed
        else:
            logger.warning(f"[Vision] Could not parse JSON from response: {raw_content[:200]}")
            return FALLBACK

    except Exception as e:
        logger.warning(f"[Vision] Groq API call failed: {e}")
        return FALLBACK


def decide_field_value(field_label: str, candidate: dict, options: Optional[List[str]] = None) -> str:
    """
    Text-only Groq call to decide what value to put in a specific form field.
    Used as a fallback when the vision loop identifies a field but has no value.
    """
    try:
        from groq import Groq
        from config.settings import settings

        client = Groq(api_key=settings.groq_api_key)
        candidate_summary = _build_candidate_summary(candidate)
        options_str = f"\nAvailable choices: {options}" if options else ""

        prompt = (
            f"{candidate_summary}\n\n"
            f"Form field label: \"{field_label}\"{options_str}\n\n"
            f"What should I type/select for this field? "
            f"Return ONLY the answer value, no explanation. "
            f"For dropdowns, return exactly one of the available choices."
        )

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # fast text model for field values
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip().strip('"').strip("'")
        logger.info(f"[VisionField] '{field_label}' → '{answer}'")
        return answer

    except Exception as e:
        logger.warning(f"[VisionField] Fallback for '{field_label}': {e}")
        label_lower = field_label.lower()
        if "first" in label_lower and "name" in label_lower:
            return candidate.get("first_name", "Manthan")
        if "last" in label_lower and "name" in label_lower:
            return candidate.get("last_name", "Raut")
        if "name" in label_lower:
            return candidate.get("name", "Manthan Raut")
        if "email" in label_lower:
            return candidate.get("email", "manthanr141@gmail.com")
        if "phone" in label_lower or "mobile" in label_lower:
            return candidate.get("phone", "+919529883808")
        if "github" in label_lower:
            return candidate.get("github", "https://github.com/Manthanraut13")
        if "linkedin" in label_lower:
            return candidate.get("linkedin", "https://linkedin.com/in/manthan-raut")
        if "location" in label_lower or "city" in label_lower:
            return candidate.get("location", "India")
        if "experience" in label_lower or "year" in label_lower:
            return "2"
        if "salary" in label_lower or "ctc" in label_lower:
            return "Negotiable"
        if "sponsor" in label_lower or "visa" in label_lower:
            return "No"
        if "authoriz" in label_lower or "eligible" in label_lower:
            return "Yes"
        if "notice" in label_lower or "availab" in label_lower:
            return "Immediately"
        return "Yes"
