"""
This module provides advanced configurations and email source integrations
for the Newsletter Email Parser project.

Examples:
- Gmail API integration with OAuth2
- IMAP integration (local email clients)
- Custom email sources (RSS feeds to email)
- Batch processing strategies
"""

import imaplib
import email
import base64
import os
import pickle
from typing import List
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION PROFILES
# ============================================================================

class ParserConfig:
    """Base configuration for newsletter parser"""
    
    # Free Tier Limits
    MAX_REQUESTS_PER_MINUTE = 10
    MAX_TOKENS_PER_MINUTE = 250_000
    MAX_REQUESTS_PER_DAY = 500
    
    # Optimal settings
    SAFE_REQUEST_INTERVAL = 6  # seconds (conservative: 10 requests/min)
    BATCH_SIZE = 10  # emails per batch
    BATCH_INTERVAL = 300  # 5 minutes between batches
    
    # Content limits (to manage token usage)
    MAX_EMAIL_LENGTH = 800  # characters to analyze
    MAX_SUMMARY_LENGTH = 200  # tokens in output
    
    # Categories for classification
    CATEGORIES = [
        "Self-Care & Wellness",
        "Artificial Intelligence",
        "General Tech Updates",
        "Data Science & ML",
        "Web Development",
        "Cloud Computing",
        "Security & Privacy",
        "Product Updates",
        "Career & Industry News",
        "Other"
    ]
    
    # Confidence thresholds
    MIN_CLASSIFICATION_CONFIDENCE = 0.4
    DUPLICATE_THRESHOLD = 0.85  # semantic similarity

class EmailSourceConfig:
    """Configuration for different email sources"""
    
    # Gmail configuration
    GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    GMAIL_QUERY = 'subject:newsletter OR subject:"weekly digest" OR label:newsletters'
    
    # IMAP configuration
    IMAP_SERVERS = {
        'gmail': 'imap.gmail.com',
        'outlook': 'outlook.office365.com',
        'yahoo': 'imap.mail.yahoo.com',
        'custom': None  # Specify manually
    }
    
    # Search queries by source
    SEARCH_QUERIES = {
        'gmail': 'SUBJECT "newsletter" SINCE {date}',
        'outlook': 'SUBJECT "newsletter"',
        'generic': 'ALL'
    }

# ============================================================================
# GMAIL API INTEGRATION (OAuth2)
# ============================================================================

class GmailEmailSource:
    """
    Fetch newsletters from Gmail using Gmail API with OAuth2.
    
    Setup:
    1. Go to Google Cloud Console
    2. Create project and enable Gmail API
    3. Create OAuth2 credentials (Desktop app)
    4. Download credentials.json
    5. First run will prompt for OAuth2 consent
    """
    
    def __init__(self, credentials_file='credentials.json', token_file='token.pickle'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
    
    def authenticate(self):
        """Authenticate and get Gmail service"""
        from google.auth.oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.api_python_client import build
        
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file,
                    EmailSourceConfig.GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save for next time
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
        return self.service
    
    def fetch_newsletters(self, max_results=10):
        """
        Fetch newsletter emails from Gmail.
        
        Args:
            max_results: Maximum emails to fetch (max 500 per API call)
        
        Returns:
            List of Email objects
        """
        if not self.service:
            self.authenticate()
        
        from newsletter_parser import Email
        
        emails = []
        
        try:
            # Search for newsletters
            results = self.service.users().messages().list(
                userId='me',
                q=EmailSourceConfig.GMAIL_QUERY,
                maxResults=min(max_results, 500)
            ).execute()
            
            messages = results.get('messages', [])
            print(f"📧 Found {len(messages)} newsletters in Gmail")
            
            for msg_id in messages:
                try:
                    # Get full message
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_id['id'],
                        format='full'
                    ).execute()
                    
                    # Extract headers
                    headers = msg['payload'].get('headers', [])
                    subject = self._get_header(headers, 'Subject')
                    sender = self._get_header(headers, 'From')
                    date = self._get_header(headers, 'Date')
                    
                    # Extract body
                    content = self._get_body(msg['payload'])
                    
                    emails.append(Email(
                        sender=sender,
                        subject=subject,
                        content=content[:800],  # Truncate for token limits
                        date=date,
                        message_id=msg_id['id']
                    ))
                
                except Exception as e:
                    print(f"  ⚠️  Error processing message: {e}")
                    continue
            
            print(f"✅ Fetched {len(emails)} valid newsletters")
            return emails
        
        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            return []
    
    @staticmethod
    def _get_header(headers, name):
        """Get header value by name"""
        for h in headers:
            if h['name'] == name:
                return h['value']
        return "Unknown"
    
    @staticmethod
    def _get_body(payload):
        """Extract body from Gmail payload"""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        
        data = payload['body'].get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8')
        
        return "No content"

