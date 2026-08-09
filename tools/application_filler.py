"""
tools/application_filler.py
---------------------------
Automated job application filler using Playwright + Groq Vision AI.

Architecture:
  1. PRIMARY PATH — Vision-Guided Loop (qwen/qwen3.6-27b)
       Screenshot → Groq Vision analyzes page → decides next Playwright action
       → executes → screenshot again → repeat until submitted or max steps reached.

  2. FALLBACK PATH — CSS Selector Form Filling
       If vision loop completes with no form filling (< 3 fills),
       falls back to the classic CSS-selector-based field scanner.

Key Features:
  - 🧠 Groq Vision AI (qwen/qwen3.6-27b) guides every Playwright step
  - 🔄 Stuck Detection: same page 3 times → force scroll or try alternative action
  - 🏛️ Login Wall Detection: stops immediately if sign-in is required
  - 📸 Step-by-step screenshots saved in data/apply_steps/
  - 🎯 CSS Selector Fallback: handles simple forms without burning API tokens
  - 💾 Persistent Chrome Profile: preserves logged-in sessions (data/chrome_session)
  - 🔀 LinkedIn External Apply Bypass: navigates to ATS (Greenhouse, Lever)
  - 📄 Dynamic Resume Extraction: fills fields directly from resume PDF
"""

import logging
import asyncio
import os
import re
import time
import hashlib
import concurrent.futures
from typing import Dict, Any, List, Optional

try:
    from playwright.sync_api import sync_playwright, Page, Frame, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    Page = None
    Frame = None
    PlaywrightTimeoutError = Exception
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright in background threads
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ──────────────────────────────────────────────────────────────────────────────
# Candidate Profile
# ──────────────────────────────────────────────────────────────────────────────

def _get_candidate_profile(resume_pdf_path: str) -> dict:
    """Extract candidate profile dynamically from resume PDF or settings fallback."""
    try:
        from tools.resume_parser import get_candidate_profile_from_resume
        return get_candidate_profile_from_resume(resume_pdf_path)
    except Exception as e:
        logger.warning(f"Resume profile parsing fallback: {e}")
        return {
            "name": "Manthan Raut",
            "first_name": "Manthan",
            "last_name": "Raut",
            "email": "manthanr141@gmail.com",
            "phone": "+919529883808",
            "github": "https://github.com/Manthanraut13",
            "linkedin": "https://linkedin.com/in/manthan-raut",
            "location": "India",
            "summary": "Software Engineer & AI Application Developer specializing in Python, FastAPI, React, and LLMs.",
            "skills": ["Python", "FastAPI", "React", "SQL", "Docker", "Git", "AI/LLM"],
            "resume_pdf": os.path.abspath(resume_pdf_path) if resume_pdf_path and os.path.exists(resume_pdf_path) else "",
        }


# ──────────────────────────────────────────────────────────────────────────────
# Screenshot Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _take_screenshot(page: Page, step: int, label: str = "") -> str:
    """Take a numbered step screenshot, return the file path."""
    os.makedirs("data/apply_steps", exist_ok=True)
    safe_label = re.sub(r"[^\w]", "_", label)[:30]
    path = f"data/apply_steps/step_{step:03d}_{safe_label}.png"
    try:
        page.screenshot(path=path, full_page=False)
    except Exception as e:
        logger.debug(f"Screenshot failed at step {step}: {e}")
    return path


def _screenshot_hash(path: str) -> str:
    """MD5 hash of screenshot file to detect identical (stuck) pages."""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Vision-Guided Playwright Executor
# ──────────────────────────────────────────────────────────────────────────────

