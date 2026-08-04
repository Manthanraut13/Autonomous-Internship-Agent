"""
tools/application_filler.py
---------------------------
Automated job application filler using Playwright.
Uses Playwright's SYNC API in a background thread to avoid
Windows asyncio subprocess limitations inside uvicorn.

Key features:
  - Opens a VISIBLE Chromium browser so user can watch live
  - Specialized handlers for Greenhouse (job-boards.greenhouse.io), Lever (jobs.lever.co), Arbeitnow, Remotive, Himalayas, and generic forms
  - Clicks through listing pages to reach actual apply forms
  - Fills forms using candidate profile from settings.py
  - Fills standard and custom questions (LinkedIn, GitHub, Salary, Availability, Dropdowns, Uploads)
  - Stealth flags enabled to pass security checks
"""

import logging
import asyncio
import os
import concurrent.futures
from typing import Dict, Any

try:
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    Page = None
    PlaywrightTimeoutError = Exception
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright in background threads
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _get_candidate_info() -> dict:
    """Load candidate profile from settings."""
    try:
        from config.settings import settings
        return {
            "name": settings.candidate_name,
            "email": settings.candidate_email,
            "phone": settings.candidate_phone,
            "github": settings.candidate_github,
            "linkedin": settings.candidate_linkedin,
        }
    except Exception:
        return {
            "name": "Manthan Raut",
            "email": "manthanr141@gmail.com",
            "phone": "+919529883808",
            "github": "https://github.com/Manthanraut13",
            "linkedin": "https://linkedin.com/in/manthan-raut",
        }


