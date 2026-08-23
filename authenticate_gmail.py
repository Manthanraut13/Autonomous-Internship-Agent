"""
authenticate_gmail.py
---------------------
Generates or refreshes token.json using credentials.json via Google OAuth 2.0.
Run this script whenever you need to re-authenticate with Google Cloud.

Usage:
    python authenticate_gmail.py
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


def authenticate():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Error: '{CREDENTIALS_FILE}' not found in project root.")
        print("Download your OAuth Client JSON from Google Cloud Console and save it as credentials.json.")
        sys.exit(1)

    print("🔑 Initiating Google OAuth 2.0 Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    
    try:
        creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"✅ Successfully authenticated! Fresh token saved to '{TOKEN_FILE}'.")
        print("Emails will now send automatically via your Gmail API integration.")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    authenticate()
