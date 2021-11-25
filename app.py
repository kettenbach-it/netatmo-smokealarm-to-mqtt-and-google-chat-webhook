import os

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

    # MQTT
    # MQTT_SERVER = os.environ['MQTT_SERVER']
    # MQTT_CLIENTID = os.environ['MQTT_CLIENTID']
    # MQTT_USER = os.environ['MQTT_USER']
    # MQTT_PASS = os.environ['MQTT_PASS']
    #
    # Google Chat
    # GCHAT_WEBHOOK_URL = os.environ['GCHAT_WEBHOOK_URL']

except Exception as exc:
    print("Missing environment variable(s) " + str(exc))
    exit(-1)


api: Netatmo = Netatmo(CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, MY_URL)

app = Flask(__name__)


@app.route('/', methods=['GET'])
def get_root():
    api.login()
    return "Logged in!", 200


@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    event = Event(request.json)
    return "", 200


if __name__ == "__main__":
    app.run()