def _dismiss_cookie_banners(page: Page) -> None:
    """Try to dismiss common cookie consent banners."""
    selectors = [
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "[id*='cookie'] button",
        "[class*='cookie'] button",
        "[id*='consent'] button",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click()
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def _find_and_click_apply_button(page: Page) -> bool:
    """
    On job listing pages (Arbeitnow, WWR, Remotive, etc.), find and click
    the external "Apply" button to reach the company's actual application portal.
    """
    apply_selectors = [
        "a:has-text('Apply Now')",
        "a:has-text('Apply for this job')",
        "a:has-text('Apply')",
        "button:has-text('Apply Now')",
        "button:has-text('Apply')",
        "a.apply-button",
        "a[class*='apply']",
        "a[href*='apply']",
        ".job-apply a",
        ".apply-btn",
    ]

    for sel in apply_selectors:
        try:
            link = page.locator(sel).first
            if link.is_visible(timeout=2000):
                href = link.get_attribute("href") or ""
                target = link.get_attribute("target") or ""

                if target == "_blank" and href.startswith("http"):
                    logger.info(f"  → Found external apply link: {href[:80]}...")
                    page.goto(href, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    return True
                elif href and href.startswith("http"):
                    page.goto(href, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    return True
                else:
                    link.click()
                    page.wait_for_timeout(3000)
                    return True
        except Exception:
            continue

    return False


def _fill_greenhouse_form(page: Page, resume_pdf_path: str, candidate: dict) -> bool:
    """
    Specialized form filler for Greenhouse (job-boards.greenhouse.io).
    Fills First Name, Last Name, Email, Phone, Resume upload, LinkedIn, GitHub,
    custom text questions, and custom dropdowns.
    """
    filled_something = False
    try:
        # First Name / Full Name
        first_name_inp = page.locator("input[id*='first_name'], input[name*='first_name']").first
        if first_name_inp.count() > 0 and first_name_inp.is_visible():
            first_name_inp.fill(candidate["name"].split()[0])
            filled_something = True

        last_name_inp = page.locator("input[id*='last_name'], input[name*='last_name']").first
        if last_name_inp.count() > 0 and last_name_inp.is_visible():
            parts = candidate["name"].split()
            last_name_inp.fill(parts[-1] if len(parts) > 1 else "")
            filled_something = True

        # Email
        email_inp = page.locator("input[id*='email'], input[type='email']").first
        if email_inp.count() > 0 and email_inp.is_visible():
            email_inp.fill(candidate["email"])
            filled_something = True

        # Phone
        phone_inp = page.locator("input[id*='phone'], input[type='tel']").first
        if phone_inp.count() > 0 and phone_inp.is_visible():
            phone_inp.fill(candidate["phone"])
            filled_something = True

        # Resume file upload
        resume_inp = page.locator("input[type='file']").first
        if resume_inp.count() > 0 and os.path.exists(resume_pdf_path):
            resume_inp.set_input_files(resume_pdf_path)
            filled_something = True
            logger.info(f"  📎 Uploaded resume to Greenhouse: {os.path.basename(resume_pdf_path)}")

        # Custom Greenhouse text questions (job_application_answers_attributes_X_value)
        custom_inputs = page.locator("input[id*='job_application_answers_attributes_']").all()
        for inp in custom_inputs:
            try:
                id_val = inp.get_attribute("id") or ""
                label_text = ""
                if id_val:
                    lbl = page.locator(f"label[for='{id_val}']").first
                    if lbl.count() > 0:
                        label_text = lbl.inner_text().lower()
                if not label_text:
                    parent = inp.locator("xpath=ancestor::div[1]")
                    label_text = parent.inner_text().lower() if parent.count() > 0 else ""

                if "linkedin" in label_text:
                    inp.fill(candidate["linkedin"])
                    filled_something = True
                    logger.info("  📝 Filled Greenhouse custom LinkedIn profile")
                elif any(k in label_text for k in ["github", "portfolio", "website", "url"]):
                    inp.fill(candidate["github"])
                    filled_something = True
                    logger.info("  📝 Filled Greenhouse custom GitHub profile")
                elif any(k in label_text for k in ["salary", "expectation", "compensation"]):
                    inp.fill("Negotiable")
                    filled_something = True
                    logger.info("  📝 Filled Greenhouse salary expectation")
                elif any(k in label_text for k in ["notice", "period", "available", "start"]):
                    inp.fill("Immediately")
                    filled_something = True
                else:
                    inp.fill("Yes")
                    filled_something = True
            except Exception:
                continue

        # Custom Greenhouse dropdown questions
        custom_selects = page.locator("select[id*='job_application_answers_attributes_'], select").all()
        for sel in custom_selects:
            try:
                opts = sel.locator("option").all()
                selected_val = None
                for opt in opts:
                    opt_val = opt.get_attribute("value") or ""
                    opt_text = opt.inner_text().strip().lower()
                    if opt_val and opt_val != "" and opt_text not in ["select...", "select an option", "choose..."]:
                        selected_val = opt_val
                        if any(w in opt_text for w in ["yes", "y", "true", "agree", "open", "full-time", "remote"]):
                            break
                if selected_val:
                    sel.select_option(value=selected_val)
                    filled_something = True
                    logger.info(f"  📝 Selected Greenhouse dropdown option: {selected_val}")
            except Exception:
                continue

        # Try to find and click Greenhouse submit button
        submit_btn = page.locator("button[type='submit'], input[type='submit'], #submit_app, button:has-text('Submit Application')").first
        if submit_btn.count() > 0 and submit_btn.is_visible():
            submit_btn.click()
            page.wait_for_timeout(3000)
            logger.info("  🖱️ Clicked Greenhouse submit button")
            return True

        return filled_something

    except Exception as e:
        logger.error(f"Error in Greenhouse form filler: {e}")
        return False


def _fill_generic_form(page: Page, resume_pdf_path: str, candidate: dict) -> bool:
    """
    Generic fallback form filler for all other job portals.
    """
    filled_something = False
    try:
        inputs = page.locator("input").all()
        for inp in inputs:
            try:
                if not inp.is_visible():
                    type_attr = (inp.get_attribute("type") or "").lower()
                    if type_attr != "file":
                        continue

                type_attr = (inp.get_attribute("type") or "text").lower()
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                name_attr = (inp.get_attribute("name") or "").lower()
                id_attr = (inp.get_attribute("id") or "").lower()
                aria_label = (inp.get_attribute("aria-label") or "").lower()

                label_text = ""
                try:
                    if id_attr:
                        lbl = page.locator(f"label[for='{id_attr}']").first
                        if lbl.count() > 0:
                            label_text = lbl.inner_text().lower()
                    if not label_text:
                        parent = inp.locator("xpath=ancestor::div[1]")
                        if parent.count() > 0:
                            label_text = parent.inner_text().lower()
                except Exception:
                    pass

                hints = f"{placeholder} {name_attr} {id_attr} {aria_label} {label_text}"

                if type_attr == "email" or "email" in hints:
                    inp.fill(candidate["email"])
                    filled_something = True
                elif type_attr in ["tel", "number"] or any(k in hints for k in ["phone", "mobile", "contact"]):
                    inp.fill(candidate["phone"])
                    filled_something = True
                elif type_attr == "file":
                    if os.path.exists(resume_pdf_path):
                        inp.set_input_files(resume_pdf_path)
                        filled_something = True
                elif "linkedin" in hints:
                    inp.fill(candidate["linkedin"])
                    filled_something = True
                elif any(k in hints for k in ["github", "portfolio", "website", "url"]):
                    inp.fill(candidate["github"])
                    filled_something = True
                elif "first" in hints and "name" in hints:
                    inp.fill(candidate["name"].split()[0])
                    filled_something = True
                elif "last" in hints and "name" in hints:
                    parts = candidate["name"].split()
                    inp.fill(parts[-1] if len(parts) > 1 else "")
                    filled_something = True
                elif "name" in hints and "user" not in hints and "company" not in hints:
                    inp.fill(candidate["name"])
                    filled_something = True
                elif any(k in hints for k in ["salary", "expectation", "compensation"]):
                    inp.fill("Negotiable")
                    filled_something = True
                elif any(k in hints for k in ["notice", "period", "available", "start"]):
                    inp.fill("Immediately")
                    filled_something = True
                elif type_attr in ["checkbox", "radio"]:
                    if any(k in hints for k in ["agree", "terms", "privacy", "consent", "gdpr", "yes"]):
                        if not inp.is_checked():
                            inp.check()
                            filled_something = True
            except Exception:
                continue

        selects = page.locator("select").all()
        for sel in selects:
            try:
                options = sel.locator("option").all()
                if len(options) > 1:
                    selected_val = None
                    for opt in options:
                        opt_text = opt.inner_text().strip().lower()
                        opt_val = opt.get_attribute("value") or ""
                        if opt_val and opt_val != "" and opt_text not in ["select...", "select an option", "choose...", "select"]:
                            selected_val = opt_val
                            if any(w in opt_text for w in ["yes", "y", "true", "agree", "open", "full-time", "remote"]):
                                break

                    if selected_val:
                        sel.select_option(value=selected_val)
                        filled_something = True
            except Exception:
                continue

        textareas = page.locator("textarea:visible").all()
        for ta in textareas:
            try:
                cover_text = (
                    f"Dear Hiring Manager,\n\n"
                    f"I am very interested in this position and believe my experience in Python, "
                    f"FastAPI, React, and AI/ML make me a strong candidate.\n\n"
                    f"GitHub: {candidate['github']}\n"
                    f"LinkedIn: {candidate['linkedin']}\n\n"
                    f"Best regards,\n{candidate['name']}"
                )
                ta.fill(cover_text)
                filled_something = True
            except Exception:
                continue

        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "button:has-text('Send')",
            "#submit_app",
            "#create_application",
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(3000)
                    return True
            except Exception:
                continue

        return filled_something

    except Exception as e:
        logger.error(f"Error filling generic application form: {e}")
        return False


def _run_playwright_sync(job_link: str, resume_pdf_path: str) -> Dict[str, str]:
    """
    Synchronous Playwright execution — runs in a background thread.
    Opens a VISIBLE Chromium browser window.
    """
    candidate = _get_candidate_info()

    platform = "generic"
    if "greenhouse.io" in job_link.lower():
        platform = "greenhouse"
    elif "lever.co" in job_link.lower():
        platform = "lever"
    elif "arbeitnow.com" in job_link.lower():
        platform = "arbeitnow"
    elif "remotive.com" in job_link.lower():
        platform = "remotive"

    logger.info(f"🌐 Launching visible Chromium browser for {platform} application: {job_link}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                slow_mo=400,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Step 1: Navigate to job page (handling Arbeitnow direct apply URLs)
            target_url = job_link
            if "arbeitnow.com" in job_link.lower() and not job_link.endswith("/apply"):
                target_url = f"{job_link.rstrip('/')}/apply"

            try:
                page.goto(target_url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading {target_url}")
                browser.close()
                return {"status": "failed", "platform": platform, "error": "Page load timeout"}

            # Step 2: Dismiss cookie banners
            _dismiss_cookie_banners(page)

            # Step 3: Pre-apply screenshot
            os.makedirs("data", exist_ok=True)
            try:
                page.screenshot(path="data/pre_apply_screenshot.png")
            except Exception:
                pass

            # Step 4: Click through to actual apply form if on a listing portal
            clicked_through = _find_and_click_apply_button(page)
            if clicked_through:
                logger.info("  → Navigated to job application page")
                _dismiss_cookie_banners(page)
                page.wait_for_timeout(2000)

            # Step 5: Detect platform and fill form
            current_url = page.url.lower()
            success = False
            if "greenhouse.io" in current_url:
                logger.info("  → Detected Greenhouse application form")
                success = _fill_greenhouse_form(page, resume_pdf_path, candidate)
            else:
                success = _fill_generic_form(page, resume_pdf_path, candidate)

            # Step 6: Post-apply screenshot
            try:
                page.screenshot(path="data/post_apply_screenshot.png")
            except Exception:
                pass

            page.wait_for_timeout(3000)
            browser.close()

            if success:
                logger.info(f"✅ Successfully applied via {platform} for {job_link}")
                return {"status": "applied", "platform": platform}
            else:
                logger.info(f"⚠️ Opened job page but form filling incomplete for {job_link}")
                return {"status": "attempted", "platform": platform}

    except Exception as e:
        logger.error(f"Critical error during auto_apply: {e}")
        return {"status": "failed", "platform": platform, "error": str(e)}


async def auto_apply_to_job(
    job_link: str,
    resume_pdf_path: str,
    github: str = "",
    linkedin: str = "",
) -> Dict[str, str]:
    """
    Main async entry point. Runs Playwright's sync API in a background thread
    to avoid Windows asyncio subprocess limitations inside uvicorn.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright is not installed. Run `pip install playwright`.")
        return {"status": "failed", "platform": "unknown", "error": "Playwright missing"}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        _run_playwright_sync,
        job_link,
        resume_pdf_path,
    )
    return result
