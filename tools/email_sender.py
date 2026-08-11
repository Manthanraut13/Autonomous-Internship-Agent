"""
tools/email_sender.py
---------------------
Sends emails with CSV attachments.
Supports SendGrid (if configured) or fallback to Gmail SMTP.
"""

import logging
import os
import base64
from email.message import EmailMessage
import smtplib

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName, FileType, Disposition
    )
except ImportError:
    SendGridAPIClient = None

from config.settings import settings

logger = logging.getLogger(__name__)


def send_csv_email(csv_path: str, job_count: int) -> bool:
    """
    Sends the generated CSV file via email to the configured recipient.
    Prefers SendGrid if available; falls back to Gmail SMTP.
    """
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return False

    recipient = settings.recipient_email
    subject = f"Autonomous Internship Agent: {job_count} New Matches!"
    html_content = f"""
    <h3>Your Internship Report is Ready</h3>
    <p>We found <strong>{job_count}</strong> new matching internships in the last 24 hours.</p>
    <p>Please find the attached CSV for direct apply links and match details.</p>
    <p>Happy applying!</p>
    """

    # 1. Try SendGrid First
    if settings.sendgrid_api_key and SendGridAPIClient:
        try:
            logger.info("Attempting to send email via SendGrid...")
            message = Mail(
                from_email=settings.sender_email,
                to_emails=recipient,
                subject=subject,
                html_content=html_content
            )
            
            with open(csv_path, 'rb') as f:
                data = f.read()
                encoded_file = base64.b64encode(data).decode()
                
            attached_file = Attachment(
                FileContent(encoded_file),
                FileName(os.path.basename(csv_path)),
                FileType('text/csv'),
                Disposition('attachment')
            )
            message.attachment = attached_file
            
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            response = sg.send(message)
            if response.status_code in (200, 201, 202):
                logger.info(f"SendGrid email sent successfully to {recipient}")
                return True
            else:
                logger.error(f"SendGrid returned unexpected status: {response.status_code}")
        except Exception as e:
            logger.error(f"SendGrid failed: {e}")

    # 2. Fallback to Gmail SMTP
    if settings.gmail_app_password and settings.gmail_user:
        try:
            logger.info("Attempting to send email via Gmail SMTP...")
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = settings.gmail_user
            msg['To'] = recipient
            msg.set_content("Please enable HTML viewing to see this message.")
            msg.add_alternative(html_content, subtype='html')

            with open(csv_path, 'rb') as f:
                csv_data = f.read()

            msg.add_attachment(
                csv_data,
                maintype='text',
                subtype='csv',
                filename=os.path.basename(csv_path)
            )

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.gmail_user, settings.gmail_app_password)
                server.send_message(msg)

            logger.info(f"SMTP email sent successfully to {recipient}")
            return True

        except Exception as e:
            logger.error(f"SMTP fallback failed: {e}")
            return False

    logger.warning("No email provider configured (SendGrid API key or Gmail SMTP credentials missing).")
    return False
