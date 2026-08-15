"""
tools/whatsapp_handler.py
-------------------------
WhatsApp integration using the Twilio SDK to send notifications
and daily summaries to the user. One-way only — no incoming webhooks.
"""

import logging
from typing import List, Dict, Any
import sys
import os

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


def send_whatsapp_notification(phone: str, message_body: str) -> str:
    """
    Sends a simple one-way notification to WhatsApp.

    Args:
        phone: The recipient's WhatsApp number (E.164 format).
        message_body: The text message to send.

    Returns:
        The Twilio Message SID if successful, empty string otherwise.
    """
    try:
        client = _get_twilio_client()
        to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
        from_number = settings.whatsapp_from

        message = client.messages.create(
            from_=from_number,
            body=message_body,
            to=to_number
        )
        logger.info(f"WhatsApp notification sent. SID: {message.sid}")
        return message.sid

    except TwilioRestException as e:
        logger.error(f"Twilio API Error sending notification: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error sending WhatsApp notification: {e}")
        return ""


def send_whatsapp_summary(phone: str, matched_jobs: List[Dict[str, Any]]) -> bool:
    """
    Sends a daily summary of job matches via WhatsApp.

    Args:
        phone: The recipient's WhatsApp number (E.164 format).
        matched_jobs: A list of matched job dicts from the pipeline.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    match_count = len(matched_jobs)

    if match_count == 0:
        message_body = (
            "📊 *Internship Report*\n\n"
            "No new internships met your threshold today. We'll keep looking! 🕵️‍♂️"
        )
    else:
        message_body = (
            f"📊 *Internship Report Ready!*\n\n"
            f"Found {match_count} matching internships in the last 24h.\n"
            f"📧 CSV report sent to {settings.recipient_email}\n\n"
            f"*Top matches:*\n"
        )
        for job in matched_jobs[:5]:
            company = job.get("company", "Unknown")
            title = job.get("title", "")
            score = job.get("match_score", 0)
            message_body += f"• {company} — {title} ({score}/100)\n"

        if match_count > 5:
            message_body += f"\n...and {match_count - 5} more."

    return bool(send_whatsapp_notification(phone, message_body))
