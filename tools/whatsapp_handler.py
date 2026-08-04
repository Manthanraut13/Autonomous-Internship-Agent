"""
tools/whatsapp_handler.py
-------------------------
WhatsApp integration using the Twilio SDK to send approval requests
and daily summaries to the user.
"""

import logging
from typing import List, Dict, Any


import sys, os
# Ensure project root is on the import path so `config.settings` can be imported
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
except ImportError:
    Client = None
    TwilioRestException = Exception

from config.settings import settings

logger = logging.getLogger(__name__)


def _get_twilio_client() -> Client:
    """Initialise and return the Twilio REST client."""
    if Client is None:
        raise ImportError("Twilio SDK not installed. Run `pip install twilio`.")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_whatsapp_approval(
    phone: str,
    job_title: str,
    company: str,
    match_score: float,
    job_link: str = "",
    location: str = "",
) -> str:
    """
    Sends a WhatsApp message asking the user for approval to apply to a job.

    Args:
        phone (str): The recipient's WhatsApp number (E.164 format).
        job_title (str): Title of the internship/job.
        company (str): Name of the company.
        match_score (float): The calculated match score (0-100).
        job_link (str): URL to the job listing.
        location (str): Job location.

    Returns:
        str: The Twilio Message SID if successful.
    """
    try:
        client = _get_twilio_client()
        
        # Ensure the phone numbers start with 'whatsapp:'
        to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        from_number = settings.whatsapp_from
        
        message_body = (
            f"🎯 *New Match Alert!*\n\n"
            f"💼 *{company}*\n"
            f"📌 {job_title}\n"
            f"⭐ Match Score: {int(match_score)}/100\n"
        )
        if location:
            message_body += f"📍 {location}\n"
        if job_link:
            message_body += f"🔗 {job_link}\n"
        message_body += f"\nReply *yes* to apply, or *no* to skip."

        message = client.messages.create(
            from_=from_number,
            body=message_body,
            to=to_number
        )
        
        logger.info(f"WhatsApp approval sent for {company}. SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending approval: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error sending WhatsApp approval: {e}")
        return ""


def send_whatsapp_confirmation(phone: str, job_title: str, company: str) -> str:
    """
    Sends a WhatsApp message confirming that an application was successfully submitted.

    Args:
        phone (str): The recipient's WhatsApp number (E.164 format).
        job_title (str): Title of the internship/job.
        company (str): Name of the company.

    Returns:
        str: The Twilio Message SID if successful.
    """
    try:
        client = _get_twilio_client()
        to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        from_number = settings.whatsapp_from

        message_body = (
            f"🎉 *Successfully Applied!*\n\n"
            f"💼 *{company}*\n"
            f"📌 {job_title}\n\n"
            f"Your application has been submitted! 🚀"
        )

        message = client.messages.create(
            from_=from_number,
            body=message_body,
            to=to_number
        )

        logger.info(f"WhatsApp application confirmation sent for {company}. SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending confirmation: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error sending WhatsApp confirmation: {e}")
        return ""


def send_whatsapp_summary(phone: str, applications: List[Dict[str, Any]]) -> bool:
    """
    Sends a daily summary of job applications via WhatsApp.

    Args:
        phone (str): The recipient's WhatsApp number (E.164 format).
        applications (List[Dict[str, Any]]): A list of dictionaries representing
            applied jobs (expected keys: 'company', 'job_title', 'match_score').

    Returns:
        bool: True if the message was sent successfully, False otherwise.
    """
    try:
        client = _get_twilio_client()
        
        to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        from_number = settings.whatsapp_from
        
        applied_count = len(applications)
        
        if applied_count == 0:
            message_body = "📊 *Daily Summary*\n\nNo applications were submitted today. We'll keep looking! 🕵️‍♂️"
        else:
            message_body = f"📊 *Daily Summary*\n\n✅ Applied to {applied_count} internships today:\n\n"
            
            # Add up to 5 jobs to keep the message concise
            for app in applications[:5]:
                company = app.get("company", "Unknown")
                score = app.get("match_score", 0)
                message_body += f"▪️ {company} (Score: {score})\n"
                
            if applied_count > 5:
                message_body += f"\n...and {applied_count - 5} more."
                
            message_body += "\n\nFingers crossed! 🤞"

        message = client.messages.create(
            from_=from_number,
            body=message_body,
            to=to_number
        )
        
        logger.info(f"WhatsApp summary sent. SID: {message.sid}")
        return True

    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending summary: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending WhatsApp summary: {e}")
        return False