def _execute_vision_action(
    page: Page,
    next_action: dict,
    candidate: dict,
    resume_pdf_path: str,
) -> bool:
    """
    Execute a single action returned by the Groq Vision AI.
    Returns True if the action was executed successfully.
    """
    action_type = next_action.get("type", "scroll")
    target = next_action.get("target", "")
    value = next_action.get("value", "")
    selector_hints = next_action.get("selector_hints", [])

    try:
        # ── CLICK ─────────────────────────────────────────────────────────────
        if action_type == "click":
            # Try selector hints first
            for hint in selector_hints:
                try:
                    el = page.locator(f"button:has-text('{hint}'), a:has-text('{hint}'), [aria-label='{hint}']").first
                    if el.is_visible(timeout=1500):
                        el.scroll_into_view_if_needed()
                        el.click()
                        page.wait_for_timeout(1500)
                        logger.info(f"  ✅ Clicked hint: '{hint}'")
                        return True
                except Exception:
                    pass

            # Try target text
            if target:
                for loc_str in [
                    f"button:has-text('{target}')",
                    f"a:has-text('{target}')",
                    f"[aria-label='{target}']",
                    f"input[value='{target}']",
                    f"text={target}",
                ]:
                    try:
                        el = page.locator(loc_str).first
                        if el.is_visible(timeout=1500):
                            el.scroll_into_view_if_needed()
                            el.click()
                            page.wait_for_timeout(1500)
                            logger.info(f"  ✅ Clicked target: '{target}'")
                            return True
                    except Exception:
                        continue

            logger.warning(f"  ⚠️ Could not find click target: '{target}'")
            return False

        # ── FILL ──────────────────────────────────────────────────────────────
        elif action_type == "fill":
            # If no value from vision, ask text LLM
            fill_value = value
            if not fill_value and target:
                from tools.ai_vision_guide import decide_field_value
                fill_value = decide_field_value(target, candidate)

            found = False
            for hint in selector_hints:
                for sel in [
                    f"input[placeholder='{hint}']",
                    f"input[name='{hint}']",
                    f"input[aria-label='{hint}']",
                    f"textarea[placeholder='{hint}']",
                    f"textarea[name='{hint}']",
                    f"textarea[aria-label='{hint}']",
                    f"[name='{hint}']",
                ]:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=1000):
                            el.scroll_into_view_if_needed()
                            el.clear()
                            el.fill(fill_value)
                            page.wait_for_timeout(500)
                            logger.info(f"  ✅ Filled '{hint}' with '{fill_value}'")
                            found = True
                            return True
                    except Exception:
                        continue

            if not found and target:
                # Try label-based lookup
                try:
                    el = page.get_by_label(target, exact=False).first
                    if el.is_visible(timeout=1500):
                        el.scroll_into_view_if_needed()
                        el.clear()
                        el.fill(fill_value)
                        page.wait_for_timeout(500)
                        logger.info(f"  ✅ Filled by label '{target}' → '{fill_value}'")
                        return True
                except Exception:
                    pass

            logger.warning(f"  ⚠️ Could not fill field: '{target}'")
            return False

        # ── SELECT ────────────────────────────────────────────────────────────
        elif action_type == "select":
            select_value = value
            for hint in selector_hints:
                try:
                    sel_el = page.locator(f"select[name='{hint}'], select[aria-label='{hint}']").first
                    if sel_el.is_visible(timeout=1000):
                        sel_el.select_option(label=select_value)
                        page.wait_for_timeout(500)
                        logger.info(f"  ✅ Selected '{select_value}' in '{hint}'")
                        return True
                except Exception:
                    pass

            if target:
                try:
                    sel_el = page.get_by_label(target, exact=False).first
                    sel_el.select_option(label=select_value)
                    page.wait_for_timeout(500)
                    logger.info(f"  ✅ Selected '{select_value}' for '{target}'")
                    return True
                except Exception:
                    pass

            return False

        # ── UPLOAD ────────────────────────────────────────────────────────────
        elif action_type == "upload":
            upload_path = resume_pdf_path or candidate.get("resume_pdf", "")
            if not upload_path or not os.path.exists(upload_path):
                logger.warning("  ⚠️ Resume PDF not found for upload")
                return False

            for sel in ["input[type='file']", "[class*='upload'] input", "[id*='resume'] input", "[id*='cv'] input"]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        el.set_input_files(upload_path)
                        page.wait_for_timeout(2000)
                        logger.info(f"  ✅ Uploaded resume: {upload_path}")
                        return True
                except Exception:
                    continue

            # Try via filechooser event
            try:
                with page.expect_file_chooser(timeout=3000) as fc_info:
                    upload_btn = page.locator("button:has-text('Upload'), button:has-text('Resume'), label[for*='file']").first
                    upload_btn.click()
                fc = fc_info.value
                fc.set_files(upload_path)
                page.wait_for_timeout(2000)
                logger.info(f"  ✅ Uploaded resume via file chooser")
                return True
            except Exception:
                pass

            return False

        # ── SCROLL ────────────────────────────────────────────────────────────
        elif action_type == "scroll":
            direction = value.lower() if value else "down"
            amount = 500 if direction == "down" else -500
            page.evaluate(f"window.scrollBy(0, {amount})")
            page.wait_for_timeout(800)
            logger.info(f"  ✅ Scrolled {direction}")
            return True

        # ── CLOSE MODAL ───────────────────────────────────────────────────────
        elif action_type == "close_modal":
            for sel in [
                "button[aria-label='Dismiss']",
                "button[aria-label='Close']",
                "button.modal__dismiss",
                "[role='dialog'] button:has-text('Close')",
                "[role='dialog'] button:has-text('Cancel')",
                "button:has-text('Not now')",
                "button:has-text('Skip')",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=800):
                        btn.click()
                        page.wait_for_timeout(600)
                        logger.info(f"  ✅ Closed modal with: {sel}")
                        return True
                except Exception:
                    continue

            # ESC key as last resort
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
            return True

        # ── NAVIGATE ──────────────────────────────────────────────────────────
        elif action_type == "navigate":
            url = value or target
            if url.startswith("http"):
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                logger.info(f"  ✅ Navigated to: {url}")
                return True
            return False

        # ── SUBMIT ────────────────────────────────────────────────────────────
        elif action_type == "submit":
            for sel in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "button:has-text('Send')",
                "button:has-text('Confirm')",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1500):
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        page.wait_for_timeout(3000)
                        logger.info(f"  ✅ Submitted form with: {sel}")
                        return True
                except Exception:
                    continue
            return False

        # ── WAIT ──────────────────────────────────────────────────────────────
        elif action_type == "wait":
            page.wait_for_timeout(2500)
            return True

        return False

    except Exception as e:
        logger.warning(f"  ⚠️ Action '{action_type}' raised exception: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Vision-Guided Application Loop (Primary Path)
# ──────────────────────────────────────────────────────────────────────────────

def _vision_guided_apply(
    page: Page,
    candidate: dict,
    job_url: str,
    resume_pdf_path: str,
    max_steps: int = 30,
) -> Dict[str, Any]:
    """
    Main AI Vision loop.
    Takes screenshot → Groq Vision (qwen/qwen3.6-27b) decides action
    → Playwright executes → repeat until submitted, login_wall, or max steps.

    Returns: { status, steps_taken, fills_done }
    """
    from tools.ai_vision_guide import analyze_screenshot

    step_history: List[dict] = []
    filled_fields: List[str] = []
    screenshot_hashes: List[str] = []
    fills_done = 0
    consecutive_same = 0

    logger.info(f"🤖 Starting Vision-Guided apply loop (max {max_steps} steps)")

    for step in range(1, max_steps + 1):
        # ── Screenshot ────────────────────────────────────────────────────────
        screenshot_path = _take_screenshot(page, step, "vision")

        # Stuck detection via image hash
        current_hash = _screenshot_hash(screenshot_path)
        if current_hash and screenshot_hashes and current_hash == screenshot_hashes[-1]:
            consecutive_same += 1
        else:
            consecutive_same = 0
        screenshot_hashes.append(current_hash)

        if consecutive_same >= 3:
            logger.warning(f"  🔄 Page stuck for {consecutive_same} steps — forcing scroll")
            page.evaluate("window.scrollBy(0, 400)")
            page.wait_for_timeout(800)
            consecutive_same = 0
            continue

        # ── Ask Vision AI ─────────────────────────────────────────────────────
        analysis = analyze_screenshot(
            screenshot_path=screenshot_path,
            candidate=candidate,
            job_url=job_url,
            step_history=step_history,
            filled_fields=filled_fields,
        )

        page_state = analysis.get("page_state", "unknown")
        next_action = analysis.get("next_action", {})
        action_type = next_action.get("type", "scroll")
        target = next_action.get("target", "")
        description = analysis.get("description", "")

        logger.info(
            f"  Step {step:02d} | 🌐 {page_state} | "
            f"👁️ {description[:60]} | "
            f"▶️  {action_type} → '{target[:40]}'"
        )

        # ── Terminal States ───────────────────────────────────────────────────
        if page_state == "submitted" or action_type == "done":
            logger.info(f"  🎉 Application submitted after {step} steps ({fills_done} fields filled)")
            return {"status": "submitted", "steps_taken": step, "fills_done": fills_done}

        if page_state == "login_wall":
            logger.warning(f"  🔐 Login wall detected — stopping vision loop")
            return {"status": "login_required", "steps_taken": step, "fills_done": fills_done}

        if page_state == "captcha":
            logger.warning(f"  🤖 CAPTCHA detected — cannot proceed")
            return {"status": "captcha", "steps_taken": step, "fills_done": fills_done}

        # ── Execute Action ────────────────────────────────────────────────────
        success = _execute_vision_action(page, next_action, candidate, resume_pdf_path)

        if action_type == "fill" and success:
            fills_done += 1
            if target and target not in filled_fields:
                filled_fields.append(target)

        # Log step history for AI context
        step_history.append({
            "step": step,
            "page_state": page_state,
            "action": action_type,
            "target": target,
            "success": success,
        })

        page.wait_for_timeout(1200)

    logger.info(f"  ⏱️ Max steps ({max_steps}) reached — {fills_done} fields filled")
    return {"status": "max_steps", "steps_taken": max_steps, "fills_done": fills_done}


# ──────────────────────────────────────────────────────────────────────────────
# CSS Selector Fallback (Secondary Path)
# ──────────────────────────────────────────────────────────────────────────────

def ask_ai_for_field_answer(question: str, candidate: dict, options: Optional[List[str]] = None) -> str:
    """Text-only Groq LLM for custom form question answers (fallback path)."""
    try:
        from langchain_groq import ChatGroq
        from config.settings import settings

        llm = ChatGroq(api_key=settings.groq_api_key, model=settings.groq_model, temperature=0.1)
        options_str = f"\nAvailable choices: {options}" if options else ""
        prompt = (
            f"You are filling a job application for {candidate.get('name', 'Manthan Raut')}.\n"
            f"Skills: {', '.join(candidate.get('skills', ['Python', 'FastAPI', 'React']))}\n"
            f"Question: \"{question}\"{options_str}\n\n"
            f"Return ONLY the final answer. No explanation."
        )
        resp = llm.invoke(prompt)
        answer = resp.content.strip().strip('"').strip("'")
        logger.info(f"  🧠 AI answered '{question[:40]}': {answer}")
        return answer
    except Exception as e:
        logger.warning(f"AI fallback for '{question}': {e}")
        q_lower = question.lower()
        if any(k in q_lower for k in ["sponsorship", "visa"]): return "No"
        if any(k in q_lower for k in ["authorized", "legally", "eligible"]): return "Yes"
        if any(k in q_lower for k in ["notice", "start", "available"]): return "Immediately"
        if any(k in q_lower for k in ["salary", "ctc", "compensation"]): return "Negotiable"
        if any(k in q_lower for k in ["years", "experience"]): return "2"
        return "Yes"


def _get_field_value(field_name: str, field_placeholder: str, field_label: str, candidate: dict) -> str:
    """Map a form field to candidate data using name/placeholder/label signals."""
    signals = " ".join([field_name, field_placeholder, field_label]).lower()

    if any(k in signals for k in ["first", "fname", "firstname"]): return candidate.get("first_name", "Manthan")
    if any(k in signals for k in ["last", "lname", "lastname", "surname"]): return candidate.get("last_name", "Raut")
    if any(k in signals for k in ["full", "name"]) and "last" not in signals and "first" not in signals:
        return candidate.get("name", "Manthan Raut")
    if any(k in signals for k in ["email", "mail"]): return candidate.get("email", "manthanr141@gmail.com")
    if any(k in signals for k in ["phone", "mobile", "tel", "number"]): return candidate.get("phone", "+919529883808")
    if any(k in signals for k in ["github"]): return candidate.get("github", "https://github.com/Manthanraut13")
    if any(k in signals for k in ["linkedin"]): return candidate.get("linkedin", "https://linkedin.com/in/manthan-raut")
    if any(k in signals for k in ["city", "location", "address", "country"]): return candidate.get("location", "India")
    if any(k in signals for k in ["website", "portfolio", "url"]): return candidate.get("github", "https://github.com/Manthanraut13")
    if any(k in signals for k in ["cover", "message", "why", "motivation"]):
        return (
            f"I am excited to apply for this role. As a software engineer specializing in "
            f"Python, FastAPI, and AI/ML, I have hands-on experience building scalable applications. "
            f"I am confident I will be a strong addition to the team."
        )
    if any(k in signals for k in ["summary", "about", "bio", "objective"]):
        return candidate.get("summary", "Software Engineer specializing in Python, FastAPI, React, and AI/ML.")
    return ""


def _fill_all_frames(page: Page, resume_pdf_path: str, candidate: dict) -> int:
    """
    CSS-selector-based form filler. Scans all iframes recursively.
    Returns count of fields filled.
    """
    frames = [page.main_frame]
    try:
        for frame in page.frames:
            if frame not in frames:
                frames.append(frame)
    except Exception:
        pass

    filled = 0
    for frame in frames:
        try:
            inputs = frame.query_selector_all(
                "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='file']),"
                "textarea, select"
            )
            for inp in inputs:
                try:
                    if not inp.is_visible():
                        continue
                    inp_type = (inp.get_attribute("type") or "text").lower()
                    name = inp.get_attribute("name") or ""
                    placeholder = inp.get_attribute("placeholder") or ""
                    aria_label = inp.get_attribute("aria-label") or ""

                    # Skip if already filled
                    if inp_type in ("text", "email", "tel", "url", "number"):
                        current = inp.input_value()
                        if current and current.strip():
                            continue

                    # Find field label from DOM
                    field_id = inp.get_attribute("id") or ""
                    label_text = ""
                    if field_id:
                        try:
                            label_el = frame.query_selector(f"label[for='{field_id}']")
                            if label_el:
                                label_text = label_el.inner_text().strip()
                        except Exception:
                            pass

                    value = _get_field_value(name, placeholder, f"{aria_label} {label_text}", candidate)

                    if inp_type == "radio" and not value:
                        continue

                    tag = inp.evaluate("el => el.tagName").lower()

                    if tag == "select" and label_text:
                        answer = ask_ai_for_field_answer(label_text, candidate)
                        try:
                            inp.select_option(label=answer)
                            filled += 1
                        except Exception:
                            pass
                        continue

                    if not value:
                        question = label_text or aria_label or placeholder or name
                        if question:
                            value = ask_ai_for_field_answer(question, candidate)

                    if value:
                        inp.scroll_into_view_if_needed()
                        inp.fill(value)
                        filled += 1
                        logger.info(f"  📝 [CSS Fallback] Filled '{name or placeholder or label_text}' → '{value[:40]}'")

                except Exception:
                    continue

            # File upload
            try:
                if resume_pdf_path and os.path.exists(resume_pdf_path):
                    file_inputs = frame.query_selector_all("input[type='file']")
                    for fi in file_inputs:
                        if fi.is_visible():
                            fi.set_input_files(resume_pdf_path)
                            logger.info(f"  📎 [CSS Fallback] Uploaded resume")
                            filled += 1
            except Exception:
                pass

        except Exception:
            continue

    return filled


def _find_and_click_apply_button(page: Page) -> bool:
    """Find and click the Apply button on a job listing page."""
    apply_selectors = [
        "button:has-text('Apply now')",
        "button:has-text('Apply Now')",
        "button:has-text('Easy Apply')",
        "a:has-text('Apply now')",
        "a:has-text('Apply for this job')",
        "button:has-text('Apply')",
        "a[href*='apply']",
        "[data-control-name='jobdetails_topcard_inapply']",
    ]
    for sel in apply_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.scroll_into_view_if_needed()
                btn.click()
                page.wait_for_timeout(2500)
                logger.info(f"  ✅ Clicked apply button: {sel}")
                return True
        except Exception:
            continue
    return False


def _dismiss_cookie_banners(page: Page) -> None:
    """Dismiss cookie/consent banners and sign-in modal overlays."""
    selectors = [
        "button[aria-label='Dismiss']",
        "button[aria-label='Close']",
        "button.modal__dismiss",
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "[id*='cookie'] button",
        "[class*='cookie'] button",
        "[id*='consent'] button",
        # LinkedIn sign-in modal
        "button.modal__dismiss",
        "[data-tracking-control-name='guest_homepage-basic_nav-header-signin'] + button",
        "button[aria-label='Sign in to view more jobs']",
        "section.sign-in-modal button.modal__dismiss",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=600):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            continue


# ──────────────────────────────────────────────────────────────────────────────
# Main Playwright Sync Runner
# ──────────────────────────────────────────────────────────────────────────────

def _run_playwright_sync(job_link: str, resume_pdf_path: str) -> Dict[str, str]:
    """
    Full Playwright execution with Vision AI as primary and CSS fallback.
    Runs in a background thread (sync Playwright).
    """
    candidate = _get_candidate_profile(resume_pdf_path)

    platform = "generic"
    if "linkedin.com" in job_link.lower():
        platform = "linkedin"
    elif "greenhouse.io" in job_link.lower():
        platform = "greenhouse"
    elif "lever.co" in job_link.lower():
        platform = "lever"
    elif "arbeitnow.com" in job_link.lower():
        platform = "arbeitnow"
    elif "remotive.com" in job_link.lower():
        platform = "remotive"

    logger.info(f"🌐 Launching Chrome ({platform}) for: {job_link}")

    try:
        with sync_playwright() as p:
            user_data_dir = os.path.abspath("data/chrome_session")
            os.makedirs(user_data_dir, exist_ok=True)

            # ── Browser Launch (Real Chrome → Chromium fallback) ──────────────
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome",
                    headless=False,
                    slow_mo=250,
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1280, "height": 800},
                )
                logger.info("  → Using real Google Chrome with persistent session")
            except Exception as launch_err:
                logger.warning(f"  → Chrome fallback to Chromium: {launch_err}")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    slow_mo=250,
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1280, "height": 800},
                )

            page = context.pages[0] if context.pages else context.new_page()

            # Arbeitnow uses a direct /apply path
            target_url = job_link
            if "arbeitnow.com" in job_link.lower() and not job_link.endswith("/apply"):
                target_url = f"{job_link.rstrip('/')}/apply"

            # ── Navigate to Job ───────────────────────────────────────────────
            try:
                page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading {target_url}")
                context.close()
                return {"status": "failed", "platform": platform, "error": "Page load timeout"}

            _dismiss_cookie_banners(page)
            os.makedirs("data", exist_ok=True)

            # Pre-apply screenshot
            try:
                page.screenshot(path="data/pre_apply_screenshot.png")
            except Exception:
                pass

            # Click "Apply" button if on listing page
            _find_and_click_apply_button(page)
            _dismiss_cookie_banners(page)
            page.wait_for_timeout(1800)

            # ══════════════════════════════════════════════════════════════════
            # PRIMARY: Vision-Guided AI Loop
            # ══════════════════════════════════════════════════════════════════
            vision_result = _vision_guided_apply(
                page=page,
                candidate=candidate,
                job_url=job_link,
                resume_pdf_path=resume_pdf_path,
                max_steps=30,
            )

            vision_status = vision_result.get("status", "unknown")
            fills_done = vision_result.get("fills_done", 0)

            # ══════════════════════════════════════════════════════════════════
            # FALLBACK: CSS Selector form filling if vision filled < 2 fields
            # ══════════════════════════════════════════════════════════════════
            if vision_status not in ("submitted", "login_required", "captcha") and fills_done < 2:
                logger.info("  🔄 Vision filled < 2 fields — running CSS fallback filler")
                fallback_fills = _fill_all_frames(page, resume_pdf_path, candidate)
                logger.info(f"  📝 CSS fallback filled {fallback_fills} fields")

                # Try to submit the form
                for submit_sel in [
                    "button[type='submit']",
                    "button:has-text('Submit')",
                    "button:has-text('Apply')",
                    "button:has-text('Send Application')",
                ]:
                    try:
                        btn = page.locator(submit_sel).first
                        if btn.is_visible(timeout=1500):
                            btn.scroll_into_view_if_needed()
                            btn.click()
                            page.wait_for_timeout(3000)
                            logger.info(f"  ✅ CSS fallback submitted with: {submit_sel}")
                            break
                    except Exception:
                        continue

            # Post-apply screenshot
            try:
                page.screenshot(path="data/post_apply_screenshot.png")
            except Exception:
                pass

            page.wait_for_timeout(2000)
            context.close()

            # ── Determine Final Status ────────────────────────────────────────
            if vision_status == "submitted":
                logger.info(f"✅ Vision confirmed submission for {job_link}")
                return {"status": "applied", "platform": platform, "mode": "vision_guided"}
            elif vision_status == "login_required":
                logger.warning(f"🔐 Login required for {job_link}")
                return {"status": "login_required", "platform": platform, "mode": "vision_guided"}
            elif fills_done > 0 or (vision_status == "max_steps" and fills_done > 0):
                return {"status": "submitted", "platform": platform, "mode": "vision_guided"}
            else:
                return {"status": "attempted", "platform": platform, "mode": "css_fallback"}

    except Exception as e:
        logger.error(f"Critical error during auto_apply: {e}")
        return {"status": "failed", "platform": platform, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Public Async Entry Point
# ──────────────────────────────────────────────────────────────────────────────

async def auto_apply_to_job(
    job_link: str,
    resume_pdf_path: str,
    github: str = "",
    linkedin: str = "",
) -> Dict[str, str]:
    """
    Async entry point — runs Playwright in a background thread.
    Called by main.py when a user approves a job via WhatsApp or dashboard.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return {"status": "failed", "platform": "unknown", "error": "Playwright missing"}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        _run_playwright_sync,
        job_link,
        resume_pdf_path,
    )
    return result