# ============================================================================
# IMAP INTEGRATION (Local Email Clients)
# ============================================================================

class ImapEmailSource:
    """
    Fetch newsletters from any IMAP-enabled email server.
    Works with Gmail, Outlook, Yahoo, and custom servers.
    
    No OAuth2 required - just email and password.
    """
    
    def __init__(self, email_address, password, imap_server='imap.gmail.com', port=993):
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.mail = None
    
    def connect(self):
        """Connect to IMAP server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.port)
            self.mail.login(self.email_address, self.password)
            print(f"✅ Connected to {self.imap_server}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def fetch_newsletters(self, mailbox='INBOX', max_results=20):
        """
        Fetch newsletters from IMAP mailbox.
        
        Args:
            mailbox: Mailbox name (e.g., 'INBOX', 'Newsletters', 'Important')
            max_results: Maximum emails to fetch
        
        Returns:
            List of Email objects
        """
        if not self.mail:
            if not self.connect():
                return []
        
        from newsletter_parser import Email
        
        emails = []
        
        try:
            # Select mailbox
            self.mail.select(mailbox)
            
            # Search for newsletter emails
            _, message_numbers = self.mail.search(
                None, 
                'OR SUBJECT newsletter SUBJECT "weekly digest"'
            )
            
            msg_list = message_numbers[0].split()[:max_results]
            print(f"📧 Found {len(msg_list)} newsletters")
            
            for num in msg_list:
                try:
                    _, msg_data = self.mail.fetch(num, '(RFC822)')
                    email_msg = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract parts
                    subject = email_msg.get('Subject', 'No Subject')
                    sender = email_msg.get('From', 'Unknown Sender')
                    date = email_msg.get('Date', datetime.now().isoformat())
                    
                    # Get body
                    content = self._get_email_body(email_msg)
                    
                    emails.append(Email(
                        sender=sender,
                        subject=subject,
                        content=content[:800],
                        date=date,
                        message_id=num.decode() if isinstance(num, bytes) else num
                    ))
                
                except Exception as e:
                    print(f"  ⚠️  Error processing message: {e}")
                    continue
            
            print(f"✅ Fetched {len(emails)} valid newsletters")
            return emails
        
        except Exception as e:
            print(f"❌ Error fetching emails: {e}")
            return []
        
        finally:
            if self.mail:
                self.mail.close()
    
    @staticmethod
    def _get_email_body(email_msg):
        """Extract plain text body from email"""
        body = ""
        
        if email_msg.is_multipart():
            for part in email_msg.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode('utf-8')
                        break
                    except:
                        pass
        else:
            try:
                body = email_msg.get_payload(decode=True).decode('utf-8')
            except:
                body = email_msg.get_payload()
        
        return body or "No content"

# ============================================================================
# BATCH PROCESSING STRATEGIES
# ============================================================================

class BatchProcessingStrategy:
    """Strategies for processing newsletters while respecting rate limits"""
    
    @staticmethod
    def conservative_batch(emails: List, batch_size=10):
        """
        Conservative strategy: 1 email every 6 seconds.
        Safe for free tier (10 RPM).
        
        Total time: batch_size * 6 seconds
        """
        import time
        
        for i, email in enumerate(emails):
            if i > 0:
                wait_time = ParserConfig.SAFE_REQUEST_INTERVAL
                print(f"⏳ Rate limiting... waiting {wait_time}s")
                time.sleep(wait_time)
            
            yield email
    
    @staticmethod
    def batched_processing(emails: List, batch_size=10):
        """
        Batch strategy: Process batches with longer waits.
        
        Processes 10 emails with 1 min waiting between batches.
        Good for processing hundreds of newsletters.
        """
        import time
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i+batch_size]
            
            if i > 0:
                wait_time = ParserConfig.BATCH_INTERVAL
                print(f"\n⏳ Batch complete. Waiting {wait_time}s before next batch...")
                time.sleep(wait_time)
            
            yield batch
    
    @staticmethod
    def scheduled_processing(emails: List, per_hour=60):
        """
        Scheduled strategy: Spread processing throughout the day.
        
        Processes `per_hour` emails per hour.
        Good for 24/7 newsletter monitoring.
        """
        import time
        from datetime import datetime
        
        interval = 3600 / per_hour  # seconds between emails
        
        for i, email in enumerate(emails):
            if i > 0:
                next_time = datetime.now().timestamp() + interval
                while datetime.now().timestamp() < next_time:
                    wait = next_time - datetime.now().timestamp()
                    if wait > 0:
                        time.sleep(min(wait, 1))
            
            yield email

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
# Example 1: Using Gmail API
from advanced_config import GmailEmailSource
from newsletter_parser import NewsletterParserOrchestrator

gmail = GmailEmailSource('credentials.json')
emails = gmail.fetch_newsletters(max_results=20)

orchestrator = NewsletterParserOrchestrator()
results = orchestrator.parse_batch(emails)
print(orchestrator.get_minimalist_display())


# Example 2: Using IMAP
from advanced_config import ImapEmailSource
from newsletter_parser import NewsletterParserOrchestrator

imap = ImapEmailSource(
    email_address='your_email@gmail.com',
    password='your_app_password',
    imap_server='imap.gmail.com'
)
emails = imap.fetch_newsletters(mailbox='Newsletters', max_results=30)

orchestrator = NewsletterParserOrchestrator()
results = orchestrator.parse_batch(emails)


# Example 3: Batch processing with rate limiting
from advanced_config import ImapEmailSource, BatchProcessingStrategy
from newsletter_parser import NewsletterParserOrchestrator

imap = ImapEmailSource('user@gmail.com', 'password')
emails = imap.fetch_newsletters(max_results=100)

orchestrator = NewsletterParserOrchestrator()

# Process in batches
for batch in BatchProcessingStrategy.batched_processing(emails, batch_size=10):
    orchestrator.parse_batch(batch)

print(orchestrator.get_minimalist_display())


# Example 4: Scheduled processing (24/7)
from advanced_config import ImapEmailSource, BatchProcessingStrategy

imap = ImapEmailSource('user@gmail.com', 'password')
emails = imap.fetch_newsletters(max_results=500)

orchestrator = NewsletterParserOrchestrator()

# Spread 100 emails per hour throughout the day
for email in BatchProcessingStrategy.scheduled_processing(emails, per_hour=100):
    result = orchestrator.parse_newsletter(email)
    if result:
        print(f"✅ {result.original_subject[:50]}... → {result.category}")
"""

# ============================================================================
# GMAIL APP PASSWORD SETUP (Required for IMAP)
# ============================================================================

"""
If using IMAP with Gmail:

1. Enable 2-Factor Authentication on Google Account
2. Go to: https://myaccount.google.com/apppasswords
3. Select 'Mail' and 'Windows Computer' (or your device)
4. Google generates a 16-character password
5. Use this 16-character password in ImapEmailSource

Note: This is different from your regular Gmail password and is more secure.

"""
