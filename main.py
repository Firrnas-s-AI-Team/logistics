from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import threading
import time
import pickle
import base64
import subprocess
import PyPDF2
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import csv
from datetime import datetime
from io import StringIO, BytesIO
from flask import Flask, request
import requests
import httpx
import re
import google.generativeai as genai
import subprocess
import fitz
import io
import docx
import os
from groq import Groq
from dotenv import load_dotenv
import pdfplumber
import pandas as pd
import tempfile
import json
from extract_pdf import extract_pdf_text_with_formatting
from E_mail import create_email,send_email
from Reply import extract_reply_content,check_email_replies
from Generate import generate_email_content,evaluate_offers_with_groq
app = FastAPI()
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]

sent_emails: Dict[str, dict] = {}
email_threads: Dict[str, List[dict]] = {}
pending_emails: Dict[str, dict] = {}
email_approval_status: Dict[str, bool] = {}
gmail_service = None
email_processing_thread = None
is_running = True

uploaded_csv_data = []
uploaded_pdf_content = ""

# genai.configure(api_key='AIzaSyB5rluRiexJb_6s22ikWI42na8gDIOW7vM')

class EmailMessage(BaseModel):
    recipient: str
    subject: str
    content: str

class EmailStatus(BaseModel):
    recipient: str
    subject: str
    content: str
    timestamp: str
    status: str
    thread_id: Optional[str] = None
    error: Optional[str] = None
    replies: Optional[List[dict]] = []

class EmailReply(BaseModel):
    thread_id: str
    content: str

class EmailPreview(BaseModel):
    preview_id: str
    recipient: str
    subject: str
    content: str

class EmailApproval(BaseModel):
    approved: bool
    
pending_email_preview = {
    "subject": "",
    "content": "",
    "recipients": [],
    "approved": False
}

def authenticate_gmail_api():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credential.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def process_emails():
    global is_running, pending_email_preview,gmail_service,email_threads,sent_emails
    
    while is_running:
        try:
            check_email_replies(gmail_service,email_threads)

            if not pending_email_preview["approved"]:
                time.sleep(60)
                continue

            for recipient in pending_email_preview["recipients"]:
                send_email(
                    gmail_service,
                    email_threads,
                    sent_emails,
                    recipient,
                    pending_email_preview["subject"],
                    pending_email_preview["content"]
                )
                print(f"Email sent to {recipient}")
                time.sleep(2)  

            pending_email_preview["content"] = ""
            pending_email_preview["recipients"] = []
            pending_email_preview["approved"] = False

            time.sleep(60)
            
        except Exception as e:
            print(f"Error in email processing: {e}")
            time.sleep(60)


