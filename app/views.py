import logging
import json

from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
    send_template_message
)
from dotenv import load_dotenv
import os
from app.utils.db import WADatabase
import time

load_dotenv()

db_config = {
    'host': os.getenv("DBHOST"),
    'database': os.getenv("DBNAME"),
    'user': os.getenv("DBUSER"),
    'password': os.getenv("DBPASSWORD"),
    'port': os.getenv("DBPORT")
}
database_wa = WADatabase(db_config)

webhook_blueprint = Blueprint("webhook", __name__)


def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    body = request.get_json()
    logging.info(f"request body: {body}")

    # Check if it's a WhatsApp status update
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        logging.info("Received a WhatsApp status update.")
        return jsonify({"status": "ok"}), 200

    try:
        if is_valid_whatsapp_message(body):
            process_whatsapp_message(body)
            logging.info("Valid What's App message received. Processing started")
            return jsonify({"status": "ok"}), 200
        else:
            # if the request is not a WhatsApp API event, return an error
            logging.info("Not a valid What's App API event")
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400


# Required webhook verifictaion for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

def send_messages_to_selected_users(body):
    try:
        contacts = body.get("contacts", [{}])
        for contact in contacts:
            number = contact.get("phone", "") # phone number
            number = number.replace('+','').strip()
            logging.info(f'number: {number}')
            number_in_db = database_wa.get_user(number)
            logging.info(f'exists?: {number_in_db}')
            if number_in_db == False:
                database_wa.create_user(number)
                logging.info(f'created user: {number}')
            name = contact.get("name", "") # name
            wants_notif = database_wa.wants_notifications(phone=number)
            logging.info(f'Wants notifs?: {wants_notif}')
            if wants_notif != False:
                try:
                    send_template_message(number, template_name="rassylka_vacansii", code="ru") # TODO: this template doesn't exist yet.
                except Exception as err3:
                    logging.error(f'Error occurred: {err3}')
            # send_template_message(number, template_name="greeting", code="ru")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": f"error: {e}"}), 400

@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
def webhook_post():
    return handle_message()

@webhook_blueprint.route('/test', methods=['POST', 'GET'])
def webhook_test():
    return jsonify({"status": "OK"}), 200

@webhook_blueprint.route("/send_messages", methods = ["POST"])
def send_messages_list():
    verification = request.headers.get('token', '')
    if verification == current_app.config['VERIFY_TOKEN']:
        body = request.get_json()
        logging.info(f'Logged a post request: Body is {body}')
        return send_messages_to_selected_users(body)
    else:
        return jsonify({"status": "error", "message": "Verification failed"}), 400
    
# @webhook_blueprint.route('/')
# def index():
#     return render_template('index.html')

@webhook_blueprint.route("/vacancies", methods = ["GET"])
def vacancies_list():
    data = database_wa.get_vacancies_full()
    vacancies = []
    for idx, title, details, requirements, tasks, salary in data:
        el = {
            "id": idx,
            "title": title,
            "details": details,
            "requirements": requirements,
            "tasks": tasks,
            "salary": salary
        }
        vacancies.append(el)
    json_object = vacancies
    json_object = json.dumps(json_object, indent=4)

    return json_object # return a JSON of all vacancies

@webhook_blueprint.route("/users", methods = ["GET"])
def users_list():
    data = database_wa.get_users_full()
    
    vacancies = []
    for idx, title, details, requirements, tasks, salary in data:
        el = {
            "id": idx,
            "title": title,
            "details": details,
            "requirements": requirements,
            "tasks": tasks,
            "salary": salary
        }
        vacancies.append(el)

    return jsonify(vacancies) # return a JSON of all vacancies


@webhook_blueprint.route("/surveys", methods = ["GET"])
def surveys_list():
    return jsonify(database_wa.get_surveys_full()) # return a JSON of all surveys
