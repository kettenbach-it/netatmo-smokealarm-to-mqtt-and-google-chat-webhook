import datetime
import json
import os
import time
from threading import Thread
import paho.mqtt.client as mqtt

import requests
from flask import Flask, request

from netatmo import Netatmo, Event

try:
    # Netatmo https://dev.netatmo.com/apidocumentation/oauth#client-credential
    # https://dev.netatmo.com/apps/6195e6e5463afd042d48c90a#form
    # The URL this API is listening on (needed to install webhook)
    MY_URL = os.environ['MY_URL']
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
    USERNAME = os.environ['USERNAME']
    PASSWORD = os.environ['PASSWORD']

    # Google Chat
    GCHAT_WEBHOOK_URL = os.environ['GCHAT_WEBHOOK_URL']

    # MQTT
    MQTT_SERVER = os.environ['MQTT_SERVER']
    MQTT_CLIENTID = os.environ['MQTT_CLIENTID']
    MQTT_USER = os.environ['MQTT_USER']
    MQTT_PASS = os.environ['MQTT_PASS']
    MQTT_TOPIC = os.environ['MQTT_TOPIC']

except Exception as exc:
    print("Missing environment variable(s) " + str(exc))
    exit(-1)


api: Netatmo = Netatmo(CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, MY_URL)
mqtt_client = mqtt.Client(client_id=CLIENT_ID)
mqtt_client.username_pw_set(username=MQTT_USER, password=MQTT_PASS)
mqtt_client.connect(MQTT_SERVER, port=1883)
mqtt_client.publish(MQTT_TOPIC + "LAST_START_DATETIME", payload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
app = Flask(__name__)


@app.route('/', methods=['GET'])
def get_root():
    api.login()
    return "Logged in!", 200


@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        event = Event(request.json)
        # Events: https://dev.netatmo.com/apidocumentation/security#events
        if event.is_alert:
            # Publish to MQTT
            mqtt_client.publish(MQTT_TOPIC + "LAST_EVENT_DATETIME",
                                payload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            mqtt_client.publish(MQTT_TOPIC + "LAST_EVENT_PAYLOAD", payload=event.json_dumps())
            if event.is_severe:
                mqtt_client.publish(MQTT_TOPIC + "ALERT", 1)

            # Send to Google Chat
            header = {
                'title': f"{event.device_name}@{event.home_name} - Smoke Detector Event",
                'subtitle': "At: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            widget = {'textParagraph': {
                'text': f"<b>{event.event_type_text} {event.sub_type_text}</b> on "
                        f"{event.device_name}@{event.home_name} at {event.datetime.strftime('%Y-%m-%d %H:%M:%S')}"}}
            try:
                response = requests.post(GCHAT_WEBHOOK_URL, json={
                    'cards': [
                        {
                            'header': header,
                            'sections': [{'widgets': [widget]}],
                        }
                    ]
                })
            except TypeError as error:
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
                print(f"Error: {str(error)}")
        return "", 200
    except Exception as error:
        header = {
            'title': "Unknown Smoke Detector Event",
            'subtitle': "At: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        widget = {
            'textParagraph':
                {
                    'text': f"Please check the logs of the API!\n The error was:\n {str(error)}\n"
                            f"The request payload was: {str(request.json)}"
                }
        }
        try:
            response = requests.post(GCHAT_WEBHOOK_URL, json={
                'cards': [
                    {
                        'header': header,
                        'sections': [{'widgets': [widget]}],
                    }
                ]
            })
        except TypeError as error:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
            print(f"Error: {str(error)}")
        return f"Error in parsing json! {str(error)}", 400


# Login in the background
def login_threaded_task():
    time.sleep(1)
    api.login()


thread = Thread(target=login_threaded_task)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run()
