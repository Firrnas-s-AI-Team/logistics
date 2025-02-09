import streamlit as st
import requests
import pandas as pd

# FastAPI backend URL
BACKEND_URL = "http://127.0.0.1:5000"

# Function to upload files
def upload_files(csv_file, pdf_file):
    files = {
        "csv_file": (csv_file.name, csv_file.getvalue(), "text/csv"),
        "pdf_file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")
    }
    response = requests.post(f"{BACKEND_URL}/api/upload/files", files=files)
    return response.json()

# Function to get email preview
def get_email_preview():
    response = requests.get(f"{BACKEND_URL}/api/preview")
    return response.json()

# Function to approve email
def approve_email(approved):
    response = requests.post(f"{BACKEND_URL}/api/approve", json={"approved": approved})
    return response.json()

# Function to get sent emails
def get_sent_emails():
    response = requests.get(f"{BACKEND_URL}/api/emails")
    return response.json()

# Function to evaluate offers
def evaluate_offers():
    response = requests.get(f"{BACKEND_URL}/api/evaluate_offers")
    return response.json()

# Streamlit app
def main():
    st.title("Email Automation System")

    # File upload section
    st.header("Upload Files")
    csv_file = st.file_uploader("Upload CSV file", type=["csv"])
    pdf_file = st.file_uploader("Upload PDF file", type=["pdf"])

    if csv_file and pdf_file:
        if st.button("Upload and Generate Email Preview"):
            result = upload_files(csv_file, pdf_file)
            st.success(result["message"])
            st.json(result["preview"])

    # Email preview section
    st.header("Email Preview")
    if st.button("Get Email Preview"):
        preview = get_email_preview()
        st.subheader("Subject")
        st.write(preview["subject"])
        st.subheader("Content")
        st.write(preview["content"])

    # Email approval section
    st.header("Approve Email")
    if st.button("Approve Email"):
        result = approve_email(True)
        st.success(result["message"])

    if st.button("Reject Email"):
        result = approve_email(False)
        st.success(result["message"])

    # Sent emails section
    st.header("Sent Emails")
    if st.button("View Sent Emails"):
        emails = get_sent_emails()
        for email in emails:
            st.subheader(f"Email to {email['recipient']}")
            st.write(f"Subject: {email['subject']}")
            st.write(f"Content: {email['content']}")
            st.write(f"Status: {email['status']}")
            st.write(f"Timestamp: {email['timestamp']}")
            if email['replies']:
                st.subheader("Replies")
                for reply in email['replies']:
                    st.write(reply['content'])

    # Evaluate offers section
    st.header("Evaluate Offers")
    if st.button("Evaluate Offers"):
        result = evaluate_offers()
        st.subheader("Evaluation Result")
        st.write(result["evaluation_result"])
        if result["logged"]:
            st.success("Evaluation logged successfully.")

if __name__ == "__main__":
    main()