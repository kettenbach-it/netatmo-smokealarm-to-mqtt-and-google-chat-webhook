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
    print("Missing environment variable(s) " + str(exc), flush=True)
    exit(-1)


api: Netatmo = Netatmo(CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, MY_URL)
mqtt_client = mqtt.Client(client_id=CLIENT_ID)
mqtt_client.username_pw_set(username=MQTT_USER, password=MQTT_PASS)
mqtt_client.connect(MQTT_SERVER, port=1883)
mqtt_client.publish(MQTT_TOPIC + "LAST_START_DATETIME", payload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
mqtt_client.disconnect()
app = Flask(__name__)


@app.route('/', methods=['GET'])
def get_root():
    api.login()
    return "Logged in!", 200


@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    if api.login():
        return "ok", 200
    else:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
        print("Healthcheck Error", flush=True)
        return "error", 400


@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        event = Event(request.json)
    except Exception as error:
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
        print(f"Error in parsing request! {str(error)}\n{request.json}", end="...", flush=True)
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
        except Exception as response_error:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
            print(f"Error in sending to Google chat: {str(response_error)}", flush=True)
        return f"Error in parsing json! {str(error)}\n{request.json}", 400

    # Events: https://dev.netatmo.com/apidocumentation/security#events
    if event.is_alert:
        # Publish to MQTT
        mqtt_client.connect(MQTT_SERVER, port=1883)
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
        print("Sending to MQTT:", end="... ", flush=True)
        result1 = mqtt_client.publish(MQTT_TOPIC + "LAST_EVENT_DATETIME",
                            payload=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        result2 = mqtt_client.publish(MQTT_TOPIC + "LAST_EVENT_PAYLOAD", payload=event.json_dumps())
        if event.is_severe:
            mqtt_client.publish(MQTT_TOPIC + "ALERT", 1)
        print(f"Results: {str(result1)}, {str(result2)}", flush=True)
        mqtt_client.disconnect()
        # Send to Google Chat
        header = {
            'title': f"{event.device_name}@{event.home_name} - Smoke Detector Event",
            'subtitle': "At: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        widget = {'textParagraph': {
            'text': f"<b>{event.event_type_text} {event.sub_type_text}</b> on "
                    f"{event.device_name}@{event.home_name} at {event.datetime.strftime('%Y-%m-%d %H:%M:%S')}"
                    f"\n(MQTT sending results where: {str(result1)}, {str(result2)}"
        }}
        try:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
            print("Sending to Google Chat:", end="... ")
            response = requests.post(GCHAT_WEBHOOK_URL, json={
                'cards': [
                    {
                        'header': header,
                        'sections': [{'widgets': [widget]}],
                    }
                ]
            })
            if response.status_code == 200:
                print("Done!", flush=True)
            else:
                print("ERROR: " + str(response.status_code) + " - " + response.text, flush=True)
        except TypeError as error:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
            print(f"Error: {str(error)}", flush=True)
    return "", 200


# Login in the background
def login_threaded_task():
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ", flush=True)
    print("Waiting to login....", flush=True)
    time.sleep(5)
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ", flush=True)
    api.login()


thread = Thread(target=login_threaded_task)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run()
