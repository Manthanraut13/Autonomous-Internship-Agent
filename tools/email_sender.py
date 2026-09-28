"""
tools/email_sender.py
---------------------
Sends emails with CSV attachments.
Multi-tier fallback architecture:
  1. Gmail SMTP (App Password) - 100% reliable, never expires, no domain verification needed
  2. SendGrid API - High volume transactional delivery
  3. Gmail API (OAuth 2.0) - Token-based delivery
"""

import os
import base64
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Attachment, FileContent, FileName, FileType, Disposition
    )
except ImportError:
    SendGridAPIClient = None

from config.settings import settings

logger = logging.getLogger(__name__)


def _send_via_smtp(csv_path: str, job_count: int, recipient: str, subject: str, html_content: str) -> bool:
    """
    Sends email via standard Gmail SMTP using an App Password.
    This is the most reliable method as it never expires and requires no DNS verification.
    """
    smtp_user = settings.gmail_user or settings.sender_email or settings.recipient_email
    smtp_pass = settings.gmail_app_password

    if not smtp_pass or not smtp_user or smtp_user == "your-email@domain.com" or smtp_user == "noreply@internshipagent.com":
        return False

    try:
        logger.info(f"Attempting email delivery via Gmail SMTP ({settings.smtp_host}:{settings.smtp_port}) using {smtp_user}...")

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = recipient
        msg.set_content("Please enable HTML viewing to read your daily internship report.")
        msg.add_alternative(html_content, subtype='html')

        with open(csv_path, 'rb') as f:
            csv_data = f.read()

        msg.add_attachment(
            csv_data,
            maintype='text',
            subtype='csv',
            filename=os.path.basename(csv_path)
        )

        # Connect with TLS
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"✅ Gmail SMTP email successfully delivered to {recipient}!")
        return True
    except Exception as e:
        logger.warning(f"Gmail SMTP delivery failed: {e}")
        return False


