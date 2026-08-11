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

    # 2. Fallback to Gmail API (OAuth 2.0)
    credentials_path = settings.gmail_credentials_file
    token_path = settings.gmail_token_file
    
    if os.path.exists(credentials_path) or os.path.exists(token_path):
        try:
            logger.info("Attempting to send email via Gmail API (OAuth 2.0)...")
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            SCOPES = ['https://www.googleapis.com/auth/gmail.send']
            creds = None
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                    
            service = build('gmail', 'v1', credentials=creds)
            
            msg = EmailMessage()
            msg['Subject'] = subject
            # Use "me" for Gmail API unless user specifies sender_email
            msg['From'] = settings.sender_email if settings.sender_email != "noreply@internshipagent.com" else "me"
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

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            body = {'raw': raw_message}
            
            sent_message = service.users().messages().send(userId='me', body=body).execute()
            logger.info(f"Gmail API email sent successfully to {recipient}. Message Id: {sent_message.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Gmail API fallback failed: {e}")
            return False

    logger.warning("No email provider configured (SendGrid API key or Gmail OAuth credentials missing).")
    return False
