import json
import os

from pymessenger2.bot import Bot

import requests

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
COUNTY_ADJACENCY = 'https://www2.census.gov/geo/docs/reference/county_adjacency.txt'
bot = Bot(ACCESS_TOKEN)


def set_get_started_button_payload():
    """Sets the 'Get Started' payload

    :returns: requests.Response object created from a
        POST request to the messenger
    """
    data = {"setting_type": "call_to_actions",
            "thread_state": "new_thread",
            "call_to_actions": [{"payload": 'GET_STARTED'}]}
    url = bot.graph_url + "/me/thread_settings?access_token={token}"
    return requests.post(url.format(token=bot.access_token),
                         headers={"Content-Type": "application/json"},
                         data=json.dumps(data))


def set_greeting_text(text):
    """Sets the greeting text for the bot

    :returns: requests.Response object created from a
        POST request to the messenger
    """
    data = {"setting_type": "greeting", "greeting": {"text": text}}
    url = bot.graph_url + "/me/thread_settings?access_token={token}"
    return requests.post(url.format(token=bot.access_token),
                         headers={"Content-Type": "application/json"},
                         data=json.dumps(data))


def send_message(recipient_id, response):
    """Sends a text message to the user

    :param recipient_id: user id to send the message to
    :param response: text to send
    """
    bot.send_text_message(recipient_id, response)


def send_start_options(recipient_id):
    """Sends Grocery, Pharmacy, Hospital and Other
    quick reply options to the user to select from

    :param recipient_id: user id to send the options to
    """
    buttons = []
    button = create_quick_reply_button('text', u'\U0001F6D2' + ' Grocery', 'GROCERY')
    buttons.append(button)
    button = create_quick_reply_button('text', u'\U0001F48A' + ' Pharmacy', 'PHARMACY')
    buttons.append(button)
    button = create_quick_reply_button('text', u'\U0001F3E5' + ' Hospital', 'HOSPITAL')
    buttons.append(button)
    button = create_quick_reply_button('text', 'Other', 'OTHER')
    buttons.append(button)
    bot.send_quick_reply(recipient_id,
                         "Where do you plan to travel today?", buttons)


def create_quick_reply_button(type, title, payload, image_url=None):
    """Creates a quick reply button

    Refer https://developers.facebook.com/docs/messenger-platform/send-messages/quick-replies#sending
    """
    if not image_url:
        button = {'content_type': type, 'title': title,
                  'payload': payload}
    else:
        button = {'content_type': type, 'title': title,
                  'payload': payload, 'image_url': image_url}
    return button


def send_notification_request(recipient_id, title, payload):
    """Sends the one time notification request

    Refer https://developers.facebook.com/docs/messenger-platform/send-messages/one-time-notification
    """
    message = {
        'attachment': {
            'type': 'template',
            'payload': {
                'template_type': 'one_time_notif_req',
                'title': title,
                'payload': payload
            }
        }
    }
    bot.send_message(recipient_id, message)


def send_follow_up_message(token, content):
    """Sends the follow up message to the subscribed users

    Refer https://developers.facebook.com/docs/messenger-platform/send-messages/one-time-notification
    """
    body = {
        'recipient': {
            'one_time_notif_token': token
        },
        'message': {
            'text': content
        }
    }
    bot.send_raw(body)


def create_county_adjacency_dict():
    """Creates a county adjacency dict of all adjacent US counties

    :returns: dict having keys as county name and values as list of
        all its adjacent counties
    """
    county_file = requests.get(COUNTY_ADJACENCY)
    data = county_file.text.translate(str.maketrans('', '', '1234567890'))
    with open('sample.txt', 'w') as f:
        f.write(data)

    county_dict = {}
    prev = ""
    with open('sample.txt') as f:
        for line in f:
            data_list = line.strip().split('\t\t')

            while("" in data_list):
                data_list.remove("")

            if len(data_list) == 2:
                county_dict[data_list[0][1:-1]] = [data_list[1][1:-1]]
                prev = data_list[0][1:-1]
            elif len(data_list) == 1:
                county_dict[prev].append(data_list[0][1:-1])
    return county_dict
