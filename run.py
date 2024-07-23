import logging
from app import create_app
app = create_app()

if __name__ == "__main__":
    logging.info("Flask app started")
    app.run(host="127.0.0.1", port=5000)
