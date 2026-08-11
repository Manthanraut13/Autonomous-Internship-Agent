import os
import sys
import base64
import logging
from email.message import EmailMessage

from config.settings import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

def test_oauth():
    credentials_path = settings.gmail_credentials_file
    token_path = settings.gmail_token_file
    
    if not os.path.exists(credentials_path):
        logger.error(f"Cannot find '{credentials_path}'. Please download it from Google Cloud Console and place it in this folder.")
        sys.exit(1)
        
    logger.info("Starting Gmail OAuth 2.0 flow...")
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None
    
    if os.path.exists(token_path):
        logger.info(f"Loading existing tokens from '{token_path}'...")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            logger.info("No valid token found. A browser window should open to request authorization.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            logger.info(f"Saved new token to '{token_path}'")
            
    logger.info("Authentication successful! Building Gmail service...")
    service = build('gmail', 'v1', credentials=creds)
    
    msg = EmailMessage()
    msg['Subject'] = "Test Email from Autonomous Internship Agent"
    msg['From'] = "me"
    msg['To'] = settings.recipient_email
    msg.set_content("If you are reading this, your Gmail OAuth 2.0 integration is working perfectly!")
    
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body = {'raw': raw_message}
    
    try:
        sent_message = service.users().messages().send(userId='me', body=body).execute()
        logger.info(f"Test email sent successfully! Message Id: {sent_message.get('id')}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    test_oauth()
