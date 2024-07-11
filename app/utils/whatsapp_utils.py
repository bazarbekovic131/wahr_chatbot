import logging
from flask import current_app, jsonify
import json
import requests

# from app.services.openai_service import generate_ai_ response
from .db import WADatabase
import re

db_config = {
    'host': 'localhost',
    'database': 'shark_whatsapp',
    'user': 'shark',
    'password': 'shark',
    'port': '5432'
}
database = WADatabase(db_config)

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_vacancies(from_number):
    """Handle incoming messages and answer with vacancy list."""
    vacancies = database.get_vacancies()
    
    message = "Отлично! У нас есть несколько открытых позиций:\n\n"
    for id, vacancy in vacancies:
        message = message + "\n" + f"{id}. {vacancy}"
    logging.info(f'Message to be sent: {message}')
    
    
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)
    send_message(data)

def send_vacancy_details(from_number, data):
    message = f'Вакансия: {data[0]}\n\n Требования:\n {data[1]}\n\n  Условия работы:\n {data[2]}'
    data_to_be_sent = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    send_message(data_to_be_sent)

def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"] # change .config recipient waid to this i guess
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]

    # TODO: implement custom function here
    # response = generate_response(message_body)

    vacancies = database.get_vacancies()
    
    if ('ваканс' in message or 'работ' in message): # list vacancies
        send_vacancies(wa_id)

        for idx, vacancy_title in vacancies: # vacancy details
            if vacancy_title.lower() in message_body:
                response = database.get_vacancy_details(idx)
                data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
                send_message(data)
                break













    
    # OpenAI Integration
    # response = generate_ai_response(message_body, wa_id, name)
    # response = process_text_for_whatsapp(response)

    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
    # send_message(data)


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