def _send_via_sendgrid(csv_path: str, job_count: int, recipient: str, subject: str, html_content: str) -> bool:
    """Sends email via SendGrid API."""
    if not settings.sendgrid_api_key or not SendGridAPIClient:
        return False

    # Check if sender_email is a placeholder
    sender = settings.sender_email
    if not sender or sender in ["your-email@domain.com", "noreply@internshipagent.com"]:
        logger.warning("SendGrid skipped: SENDER_EMAIL is set to a placeholder. Set a verified SendGrid sender address.")
        return False

    try:
        logger.info("Attempting email delivery via SendGrid...")
        message = Mail(
            from_email=sender,
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
            logger.info(f"✅ SendGrid email successfully delivered to {recipient}")
            return True
        else:
            logger.warning(f"SendGrid returned unexpected status: {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"SendGrid delivery failed: {e}")
        return False


def _send_via_gmail_oauth(csv_path: str, job_count: int, recipient: str, subject: str, html_content: str) -> bool:
    """Sends email via Google Gmail API OAuth 2.0 credentials."""
    credentials_path = settings.gmail_credentials_file
    token_path = settings.gmail_token_file

    if not os.path.exists(token_path) and not os.path.exists(credentials_path):
        return False

    try:
        logger.info("Attempting email delivery via Gmail API (OAuth 2.0)...")
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        creds = None

        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            except Exception as load_err:
                logger.warning(f"Could not load token.json: {load_err}")

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'w') as token_file:
                    token_file.write(creds.to_json())
                logger.info("Gmail OAuth token refreshed successfully.")
            except Exception as refresh_err:
                logger.warning(f"Gmail OAuth token refresh failed (likely expired/revoked): {refresh_err}")
                creds = None

        if not creds or not creds.valid:
            logger.warning("Gmail OAuth credentials invalid or expired.")
            return False
                
        service = build('gmail', 'v1', credentials=creds)
        
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = "me"
        msg['To'] = recipient
        msg.set_content("Please enable HTML viewing to read your daily internship report.")
        msg.add_alternative(html_content, subtype='html')

        with open(csv_path, 'rb') as f:
            csv_data = f.read()

        msg.add_attachment(
            csv_data,
            maintype='text',
            subtype='csv',
            filename=os.path.basename(csv_path)
        )

        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body = {'raw': raw_message}
        
        sent_message = service.users().messages().send(userId='me', body=body).execute()
        logger.info(f"✅ Gmail API email sent successfully to {recipient}. Message ID: {sent_message.get('id')}")
        return True
        
    except Exception as e:
        logger.warning(f"Gmail API OAuth delivery failed: {e}")
        return False


def send_csv_email(csv_path: str, job_count: int) -> bool:
    """
    Sends the generated CSV report file to the configured recipient email.
    Tries Gmail SMTP (App Password) -> SendGrid -> Gmail OAuth in priority order.
    """
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found for email delivery: {csv_path}")
        return False

    recipient = settings.recipient_email or "manthanr141@gmail.com"
    subject = f"Autonomous Internship Agent: {job_count} Qualified India AI Matches!"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f6fa; margin: 0; padding: 24px; color: #0f1c2b; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #d4dde8; padding: 32px; }}
        .header {{ border-bottom: 2px solid #eef4ff; padding-bottom: 20px; margin-bottom: 24px; }}
        .title {{ font-size: 22px; font-weight: 700; color: #136299; margin: 0 0 8px 0; }}
        .subtitle {{ font-size: 14px; color: #576579; margin: 0; }}
        .highlight-box {{ background: #f0f7ff; border-left: 4px solid #136299; padding: 16px; border-radius: 6px; margin: 20px 0; }}
        .count {{ font-size: 28px; font-weight: 800; color: #0f1c2b; }}
        .footer {{ margin-top: 32px; padding-top: 20px; border-top: 1px solid #e4efff; font-size: 12px; color: #8a99ad; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1 class="title">Autonomous Internship Agent</h1>
          <p class="subtitle">Daily AI, GenAI & ML Job Intelligence (India Only)</p>
        </div>
        
        <p>Hello <strong>{settings.candidate_name}</strong>,</p>
        <p>Your scheduled pipeline has scanned job portals across India with strict location verification (Full-time, Part-time, Contract, Internship, On-site, Hybrid, Remote in India).</p>
        
        <div class="highlight-box">
          <div class="count">{job_count}</div>
          <p style="margin: 4px 0 0 0; font-weight: 600; color: #136299;">Verified India AI Openings Discovered</p>
        </div>

        <p>The full structured breakdown including Match Scores, Reasoning, Key Skills, Role Types, Work Modes, and Direct Apply links is attached as a CSV report.</p>
        <p>You can also review, track, and manage all applications in real time on your <a href="http://localhost:8000/dashboard" style="color: #136299; font-weight: 600;">Glacial Precision Dashboard</a>.</p>
        
        <div class="footer">
          <p>Autonomous Internship Agent • India AI Career Intelligence</p>
        </div>
      </div>
    </body>
    </html>
    """

    # 1. Try Gmail SMTP with App Password (Most reliable, never expires)
    if _send_via_smtp(csv_path, job_count, recipient, subject, html_content):
        return True

    # 2. Try SendGrid API
    if _send_via_sendgrid(csv_path, job_count, recipient, subject, html_content):
        return True

    # 3. Try Gmail API OAuth 2.0
    if _send_via_gmail_oauth(csv_path, job_count, recipient, subject, html_content):
        return True

    # Detailed setup instruction log if all fail
    logger.error(
        "❌ Email delivery could not be completed because no email provider is configured or authorized.\n"
        "To enable instant email delivery:\n"
        "1. Option A (Recommended - 1 minute): Generate a Gmail App Password:\n"
        "   - Go to https://myaccount.google.com/apppasswords\n"
        "   - Create an app password named 'Internship Agent'\n"
        "   - Add to your .env file:\n"
        "     GMAIL_USER=manthanr141@gmail.com\n"
        "     GMAIL_APP_PASSWORD=your-16-char-app-password\n"
        "2. Option B: Configure SendGrid with a verified sender email in .env:\n"
        "     SENDER_EMAIL=your-verified-sender@domain.com\n"
        "     SENDGRID_API_KEY=SG.your_sendgrid_api_key\n"
    )
    return False

