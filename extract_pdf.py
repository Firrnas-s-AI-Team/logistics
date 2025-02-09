from io import BytesIO
import fitz
import base64
import re
import pandas as pd
import tempfile
import os
import pdfplumber
def extract_pdf_text_with_formatting(pdf_bytes):
    """
    Extracts text from a PDF while maintaining original formatting (spaces, new lines).
    """
    try:
        pdf_file_obj = BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_file_obj, filetype="pdf")  
        extracted_text = ""
        for page in doc:
            extracted_text += page.get_text("text") + "\n"  
        return extracted_text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""
def extract_body(payload):
    """Extracts the email body, handling multipart messages and ensuring full content is retrieved."""
    body = ""

    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore') + "\n"
            elif part['mimeType'] == 'text/html' and 'body' in part and 'data' in part['body']:
                html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                plain_text = re.sub(r'<[^>]+>', '', html_content)  # Remove HTML tags
                body += plain_text + "\n"
            elif 'parts' in part:
                # Handle nested MIME structures
                body += extract_body(part)

    if not body and 'body' in payload and 'data' in payload['body']:
        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        body = re.sub(r'[ \t]+', ' ', body)  
    body = re.sub(r'\n\s+', '\n', body)  

    return body.strip()

def pdf_reader_table(file_path):
    tables = []
    content = []
    structured_tables = []  

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()

            # Extract text while removing table content
            text = ""
            table_bbox = [table.bbox for table in page.find_tables()]
            
            for block in page.extract_words():
                if not any(
                    bbox[0] <= float(block["x0"]) <= bbox[2] and bbox[1] <= float(block["top"]) <= bbox[3]
                    for bbox in table_bbox
                ):
                    text += block["text"] + " "

            text = text.strip()
            if text:
                content.append(text)

            # Convert tables into dictionary format
            for table in page_tables:
                if table:  # Ensure table is not empty
                    header = table[0]  # First row as keys (column names)
                    for row in table[1:]:  # Remaining rows as values
                        table_dict = {header[i]: row[i] for i in range(len(header)) if i < len(row)}
                        structured_tables.append(table_dict)
        
        # Create a text representation of tables
        table_text_representation = []
        for table in structured_tables:
            table_text = "\n".join([f"{key}: {value}" for key, value in table.items()])
            table_text_representation.append(table_text)
        
        text_representation = "\n\n".join(content + table_text_representation)

    return {
        "content": content,
        "tables": structured_tables,
        "text_representation": text_representation
    }


def file_reader(file_path):
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".xls") or file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please provide a CSV or Excel file.")

        # Convert DataFrame to a comprehensive dictionary representation
        data = {
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
            "text_representation": "\n".join([
                f"{col}: {', '.join(map(str, df[col].dropna().tolist()))}"
                for col in df.columns
            ])
        }

        return data
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
def extract_attachments(gmail_service,payload, message_id):
    attachments = []
    
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('filename'):
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    try:
                        attachment = gmail_service.users().messages().attachments().get(
                            userId='me',
                            messageId=message_id,
                            id=attachment_id
                        ).execute()
                        
                        if 'data' not in attachment:
                            print(f"No data found in attachment: {part['filename']}")
                            continue
                            
                        file_data = base64.urlsafe_b64decode(attachment['data'])
                        file_name = part['filename']
                        file_extension = file_name.split('.')[-1].lower()
                        
                        attachment_data = {
                            'file_name': file_name,
                            'file_extension': file_extension,
                            'content': None,
                            'text_content': None
                        }
                        
                        if file_extension == 'pdf':
                            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                                temp_file.write(file_data)
                                temp_file_path = temp_file.name
                            
                            try:
                                result = pdf_reader_table(temp_file_path)
                                attachment_data['content'] = result
                                attachment_data['text_content'] = result.get('text_representation', '')
                            finally:
                                os.unlink(temp_file_path)
                                
                        elif file_extension in ['csv', 'xls', 'xlsx']:
                            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_file:
                                temp_file.write(file_data)
                                temp_file_path = temp_file.name
                            
                            try:
                                result = file_reader(temp_file_path)
                                attachment_data['content'] = result
                                attachment_data['text_content'] = result.get('text_representation', '')
                            finally:
                                os.unlink(temp_file_path)
                                
                        elif file_extension == 'txt':
                            attachment_data['content'] = file_data.decode('utf-8').split("\n")
                            attachment_data['text_content'] = attachment_data['content']
                            
                        attachments.append(attachment_data)
                        
                    except Exception as e:
                        print(f"Error processing attachment {part['filename']}: {str(e)}")
                        continue
    
    return attachments