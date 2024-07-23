import logging
from app import create_app
from app.services.email_service import mailmain
import schedule
import threading
import time
app = create_app()

def start_mailmain():
    logging.info("Email service started\n\n\n")
    # mailmain()

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)



if __name__ == "__main__":

    schedule.every(5).seconds.do(start_mailmain) # try to schedule
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    logging.info("Flask app started")
    app.run(host="127.0.0.1", port=5000)
