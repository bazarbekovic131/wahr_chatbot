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
    timestamp = datetime.strftime("%Y%m%d%H%M%S") # should be a timestamp
    zip_name = f"resumes_{timestamp}.zip"

    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in attachment_paths:
            zipf.write(file, os.path.basename(file))
    return zip_name

def generate_email_body(survey_df):
    html = """
    <html>
    <head>
        <style>
            body {font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;}
            .container {width: 80%; margin: 0 auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);}
            .header, .footer {background-color: #333; color: #fff; text-align: center; padding: 10px 0;}
            .content {padding: 20px;}
            table {width: 100%; border-collapse: collapse; margin: 20px 0;}
            th, td {padding: 12px; border: 1px solid #ddd; text-align: left;}
            th {background-color: #333; color: #fff;}
            tr:nth-child(even) {background-color: #f2f2f2;}
            tr:nth-child(odd) {background-color: #e9e9e9;}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Новые резюме</h1>
            </div>
            <div class="content">
                <p>На указанный период были получены следующие отклики на вакансии (из What's App):</p>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Phone</th>
                        <th>Age</th>
                        <th>Production Experience</th>
                        <th>Completed Survey</th>
                        <th>Resume</th>
                    </tr>
    """

    for index, row in survey_df.iterrows():
        html += f"""
                    <tr>
                        <td>{row['id']}</td>
                        <td>{row['phone']}</td>
                        <td>{row['age']}</td>
                        <td>{row['production_experience']}</td>
                        <td>{row['completed_survey']}</td>
                        <td>{row['resume']}</td>
                    </tr>
        """

    html += """
                </table>
            </div>
            <div class="footer">
                <p>© 2024 Your Company. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html

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
        msg.attach(MIMEText(body, 'html'))

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
                body = generate_email_body(incomplete_surveys)
                if attachment_paths:
                    zip_path = create_zip(attachment_paths)
                    send_email(email, subject, body, zip_path)
                    os.remove(zip_path) # clean up after sending
                else:
                    send_email(email, subject, body)