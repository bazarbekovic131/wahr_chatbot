import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email_with_resume(to_address, subject, body, attachment_path):
    try:
        # Set up the SMTP server
        server = smtplib.SMTP(host=EMAIL_HOST, port=EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_address
        msg['Subject'] = subject

        # Add the email body
        msg.attach(MIMEText(body, 'plain'))

        # Attach the resume file
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(attachment_path)}",
        )

        msg.attach(part)

        # Send the email
        server.send_message(msg)
        server.quit()

        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def handle_resume_submission(user_phone, user_address, resume_file_path):
    # Save the resume file in the database
    with open(resume_file_path, "rb") as file:
        resume_data = file.read()
        resume_filename = os.path.basename(resume_file_path)
        database.insert_resume(user_phone, user_address, resume_filename, resume_data)
    
    # Define the recipient email address
    recipient_email = "bazar.akhmet@gmail.com" #TODO: change to HR email hr@shark.kz

    # Define the email subject and body
    email_subject = "Отправлено новое резюме"
    email_body = f"Резюме было отправлено из What's App пользователем с номером: {user_phone}."

    # Send the email with the resume attachment
    send_email_with_resume(recipient_email, email_subject, email_body, resume_file_path)