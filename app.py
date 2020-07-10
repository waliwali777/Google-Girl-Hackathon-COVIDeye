import codecs
import csv
import os
import sched
import threading
import time
import urllib

from flask import Flask, render_template, request

from flask_classful import FlaskView, route

import googlemaps

from helpers import create_county_adjacency_dict, \
    create_quick_reply_button, send_follow_up_message, \
    send_message, send_notification_request, send_start_options, \
    set_get_started_button_payload, set_greeting_text

from pymessenger2.bot import Bot
from pymessenger2.buttons import URLButton

import requests

app = Flask(__name__)
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
MAPS_API_TOKEN = os.environ.get('MAPS_API_TOKEN')
COUNTY_DATA_URL = 'https://raw.githubusercontent.com/' \
    'nytimes/covid-19-data/master/us-counties.csv'
bot = Bot(ACCESS_TOKEN)


class App(FlaskView):
    def __init__(self):
        """Intializes a new instance with following:
        Googlemaps client, US County Adjacency dict and
        Scheduler object
        """
        self.map_connect = googlemaps.Client(key=MAPS_API_TOKEN)
        self.county_adjacency = create_county_adjacency_dict()
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.thread = None
        self.user_data = {}
        self.cache = {}

    @route("/")
    def index(self):
        return render_template("index.html")

    @route("/webhook", methods=['GET', 'POST'])
    def start(self):
        # Actions when GET requests are received
        if request.method == 'GET':
            if request.args.get("hub.verify_token") == VERIFY_TOKEN:
                return request.args.get("hub.challenge")
            else:
                return 'Invalid verification token'
        # Actions when POST requests are received
        else:
            output = request.get_json()
            for event in output['entry']:
                messaging = event['messaging']
                for message in messaging:
                    # Used when payload is received from a postback button
                    if message.get('postback'):
                        payload = message['postback']['payload']
                        if payload == 'GET_STARTED':
                            set_greeting_text('Hi {{user_first_name}}!')
                            set_get_started_button_payload()
                            # Store the sender id to send response back to
                            recipient_id = message['sender']['id']
                            if recipient_id not in self.user_data.keys():
                                self.user_data[recipient_id] = {}
                            bot.send_action(recipient_id, 'typing_on')
                            send_message(recipient_id, 'Welcome to En route to safety! (USA only)')
                            time.sleep(2)
                            # Send quick reply options Grocery, Pharmacy,
                            # Hospital or Other to the user
                            send_start_options(recipient_id)

                    # Used when a user subscribes to one time notif
                    if message.get('optin'):
                        payload = message['optin']['payload']
                        if payload == 'SUBSCRIBE_USER':
                            token = message['optin']['one_time_notif_token']
                            recipient_id = message['sender']['id']
                            # Initialize a thread if it doesn't exist
                            if not self.thread:
                                self.thread = threading.Thread(target=self.subscriber_queue, args=(recipient_id, token,))
                                self.thread.start()
                            # If the thread exists, check if its still alive
                            else:
                                # If thread is not alive, initialize it
                                if not self.thread.is_alive():
                                    self.thread = threading.Thread(target=self.subscriber_queue, args=(recipient_id, token,))
                                    self.thread.start()
                                else:
                                    # The thread exists, add the notif request to the scheduler queue
                                    # such that it sends the notification after 24 hours and 1 minute
                                    self.scheduler.enter(86460, 1, self.send_one_time_notification, (recipient_id, token,))
                            send_message(recipient_id, 'Thanks! You are now subscribed to daily cases updates of {}. According to Facebook\'s Privacy Policy, you need to subscribe every 24 hours to keep receiving updates'.format(self.user_data[recipient_id]['subscribe_county']))

                    if message.get('message'):
                        recipient_id = message['sender']['id']
                        # Create the user entry in self.user_data dict if
                        # it doesn't exist already
                        if recipient_id not in self.user_data.keys():
                            self.user_data[recipient_id] = {}
                        qr = message['message'].get('quick_reply')
                        txt = message['message'].get('text')

                        # Used when the message is a quick reply
                        if qr and txt:
                            payload = message['message']['quick_reply']['payload']
                            # Set destination type and icon based on user selection
                            if (payload == 'GROCERY' or payload == 'PHARMACY' or payload == 'HOSPITAL' or payload == 'OTHER'):
                                if payload == 'GROCERY':
                                    self.user_data[recipient_id]['dest_type'] = "Grocery"
                                    self.user_data[recipient_id]['dest_type_icon'] = u'\U0001F6D2'

                                if payload == 'PHARMACY':
                                    self.user_data[recipient_id]['dest_type'] = "Pharmacy"
                                    self.user_data[recipient_id]['dest_type_icon'] = u'\U0001F48A'

                                if payload == 'HOSPITAL':
                                    self.user_data[recipient_id]['dest_type'] = "Hospital"
                                    self.user_data[recipient_id]['dest_type_icon'] = u'\U0001F3E5'

                                if payload == 'OTHER':
                                    self.user_data[recipient_id]['dest_type'] = None
                                send_message(recipient_id, 'Thanks, please enter the destination location now')

                            # Set search county based on user input
                            if (payload == 'SEARCH_ORIG_COUNTY' or payload == 'SEARCH_SAFER_COUNTY'):
                                try:
                                    if payload == 'SEARCH_ORIG_COUNTY':
                                        search_county = self.user_data[recipient_id]['orig_county'] + ', ' + self.user_data[recipient_id]['state_short']
                                    else:
                                        search_county = self.user_data[recipient_id]['safer_county']
                                    self.user_data[recipient_id]['subscribe_county'] = search_county
                                    # Send a Google Maps url to the user based on previous inputs
                                    if self.user_data[recipient_id].get('dest_type'):
                                        dest_type = self.user_data[recipient_id]['dest_type']
                                        # Seach for currently open businesses of the user specified type
                                        search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json?"
                                        places_search = requests.get(
                                            search_url + 'query=' + dest_type + '+' + '+'.join(str(search_county).split()) + '&opennow=true&key=' + MAPS_API_TOKEN)
                                        places_list = places_search.json()['results']
                                        buttons = []
                                        # Provide upto 2 results as max limit is 3 for URL buttons
                                        result_number = 2 if len(places_list) > 2 else len(places_list)
                                        for number in range(result_number):
                                            place_address = places_list[number]['formatted_address']
                                            place_url = 'https://www.google.com/maps/place/' + '+'.join(place_address.split())
                                            buttons.append(URLButton(title=places_list[number]['name'], url=place_url))
                                        # Third button will provide a list of all available options
                                        buttons.append(URLButton(title=self.user_data[recipient_id]['dest_type_icon'] + ' ' + dest_type + ' (All Options)',
                                                                 url="https://maps.google.com/?q={}".format(dest_type + '+' + '+'.join(str(search_county).split()))))
                                        bot.send_button_message(recipient_id, "Click below to search for {} options in {}".format(dest_type, search_county), buttons)
                                    else:
                                        buttons = []
                                        buttons.append(URLButton(title=search_county,
                                                                 url="https://maps.google.com/?q={}".format('+'.join(str(search_county).split()))))
                                        bot.send_button_message(recipient_id, "Click below to search within {}".format(search_county), buttons)
                                except KeyError:
                                    send_message(recipient_id, "Oops, error occured..")
                                finally:
                                    # Ask if the user wants to search for another location
                                    buttons = []
                                    button = create_quick_reply_button('text', 'Yes', 'SEARCH_YES')
                                    buttons.append(button)
                                    button = create_quick_reply_button('text', 'No', 'SEARCH_NO')
                                    buttons.append(button)
                                    time.sleep(5)
                                    bot.send_quick_reply(recipient_id, 'Do you want to search for another place?', buttons)

                            if payload == 'SEARCH_YES':
                                send_start_options(recipient_id)

                            if payload == 'SEARCH_NO':
                                # Send subscribe option to user
                                if self.user_data[recipient_id].get('subscribe_county'):
                                    send_message(recipient_id, 'Click \'Notify Me\' to subscribe for updates')
                                    send_notification_request(recipient_id, self.user_data[recipient_id]['subscribe_county'], 'SUBSCRIBE_USER')
                                send_message(recipient_id, 'Message \'Start\' anytime to get searching again')
                                time.sleep(2)
                                send_message(recipient_id, 'Thank you, visit again!')

                        # Used when the message is a text
                        if txt and not qr:
                            address = message['message']['text']
                            if address.lower() == 'start':
                                send_start_options(recipient_id)
                                continue
                            bot.send_action(recipient_id, 'mark_seen')
                            time.sleep(2)
                            send_message(recipient_id, "Searching...")
                            bot.send_action(recipient_id, 'typing_on')
                            result_list = self._search_address(address)
                            if result_list:
                                self.user_data[recipient_id]['orig_county'] = result_list[0]
                                self.user_data[recipient_id]['state'] = state = result_list[1]
                                self.user_data[recipient_id]['state_short'] = result_list[2]
                                cases = result_list[3]
                                deaths = result_list[4]
                                date_updated = result_list[5]
                                self.user_data[recipient_id]['safer_county'] = result_list[6]
                                safer_county_cases = result_list[7]
                            else:
                                send_message(recipient_id, "Invalid address, try again")
                                break

                            try:
                                if cases:
                                    # Send total cases, deaths and date updated of the county from user input
                                    send_message(recipient_id, self.user_data[recipient_id]['orig_county'] + ", " + state)
                                    send_message(recipient_id, "Total positive cases: {}, Deaths: {} as of {}".
                                                 format(cases, deaths, date_updated))
                                    time.sleep(2)
                                    # Send the safest adjacent county found to the user input county with its cases
                                    send_message(recipient_id, "A safer nearby county we've found is {} with {} cases".
                                                 format(self.user_data[recipient_id]['safer_county'], safer_county_cases))
                                    # Ask which county does user want to search in
                                    buttons = []
                                    button = create_quick_reply_button('text', self.user_data[recipient_id]['orig_county'] + ', ' + self.user_data[recipient_id]['state_short'], 'SEARCH_ORIG_COUNTY')
                                    buttons.append(button)
                                    button = create_quick_reply_button('text', self.user_data[recipient_id]['safer_county'], 'SEARCH_SAFER_COUNTY')
                                    buttons.append(button)
                                    bot.send_quick_reply(recipient_id, "Which county do you want to search in?", buttons)

                            except UnboundLocalError:
                                send_message(recipient_id, "Sorry no data found")
                                break

        return "Success"

    def _search_address(self, address):
        """Search the address from the given user input

        :param address: The user input address to search for
        :returns: a list of following values in specified order
            county: search result county name (Ex- Dallas County, TX)
            state: search result state name in long format (Ex- Texas)
            state_short: search result state name in short (Ex- TX)
            cases: search result number of cases (Ex- 4324)
            deaths: search result number of deaths (Ex- 213)
            date_updated: search result date updated (Ex- 2020-04-12)
            safer_county: safer county name from adjacent search result
                counties (Ex- Rockwall County, TX)
            safer_county_cases: safer county number of cases (Ex- 1234)
        """
        try:
            result = self.map_connect.geocode(address)[0]
            state = state_short = county = safer_county = ""
            counties = {}
            for element in result['address_components']:
                for key, value in element.items():
                    if (key == 'types' and 'administrative_area_level_1' in value):
                        state_short = element['short_name']
                        state = element['long_name']
            for element in result['address_components']:
                for key, value in element.items():
                    if (key == 'types' and 'administrative_area_level_2' in value):
                        county = element['short_name']
                        response = urllib.request.urlopen(COUNTY_DATA_URL)
                        csv_reader = csv.reader(codecs.iterdecode(response, 'utf-8'))
                        for row in csv_reader:
                            if (row[2].lower() == state.lower() and state):
                                if row[1].lower() in county.lower():
                                    date_updated = row[0]
                                    cases = row[4]
                                    deaths = row[5]
            for county_result in self.county_adjacency[county + ", " + state_short]:
                response = urllib.request.urlopen(COUNTY_DATA_URL)
                csv_reader = csv.reader(codecs.iterdecode(response, 'utf-8'))
                for row in csv_reader:
                    if (row[2].lower() == state.lower() and state):
                        if row[1].lower() in county_result.lower():
                            counties[county_result] = int(row[4])
            if counties:
                safer_county = min(counties, key=counties.get)
                safer_county_cases = counties[safer_county]

            return [county, state, state_short, cases, deaths, date_updated, safer_county, safer_county_cases]
        except Exception:
            return None

    def send_one_time_notification(self, recipient_id, token):
        """Sends one time notification to the subscribed user

        :param recipient_id: user id key to search stored values
            from user_data dict
        :param token: one time notif token issues when user subscribed
        :returns: None
        """
        subscriber_county_cases = None
        search_state = self.user_data[recipient_id]['state']
        county_name = str(self.user_data[recipient_id]['subscribe_county']).split()[0]
        response = urllib.request.urlopen(COUNTY_DATA_URL)
        csv_reader = csv.reader(codecs.iterdecode(response, 'utf-8'))
        for row in csv_reader:
            if row[2].lower() == search_state.lower():
                if county_name.lower() == row[1].lower():
                    subscriber_county_cases = row[4]
        if self.user_data[recipient_id].get('subscribe_county') and subscriber_county_cases:
            send_follow_up_message(token, "Number of total cases for {} are {}".format(self.user_data[recipient_id]['subscribe_county'], subscriber_county_cases))
        if self.user_data[recipient_id].get('state_short'):
            state_metadata_url = "https://covidtracking.com/api/v1/states/{}/info.json".format(self.user_data[recipient_id]['state_short'].lower())
            state_metadata = requests.get(state_metadata_url)
            if state_metadata.json()['covid19Site']:
                button = []
                button.append(URLButton(title="Official {} COVID site".format(self.user_data[recipient_id]['state_short']), url=str(state_metadata.json()['covid19Site'])))
                bot.send_button_message(recipient_id, 'Checkout the official state COVID info website', button)
        send_notification_request(recipient_id, self.user_data[recipient_id]['subscribe_county'], 'SUBSCRIBE_USER')

    def subscriber_queue(self, recipient_id, token):
        """Schedules the subscriber for receiving updates

        :param recipient_id: user id key to search stored values
            from user_data dict
        :param token: one time notif token issues when user subscribed
        :returns: None
        """
        # send the notification after 24 hours and 1 minute
        self.scheduler.enter(86460, 1, self.send_one_time_notification, (recipient_id, token,))
        self.scheduler.run()


App.register(app, route_base="/")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
