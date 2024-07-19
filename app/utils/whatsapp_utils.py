import logging
from flask import current_app, jsonify
import json
import requests
from dotenv import load_dotenv
import os

# from app.services.openai_service import generate_ai_ response
# from app.services.email_service import send_email_with_resume
from .db import WADatabase
import re

load_dotenv()

db_config = {
    'host': os.getenv("DBHOST"),
    'database': os.getenv("DBNAME"),
    'user': os.getenv("DBUSER"),
    'password': os.getenv("DBPASSWORD"),
    'port': os.getenv("DBPORT")
}
database = WADatabase(db_config)

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

# logs http response
def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

# processes OpenAI style text to What's App style text (for AI integration)
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

# returns the JSON from the text. So i need to turn my text fetched from database using this command
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

# sends a message (first, a reply is required)
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

def send_template_message(number, template_name = "hello_world", code = "en-US"):
    url = f"https://graph.facebook.com/{current_app['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": "Bearer " + current_app.config["ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": current_app.config["RECIPIENT_WAID"], #change to something else
        "type": "template",
        "template": {"name": f"{template_name}", "language": {"code": f"{code}"}},
    }
    response = requests.post(url, headers=headers, json=data)
    return response


# Should send a message (non-template message) to the user when he requests vacancy list
def send_vacancies(from_number):
    """Handle incoming messages and answer with vacancy list."""
    vacancies = database.get_vacancies()
    
    message = "Отлично! У нас есть несколько открытых позиций:\n\n"
    for id, vacancy in vacancies:
        message = message + "\n" + f"{id}. {vacancy}"
    logging.info(f'Message to be sent: {message}')
    
    # TODO: handle as template?

    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)
    send_message(data)

# Should send a vacancy details
def send_vacancy_details(from_number, vacancy):
    '''
    input - from_number - is the whats app id of the recipient, in the format +787777777 (KZ)
    vacancy - it is an array fetched from the database by the script

    output - sends a message in data format (e.g. message is converted to JSON format)
    '''

    message = f'Вакансия: {vacancy[0]}\n\n Требования:\n {vacancy[1]}\n\n  Условия работы:\n {vacancy[2]}'

    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)
    send_message(data)

def send_company_details(from_number):
    message = f'Наша компания является одной из ведущих строительной компаний Казахстана'
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)
    send_message(data)

def send_social_details(from_number):
    message = f'Здесь будут описаны условия соц. пакета'
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)
    send_message(data)

def asked_for_help(from_number):
    message = f'Чем я могу Вам помочь?' # add template, change send_message to send_whatsapp_message
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], message)
    # data = get_text_message_input(from_number, message)

    send_message(data) 

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"] # change .config recipient waid to this i guess
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]

    # TODO: implement custom function here
    # response = generate_response(message_body)

    vacancies = database.get_vacancies()
    sent_answer = False
    if ('ваканс' in message or 'работ' in message): # list vacancies
        send_vacancies(wa_id)
        sent_answer = True

    if ('расскажите о компании' in message.lower()):
        send_company_details(wa_id)
        sent_answer = True
    if ('мне нужна помощь' in message.lower()):
        send_company_details(wa_id)
        sent_answer = True
    if ('социальные льготы' in message.lower()):
        send_social_details(wa_id)
        sent_answer = True
    if ('резюме' in message.lower()):
        send_template_message(wa_id, template_name="resume", code="ru")
        sent_answer = True

    if not sent_answer:
        for idx, vacancy_title in vacancies: # vacancy details
            if vacancy_title.lower() in message:
                vacancy = database.get_vacancy_details(idx)
                # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
                # send_message(data)
                send_vacancy_details(wa_id, vacancy)
                sent_answer = True
                break
    if not sent_answer:
        send_template_message(wa_id,template_name="greeting", code="ru")

            











    
    # OpenAI Integration
    # response = generate_ai_response(message_body, wa_id, name)
    # response = process_text(response)

    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
    # send_message(data)