@app.post("/api/upload/files")
async def upload_files(
    csv_file: UploadFile = File(..., description="CSV file containing email addresses"),
    pdf_file: UploadFile = File(..., description="PDF file containing shipment details")
):
    global uploaded_csv_data, uploaded_pdf_content, pending_email_preview
    
    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="First file must be a CSV")
    
    if not pdf_file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Second file must be a PDF")
    
    try:
        csv_contents = await csv_file.read()
        csv_text = csv_contents.decode()
        csv_file_obj = StringIO(csv_text)
        reader = csv.DictReader(csv_file_obj)
        uploaded_csv_data = [row['email'] for row in reader if 'email' in row]
        
        pdf_contents = await pdf_file.read()
        uploaded_pdf_content = extract_pdf_text_with_formatting(pdf_contents)
        
        email_content = generate_email_content(client,uploaded_pdf_content)
        
        
        
        pending_email_preview = {
            "subject": "Shipment Information",
            "content": email_content,
            "recipients": uploaded_csv_data,
            "approved": False
        }
        
        return {
            "message": "Files uploaded and email preview generated",
            "preview": {
                "subject": pending_email_preview["subject"],
                "content": pending_email_preview["content"],
                "recipients": pending_email_preview["recipients"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing files: {str(e)}")

@app.get("/api/preview", response_model=EmailPreview)
async def get_email_preview():
    if not pending_email_preview["content"]:
        raise HTTPException(status_code=404, detail="No preview available")
    
    return EmailPreview(
        preview_id="single_preview",  
        recipient="All Recipients",  
        subject=pending_email_preview["subject"],
        content=pending_email_preview["content"]
    )
@app.post("/api/approve")
async def approve_email(approval: EmailApproval):
    if not pending_email_preview["content"]:
        raise HTTPException(status_code=404, detail="No preview available")
    
    pending_email_preview["approved"] = approval.approved
    
    if not approval.approved:
        pending_email_preview["content"] = ""
        pending_email_preview["recipients"] = []
        return {"message": "Email rejected"}
    
    return {"message": "Email approved and queued for sending"}
@app.get("/api/emails", response_model=List[EmailStatus])
async def get_sent_emails():
    email_list = []
    for thread_id, messages in email_threads.items():
        sent_message = next((msg for msg in messages if msg['type'] == 'sent'), None)
        if sent_message:
            replies = [msg for msg in messages if msg['type'] == 'reply']
            
            cleaned_replies = []
            for reply in replies:
                cleaned_content = extract_reply_content(reply['content'])
                cleaned_replies.append({
                    **reply,
                    'content': cleaned_content
                })
            
            email_list.append(EmailStatus(
                recipient=sent_message['recipient'],
                subject=sent_message['subject'],
                content=sent_message['content'],
                timestamp=sent_message['timestamp'],
                status=sent_message['status'],
                thread_id=thread_id,
                error=sent_message.get('error'),
                replies=cleaned_replies
            ))
    
    return email_list

@app.get('/api/rget')
async def reply_get():
    try:
        replies = []
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5000/api/emails", timeout=5.0)
            response.raise_for_status()  

            for email_conv in response.json():
                thread_id = email_conv['thread_id']
                email_from = email_conv['recipient']
                
                reply_contents = []
                for reply in email_conv.get('replies', []):
                    main_content = reply['content'].split('\r\nFrom:')[0]
                    
                    attachment_contents = []
                    if reply.get('attachments'):
                        for attachment in reply['attachments']:
                            if attachment.get('text_content'):
                                attachment_contents.append(attachment['text_content'])
                            elif attachment.get('content'):
                                attachment_text = ' '.join(map(str, attachment['content']))
                                attachment_contents.append(attachment_text)
                    
                    full_reply_content = main_content
                    if attachment_contents:
                        full_reply_content += "\n\nAttachment Contents:\n" + "\n".join(attachment_contents)
                    
                    reply_contents.append(full_reply_content)

                existing_thread = next((t for t in replies if t['thread_id'] == thread_id), None)
                if existing_thread:
                    existing_thread['reply'] = reply_contents
                else:
                    replies.append({
                        "thread_id": thread_id,
                        "email_from": email_from,
                        "reply": reply_contents 
                    })

            return replies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/evaluate_offers")
async def evaluate_offers():
    try:
        # Get email replies
        email_list = await reply_get()
        replies = []
        for email in email_list:
            if email['reply']:
                
                for reply in email['reply']:
                    if isinstance(reply, list):
                        replies.extend(reply)
                    else:
                        replies.append(reply)
        
        if len(replies) < 3:
            raise HTTPException(status_code=400, detail="Not enough replies to evaluate offers")

        # Store the first three replies
        offer_1 = replies[0] if len(replies) > 0 else ""
        offer_2 = replies[1] if len(replies) > 1 else ""
        offer_3 = replies[2] if len(replies) > 2 else ""
        
        # Get evaluation result
        evaluation_result = evaluate_offers_with_groq(client,replies)
        
        # Define CSV file path
        csv_file_path = 'evaluation_history.csv'
        
        # Check if file exists and create with headers if it doesn't
        file_exists = os.path.isfile(csv_file_path)
        
        # Prepare the data row
        data_row = {
            'offer_1': offer_1,
            'offer_2': offer_2,
            'offer_3': offer_3,
            'evaluation_result': evaluation_result
        }
        
        # Write to CSV file
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['offer_1', 'offer_2', 'offer_3', 'evaluation_result'])
            
            # Write headers if file is new
            if not file_exists:
                writer.writeheader()
            
            # Write the data row
            writer.writerow(data_row)
        
        return {
            "evaluation_result": evaluation_result,
            "logged": True
        }
        
    except Exception as e:
        # Log the error but still try to write to CSV
        error_message = str(e)
        
        try:
            # Define CSV file path
            csv_file_path = 'evaluation_history.csv'
            file_exists = os.path.isfile(csv_file_path)
            
            # Prepare the error data row
            data_row = {
                'offer_1': "Error occurred",
                'offer_2': "Error occurred",
                'offer_3': "Error occurred",
                'evaluation_result': f"Error: {error_message}"
            }
            
            # Write to CSV file
            with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=['offer_1', 'offer_2', 'offer_3', 'evaluation_result'])
                
                # Write headers if file is new
                if not file_exists:
                    writer.writeheader()
                
                # Write the error data row
                writer.writerow(data_row)
                
        except Exception as csv_error:
            raise HTTPException(
                status_code=500,
                detail=f"Original error: {error_message}. CSV logging error: {str(csv_error)}"
            )
            
        raise HTTPException(status_code=500, detail=error_message)


@app.on_event("startup")
async def startup_event():
    global gmail_service, email_processing_thread
    gmail_service = authenticate_gmail_api()
    email_processing_thread = threading.Thread(target=process_emails, daemon=True)
    email_processing_thread.start()

@app.on_event("shutdown")
async def shutdown_event():
    global is_running
    is_running = False
    if email_processing_thread:
        email_processing_thread.join(timeout=5)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)

# import PyPDF2
# import io
# import base64
# import docx
# import pandas as pd
# import pdfplumber

# def pdf_reader(file_path):
#     with open(file_path, "rb") as pdf_file:
#         base64_pdf_data = base64.b64encode(pdf_file.read()).decode("utf-8")
#         file_data = base64.b64decode(base64_pdf_data)

#         # Read the PDF using PyPDF2
#         pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))

#     # Extract text from each page
#     for page_num, page in enumerate(pdf_reader.pages):
#         print(f"--- Page {page_num + 1} ---")
#         print(page.extract_text())
#     return pdf_reader.pages
# gmail_service = authenticate_gmail_api()
# pdf_content = pdf_reader('Yarab\\Shipment Details.pdf')
# generate = generate_email_content(client,pdf_content)
# send_email(gmail_service,email_threads,sent_emails,'lastonecolab.com@gmail.com','try',generate)
# print('Done')