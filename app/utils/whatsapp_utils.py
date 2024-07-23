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
    {"question": "Сколько вам лет?", "key": "age"},
    {"question": "На какую вакансию вы хотите устроиться?", "key": "vacancy"},
    {"question": "Какой у вас опыт работы?", "key": "production_experience"},
    {"question": "Пожалуйста, загрузите ваше резюме.", "key": "resume"}
]



def is_valid_whatsapp_message(body):
    '''
    Check if the incoming webhook event has a valid WhatsApp message structure.
    '''
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



########################    DOWNLOAD DOCUMENTS ############################

def fetch_media_data(media_id):
    ''' Получение ссылки на документ'''

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{media_id}/"
    
    headers = {
        'Authorization': f'Bearer {current_app.config["ACCESS_TOKEN"]}'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching media data: {e}")
        raise

def get_file(url, file_name):
    headers = {
        'Authorization': f'Bearer {current_app.config["ACCESS_TOKEN"]}'
    }
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        downloads_folder = '/home/shark/wahr_chatbot/downloads'
        file_path = os.path.join(downloads_folder, file_name)

        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logging.info(f"Downloaded file: {file_path}")
        return file_path
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading file: {e}")
        raise




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
def get_text_message_input(wa_id, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def create_interactive_json(header_text, body_text, footer_text, button_text, sections):
    """
        Версия interactive сообщения ( Внутри списка )
        В каждой секции списка может быть максимум 10 кнопок
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

def create_button_interactive_json(header_text, body_text, footer_text, button_text):
    '''
     Версия interactive сообщения ( с кнопками вместо списка )
     Можно добавить максимум 3 кнопки
    '''

    json = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": header_text,
            "body": {
                "text": body_text
            },
            "footer": {
                "text": footer_text
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "123",
                            "title": button_text
                        }
                    }
                ]
            }
        }
    }

    return json

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
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        log_http_response(response)
        return response

# sends a message (first, a reply is required)
def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    logging.info(f'POST data: URL {url}\n headers: {headers}\n data: {data}')
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
    log_http_response(response)
    return response

def send_template_message_with_parameters(wa_id, template_name, code, template_data):
    """
    Sends a WhatsApp message using a template with dynamic data.

    Args:
        wa_id (str): The recipient's phone number.
        template_name (str): The name of the template.
        code (str): language code
        template_data (list): A list of dynamic data to replace placeholders.

    Returns:
        Response: The API response object.
    """

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": "Bearer " + current_app.config["ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }

    data = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": code},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type":"text", "text":template_data[i]} for i in range(len(template_data))]
                }
            ]
        }
    }

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
    log_http_response(response)
    return response

##### Higher level messages ####

# Should send a message (non-template message) to the user when he requests vacancy list
def send_vacancies(wa_id):
    """Handle incoming messages and answer with vacancy list."""
    header_text = "Вакансии"
    footer_text = "Это сообщение отправлено автоматически"
    body_text = "Отлично! У нас есть несколько открытых позиций. Пожалуйста, откройте меню для ознакомления"
    button_text = "Выбрать"

    sections = database.get_vacancies_for_interactive_message()

    data = create_interactive_json( header_text, body_text, footer_text, button_text, sections )
    send_interactive(wa_id, data)

# Should send a vacancy details
def send_vacancy_details(wa_id, vacancy):
    '''
    input - wa_id - is the whats app id of the recipient, in the format +77777777 (KZ)
    vacancy - it is an array fetched from the database by the script

    output - sends a message in data format (e.g. message is converted to JSON format)
    '''
    header_text = ""
    body_text = f'Вакансия: {vacancy[0]}\n\n Требования:\n {vacancy[1]}\n\n  Условия работы:\n {vacancy[2]}' #TODO: add new columns i guess
    footer_text = ""

    data = create_button_interactive_json(header_text, body_text, footer_text, body_text="Откликнуться")
    send_interactive(wa_id, data)

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"] # change .config recipient waid to this i guess
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]

    # Determine the type of message and handle accordingly
    message_type = message.get("type")
    message_body = None
    payload = None
    document_id = None
    interactive = None

    sent_answer = False

    db_user = database.get_user(wa_id)
    logging.info(f'Is the user with waid {wa_id} in the DB? Answer: {db_user}')
    
    if db_user == False:
        database.create_user(wa_id) # CREATE A USER

    survey_mode, step = database.filling_a_survey(wa_id)
    logging.info(f'survey mode is {survey_mode} and step is {step}')
    if survey_mode == True:
        if step <= len(survey_questions):
            message_body = message.get("text", {}).get("body", "") # answer to the previous question
            key = survey_questions[step-1]['key']
            question = survey_questions[step-1]['question']
            data = get_text_message_input(current_app.config["RECIPIENT_WAID"], question)
            database.increment_step(wa_id)
            database.save_survey_results(wa_id, key, message_body)
        else:
            # handle receiving a document    
            if message_type == 'document':
                database.set_survey_mode(wa_id, value=False)
                database.has_completed_survey(wa_id) # this should mark it as completed for the user

                document_id = message['document']['id']
                filename = message['document']['filename'].replace(' ', '_')

                try:
                    document_data = fetch_media_data(document_id)
                    file_path = get_file(document_data['url'], filename)
                except Exception as e:
                    error = f'Ошибка при обработке отправленного документа: {e}'
                    logging.error(error)
                    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], error)
                    send_message(data)
                    return jsonify({"status": "error", "message": str(e)}), 500

                data = get_text_message_input(current_app.config["RECIPIENT_WAID"], "Мы сохранили ваши данные!")

            else:
                data = get_text_message_input(current_app.config["RECIPIENT_WAID"], 'Пожалуйста, отправьте файл в качестве ответа.')
        send_message(data)


    if message_type == "text" and not survey_mode:
        message_body = message.get("text", {}).get("body", "")
        
        if ('ваканс' in message_body.lower() or 'работ' in message_body.lower()): # list vacancies # This should be deprecated
            send_vacancies(wa_id)
            sent_answer = True

        # if ('социальные льготы' in message_body):
        #     send_social_details(wa_id)
        #     sent_answer = True

        # if ('резюме' in message_body):
        #     send_template_message(wa_id, template_name="resume_form", code="ru")
        #     sent_answer = True

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
            res = send_template_message(wa_id, template_name="greeting", code="ru")
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
            # send_template_message(wa_id, template_name="resume_form", code="ru") # TODO: new flow needs to be done

            try:
                question = survey_questions[0]['question']
                data = get_text_message_input(current_app.config["RECIPIENT_WAID"], question)
                database.set_step(wa_id) # sets to 1
                database.set_survey_mode(wa_id, True)
                send_message(data)
            except KeyError:
                logging.error('No question available for the current step.')
            except Exception as e:
                logging.error(f'Error while sending question or updating session: {e}')
        
        if payload == 'Процесс найма':
            send_template_message(wa_id, template_name="hiring_conditions", code="ru")
        
        if payload == 'Связаться с HR':
            send_template_message(wa_id, template_name="help_ru", code="ru")

    elif message_type == 'interactive':
        interactive = message.get("interactive", {})
        interactive_type = interactive.get("type", "")
        if interactive_type == 'list_reply':
            vacancy_id = int(interactive.get("list_reply", {}).get("id", ""))
            vacancy = database.get_vacancy_details(vacancy_id)
            send_vacancy_details(wa_id, vacancy)
        elif interactive_type == 'button_reply':
            try:
                question = survey_questions[0]['question']
                data = get_text_message_input(current_app.config["RECIPIENT_WAID"], question)
                database.set_step(wa_id) # sets to 1
                database.set_survey_mode(wa_id, True)
                send_message(data)
            except KeyError:
                logging.error('No question available for the current step.')
            except Exception as e:
                logging.error(f'Error while sending question or updating session: {e}')

    elif message_type == "document":
        # process the document only if survey mode is enabled.
        # send_template_message(wa_id, template_name="greeting", code="ru")

        # remove this later
        document_id = message['document']['id']
        filename = message['document']['filename'].replace(' ', '_')

        try:
            document_data = fetch_media_data(document_id)
            file_path = get_file(document_data['url'], filename)
        except Exception as e:
            error = f'Ошибка при обработке отправленного документа: {e}'
            logging.error(error)
            data = get_text_message_input(current_app.config["RECIPIENT_WAID"], error)
            send_message(data)
            return jsonify({"status": "error", "message": str(e)}), 500

        data = get_text_message_input(current_app.config["RECIPIENT_WAID"], f"Мы сохранили ваши данные!Путь: {file_path}")
        send_message(data)
    


            











    
    # OpenAI Integration
    # response = generate_ai_response(message_body, wa_id, name)
    # response = process_text(response)

# def format_vacancy_message(title, requirements, tasks):
#     message = ( f"{title}\n" + "Требования:\n" + f"{requirements.replace('. ', '.\n')}\n"+"Задачи:\n" + f"{tasks.replace('. ', '.\n')}")
#     return message