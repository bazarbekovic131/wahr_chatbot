import logging
import threading
from app import create_app
from app.services.email_service import mailmain

app = create_app()

def start_mailmain():
    logging.info("Email service started")
    mailmain()

if __name__ == "__main__":
    mail_thread = threading.Thread(target=start_mailmain)
    mail_thread.daemon = True
    mail_thread.start()

    logging.info("Flask app started")
    app.run(host="127.0.0.1", port=5000)
