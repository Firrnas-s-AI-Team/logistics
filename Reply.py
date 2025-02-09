import re
from extract_pdf import extract_body,extract_attachments
from datetime import datetime
def extract_reply_content(content: str) -> str:
    """
    Extracts the full reply content, handling various email formats and preserving multi-line text.
    """
    patterns = [
        r"On .+ wrote:", 
        r"_{10,}",        
        r"Sent: .+",      
        r"To: .+",        
        r"Subject: .+",   
        r"> .+",          
        r"\nOn .+\n",     
        r"\nSent .+\n",   
        r"\nTo .+\n",     
        r"\nSubject .+\n",
        r"\n\s*Thanks and best regards,.*",  
        r"\n\s*Best regards,.*",  
        r"\n\s*Regards,.*",  
        r"\n\s*[A-Za-z\s]+,\s*\n", 
    ]
    
    normalized_content = re.sub(r'\r\n', '\n', content)
    normalized_content = re.sub(r'\n\s+', '\n', normalized_content)
    
    for pattern in patterns:
        match = re.search(pattern, normalized_content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            return normalized_content[:match.start()].strip()
    
    return normalized_content.strip()
def check_email_replies(gmail_service,email_threads):
    try:
        results = gmail_service.users().messages().list(userId='me', q='in:inbox').execute()
        messages = results.get('messages', [])

        for message in messages:
            msg = gmail_service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            thread_id = msg['threadId']

            if thread_id in email_threads:
                existing_message_ids = {reply['message_id'] for reply in email_threads[thread_id]}
                if message['id'] in existing_message_ids:
                    continue  # Skip if already processed

                if 'payload' in msg and 'headers' in msg['payload']:
                    headers = msg['payload']['headers']
                    subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), '')
                    from_email = next((header['value'] for header in headers if header['name'].lower() == 'from'), '')

                    body = extract_body(msg['payload'])  # Extract text content properly

                    reply_data = {
                        'message_id': message['id'],
                        'from': from_email,
                        'subject': subject,
                        'content': body,  # Ensure no empty body
                        'timestamp': datetime.fromtimestamp(int(msg['internalDate'])/1000).strftime('%Y-%m-%d %H:%M:%S'),
                        'type': 'reply',
                        'attachments': extract_attachments(gmail_service,msg['payload'], message['id'])  # Handle attachments separately
                    }

                    email_threads[thread_id].append(reply_data)

                    # Mark the email as read
                    gmail_service.users().messages().modify(
                        userId='me',
                        id=message['id'],
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()

    except Exception as e:
        print(f"Error checking replies: {e}")