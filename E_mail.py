from typing import List, Dict, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
from datetime import datetime
import time

def create_email(to: str, subject: str, body: str, thread_id: Optional[str] = None):
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = "abdallaelshamu781@gmail.com"  
    message['subject'] = subject

    msg = MIMEText(body, 'plain', 'utf-8')
    message.attach(msg)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    email_data = {'raw': raw_message}
    
    if thread_id:
        email_data['threadId'] = thread_id
    
    return email_data
def send_email(gmail_service,email_threads,sent_emails,to: str, subject: str, body: str, thread_id: Optional[str] = None):
    try:
        email = create_email(to, subject, body, thread_id)
        sent_message = gmail_service.users().messages().send(userId="me", body=email).execute()
        
        message_data = {
            'recipient': to,
            'subject': subject,
            'content': body,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'sent',
            'thread_id': sent_message.get('threadId'),
            'message_id': sent_message['id'],
            'type': 'sent'
        }
        
        sent_emails[sent_message['id']] = message_data
        
        thread_id = sent_message.get('threadId')
        if thread_id:
            if thread_id not in email_threads:
                email_threads[thread_id] = []
            email_threads[thread_id].append(message_data)
        
        return sent_message
    except Exception as error:
        error_data = {
            'recipient': to,
            'subject': subject,
            'content': body,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'failed',
            'error': str(error),
            'type': 'sent'
        }
        message_id = time.strftime('%Y%m%d%H%M%S')
        sent_emails[message_id] = error_data
        return None