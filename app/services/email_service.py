import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv
from app.utils.db import WADatabase
import time
import zipfile
from datetime import datetime

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def create_zip(attachment_paths):
    zip_name = datetime.strftime # should be a timestamp
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in attachment_paths:
            zipf.write(file, os.path.basename(file))
    return zip_name

def send_email(to_address, subject, body, attachment_path=None):
    '''
        Can send with or without attachment
    '''
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

def mailmain():
    db_config = {
        'host': os.getenv("DBHOST"),
        'database': os.getenv("DBNAME"),
        'user': os.getenv("DBUSER"),
        'password': os.getenv("DBPASSWORD"),
        'port': os.getenv("DBPORT")
    }
    database = WADatabase(db_config)

    while True:
        incomplete_surveys = database.get_incomplete_surveys()
        if not incomplete_surveys.empty:
            subject = 'Новые резюме'
            body = 'На указанный период были получены следующие отклики на вакансии (из What\'s App)' + incomplete_surveys.to_string(index=True)
            email = 'bazar.akhmet@gmail.com'
            
            attachment_paths = []
            survey_ids = []

            for index, row in incomplete_surveys.iterrows():
                resume_path = row['resume']
                if resume_path and os.path.isfile(resume_path):
                    attachment_paths.append(resume_path)
                    survey_ids.append(row['id'])
                else:
                    survey_ids.append(row['id'])
                database.update_sent_status(row['id'])

            if survey_ids:
                if attachment_paths:
                    zip_path = create_zip(attachment_paths)
                    send_email(email, subject, body, zip_path)
                    os.remove(zip_path) # clean up after sending
                else:
                    send_email(email, subject, body)
        time.sleep(3 * 24 * 3600) # 3 дня