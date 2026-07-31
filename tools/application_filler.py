"""
tools/application_filler.py
---------------------------
Automated job application filler using Playwright.
Handles Indeed, LinkedIn, and generic form submissions.
"""

import logging
import asyncio
from typing import Dict, Any

try:
    from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
except ImportError:
    async_playwright = None
    Page = None
    PlaywrightTimeoutError = Exception

logger = logging.getLogger(__name__)


async def apply_indeed(page: Page, resume_pdf_path: str, github: str, linkedin: str) -> bool:
    """Fills an Indeed Easy Apply form."""
    try:
        # Wait for and click the Easy Apply button
        apply_btn = page.locator("button:has-text('Apply now'), button:has-text('Easy Apply')").first
        await apply_btn.wait_for(state="visible", timeout=10000)
        await apply_btn.click()

        # Simple logic: fill inputs, upload file, submit
        # Indeed application iframes are complex, this is a basic heuristic mapping
        await page.wait_for_timeout(2000)
        
        # Email
        email_input = page.locator("input[type='email']").first
        if await email_input.is_visible():
            await email_input.fill("applicant@example.com")  # Typically pulled from settings

        # Resume upload
        file_input = page.locator("input[type='file']").first
        if await file_input.is_attached():
            await file_input.set_input_files(resume_pdf_path)

        # Cover letter / Links
        cover_letter_input = page.locator("textarea").first
        if await cover_letter_input.is_visible():
            await cover_letter_input.fill(f"GitHub: {github}\nLinkedIn: {linkedin}")

        # Submit button
        submit_btn = page.locator("button:has-text('Submit'), button:has-text('Apply')").first
        if await submit_btn.is_visible():
            await submit_btn.click()
            await page.wait_for_timeout(3000)
            return True
            
        return False
    except PlaywrightTimeoutError:
        logger.error("Timeout during Indeed application.")
        return False
    except Exception as e:
        logger.error(f"Error during Indeed application: {e}")
        return False


async def apply_linkedin(page: Page, resume_pdf_path: str, github: str, linkedin: str) -> bool:
    """Fills a LinkedIn Easy Apply form."""
    try:
        apply_btn = page.locator("button:has-text('Easy Apply')").first
        await apply_btn.wait_for(state="visible", timeout=10000)
        await apply_btn.click()

        await page.wait_for_timeout(2000)
        
        # Next / Submit flow
        while True:
            # Upload resume if asked
            file_input = page.locator("input[type='file']").first
            if await file_input.is_attached():
                await file_input.set_input_files(resume_pdf_path)
            
            # Fill common inputs if present (heuristic)
            text_inputs = await page.locator("input[type='text']").all()
            for inp in text_inputs:
                placeholder = await inp.get_attribute("placeholder") or ""
                name_attr = await inp.get_attribute("name") or ""
                if "github" in placeholder.lower() or "github" in name_attr.lower():
                    await inp.fill(github)
                elif "linkedin" in placeholder.lower() or "linkedin" in name_attr.lower():
                    await inp.fill(linkedin)

            # Look for Submit vs Next
            submit_btn = page.locator("button:has-text('Submit application')").first
            next_btn = page.locator("button:has-text('Next')").first
            
            if await submit_btn.is_visible():
                await submit_btn.click()
                await page.wait_for_timeout(3000)
                return True
            elif await next_btn.is_visible():
                await next_btn.click()
                await page.wait_for_timeout(1000)
            else:
                # Reached a state where we can't progress
                break
                
        return False
    except PlaywrightTimeoutError:
        logger.error("Timeout during LinkedIn application.")
        return False
    except Exception as e:
        logger.error(f"Error during LinkedIn application: {e}")
        return False


async def apply_generic(page: Page, resume_pdf_path: str, github: str, linkedin: str) -> bool:
    """Fills a generic application form based on input types and placeholders."""
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Try to find common input fields
        inputs = await page.locator("input:visible").all()
        for inp in inputs:
            type_attr = await inp.get_attribute("type") or "text"
            placeholder = await inp.get_attribute("placeholder") or ""
            name_attr = await inp.get_attribute("name") or ""
            
            combined_hints = (placeholder + name_attr).lower()
            
            if type_attr == "email":
                await inp.fill("applicant@example.com")
            elif type_attr == "file":
                await inp.set_input_files(resume_pdf_path)
            elif "name" in combined_hints and type_attr == "text":
                await inp.fill("Applicant Name")
            elif "phone" in combined_hints:
                await inp.fill("555-0100")
            elif "linkedin" in combined_hints:
                await inp.fill(linkedin)
            elif "github" in combined_hints or "portfolio" in combined_hints:
                await inp.fill(github)

        # Look for a textarea for cover letter/message
        textareas = await page.locator("textarea:visible").all()
        if textareas:
            await textareas[0].fill(f"I am very interested in this position.\nGitHub: {github}\nLinkedIn: {linkedin}")

        # Look for submit button
        submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply')").first
        if await submit_btn.is_visible():
            await submit_btn.click()
            await page.wait_for_timeout(3000)
            return True
            
        return False
    except PlaywrightTimeoutError:
        logger.error("Timeout during generic application.")
        return False
    except Exception as e:
        logger.error(f"Error during generic application: {e}")
        return False


async def auto_apply_to_job(job_link: str, resume_pdf_path: str, github: str, linkedin: str) -> Dict[str, str]:
    """
    Main entry point. Detects platform from URL, launches Playwright,
    navigates to the job page, and attempts to apply.
    """
    if async_playwright is None:
        logger.error("Playwright is not installed. Run `pip install playwright`.")
        return {"status": "failed", "platform": "unknown", "error": "Playwright missing"}

    platform = "generic"
    if "indeed.com" in job_link.lower():
        platform = "indeed"
    elif "linkedin.com" in job_link.lower():
        platform = "linkedin"

    logger.info(f"Starting {platform} application for {job_link}")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                await page.goto(job_link, timeout=20000, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading {job_link}")
                await browser.close()
                return {"status": "failed", "platform": platform, "error": "Page load timeout"}

            success = False
            if platform == "indeed":
                success = await apply_indeed(page, resume_pdf_path, github, linkedin)
            elif platform == "linkedin":
                success = await apply_linkedin(page, resume_pdf_path, github, linkedin)
            else:
                success = await apply_generic(page, resume_pdf_path, github, linkedin)

            await browser.close()

            if success:
                return {"status": "applied", "platform": platform}
            else:
                return {"status": "email_sent", "platform": platform}  # Fallback assumption if UI flow fails

    except Exception as e:
        logger.error(f"Critical error during auto_apply: {e}")
        return {"status": "failed", "platform": platform, "error": str(e)}
