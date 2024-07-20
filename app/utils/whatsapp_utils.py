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

# Example survey questions with JSON keys
survey_questions = [
    {"question": "Как вас зовут?", "key": "name"},
    {"question": "Сколько вам лет?", "key": "email"},
    {"question": "На какую вакансию вы хотите устроиться?", "key": "vacancy"},
    {"question": "Пожалуйста, загрузите ваше резюме.", "key": "resume"}
]

# In-memory session storage
sessions = {}

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

def create_interactive_json(header_text, body_text, footer_text, button_text, sections):
    """
        This should be documented
    """
    interactive_json = {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "footer": {
                "text": footer_text
            },
            "action": {
                "sections": sections,
                "button": button_text
            }
        }
    }
    
    return interactive_json

def send_interactive(wa_id, interactive_elements):
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    
    headers = {
        "Authorization": "Bearer " + current_app.config["ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": current_app.config["RECIPIENT_WAID"], #change to something else
    }
    data.update(interactive_elements)

    logging.info(f'POST data: URL {url}\n headers: {headers}\n data: {data}')
    response = requests.post(url, headers=headers, json=data)
    return response

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
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
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
    logging.info(f'POST data: URL {url}\n headers: {headers}\n data: {data}')
    response = requests.post(url, headers=headers, json=data)
    return response

def send_location_message(number, latitude, longitude, name, address):
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": "Bearer " + current_app.config["ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": current_app.config["RECIPIENT_WAID"], #change to something else
        "type": "location",
        "location": {
            "latitude": f"{latitude}",
            "longitude": f"{longitude}",
            "name": f"{name}",
            "address": f"{address}"
        }
    }
    logging.info(f'POST data: URL {url}\n headers: {headers}\n data: {data}')
    response = requests.post(url, headers=headers, json=data)
    return response



# Should send a message (non-template message) to the user when he requests vacancy list
def send_vacancies(wa_id):
    """Handle incoming messages and answer with vacancy list."""
    header_text = "Вакансии"
    footer_text = "Это сообщение отправлено автоматически"
    body_text = "Отлично! У нас есть несколько открытых позиций. Пожалуйста, откройте меню для ознакомления"
    button_text = "Выбрать"

    sections = database.get_vacancies_for_interactive_message()

    data = create_interactive_json( header_text, body_text, footer_text, button_text, sections )
    res = send_interactive(wa_id, data)
    logging.info(res)


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

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"] # change .config recipient waid to this i guess
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]

    # Determine the type of message and handle accordingly
    message_type = message.get("type")
    message_body = None
    payload = None
    document_id = None

    sent_answer = False
    if message_type == "text":
        message_body = message.get("text", {}).get("body", "").lower()    
        
        if ('ваканс' in message_body or 'работ' in message_body): # list vacancies # This should be deprecated
            send_vacancies(wa_id)
            sent_answer = True
            # return 1

        # if ('социальные льготы' in message_body):
        #     send_social_details(wa_id)
        #     sent_answer = True
        #     # return 1

        if ('резюме' in message_body):
            send_template_message(wa_id, template_name="resume_form", code="ru")
            sent_answer = True
            # return 1

        if not sent_answer:
            vacancies = database.get_vacancies()
            for idx, vacancy_title in vacancies: # vacancy details
                if vacancy_title.lower() in message_body:
                    vacancy = database.get_vacancy_details(idx)
                    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
                    # send_message(data)
                    send_vacancy_details(wa_id, vacancy)
                    sent_answer = True
                    break

        if not sent_answer:
            logging.info("Trying to send a template message")
            res = send_template_message(wa_id, template_name="help_ru", code="ru")
            logging.info(f'Response: {res}')
            
    elif message_type == "button":
        payload = message.get("button", {}).get("payload", "")
        
        if payload == 'О нас':
            send_template_message(wa_id, template_name="company_details", code="ru") #TODO: reimplemented DONE
        
        if payload == 'Вакансии':
            logging.info('Vacancies Payload Reached. Trying to send interactive message')
            send_vacancies(wa_id)

        if payload == 'Помощь':
            send_template_message(wa_id, template_name="help_ru", code="ru")
        
        if payload == 'Отправить резюме': # Doesn't work yet
            send_template_message(wa_id, template_name="resume_form", code="ru") # TODO: new flow needs to be done

            if wa_id not in sessions:
                sessions[wa_id] = {"responses": {}, "current_step": 0}
            user_session = sessions[wa_id]
            current_step = user_session["current_step"]
        
        if payload == 'Процесс найма':
            send_template_message(wa_id, template_name="hiring_conditions", code="ru")
        
        if payload == 'Связаться с HR':
            send_template_message(wa_id, template_name="help_ru", code="ru")

        
    elif message_type == "document":
        document_id = message['document']['id']
        filename = message['document']['filename']
        user_session["responses"].append(document_id)
        # Process the CV document if needed
        send_template_message(wa_id, template_name="placeholder", code="ru") #TODO:
        logging.info(f"Survey responses for {wa_id}: {user_session['responses']}")
        del sessions[wa_id]
    
    # payload = message['button']['payload'] # Access the payload of the button it is like Вакансии or Отправить резюме.

    # TODO: implement custom function here
    # response = generate_response(message_body)

    


            











    
    # OpenAI Integration
    # response = generate_ai_response(message_body, wa_id, name)
    # response = process_text(response)

    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
    # send_message(data)



