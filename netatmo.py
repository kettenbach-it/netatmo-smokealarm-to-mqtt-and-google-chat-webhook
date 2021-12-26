import datetime
import json
import os

import requests

try:
    DEVICEMAP = json.loads(os.environ.get("DEVICEMAP"))
except TypeError as error:
    DEVICEMAP = {}


class Token:
    # For a HA ready version, this token needs to be stored in redis
    access_token: str
    refresh_token: str
    expires_in: int
    expire_date: datetime.datetime

    def __init__(self, access_token: str, refresh_token: str, expires_in: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.set_expire_date(expires_in)

    def __str__(self):
        return self.access_token + " - " + self.refresh_token + " - " + str(self.expire_date)

    def set_expire_date(self, expires_in: int):
        self.expire_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)


class Netatmo:
    client_id: str
    client_secret: str
    username: str
    password: str
    url: str

    _token: Token
    _logged_in = False

    def __init__(self, client_id: str, client_secret: str, username: str, password: str, url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.url = url

    def __str__(self):
        return str(self.get_token())

    def get_token(self) -> Token:
        if self._token.expire_date <= datetime.datetime.now():
            self.refresh_token()
        return self._token

    def refresh_token(self):
        js = requests.post("https://api.netatmo.com/oauth2/token", data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token
        }).json()
        self._token = Token(js["access_token"], js["refresh_token"], js["expires_in"])
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
        print("Refreshed token valid until %s" % self._token.expire_date.strftime("%Y-%m-%d %H:%M:%S"), flush=True)

    def login(self) -> Token:
        if not self._logged_in:
            js = requests.post("https://api.netatmo.com/oauth2/token", data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "password",
                "scope": "read_smokedetector",
                "username": self.username,
                "password": self.password
            }).json()
            self._token = Token(js["access_token"], js["refresh_token"], js["expires_in"])
            self._add_webhook(self.url)
            self._logged_in = True
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
            print("Logged in and got token valid until %s" % self._token.expire_date.strftime("%Y-%m-%d %H:%M:%S"),
                  flush=True)
            return self._token
        else:
            return self.get_token()

    def _add_webhook(self, url: str):
        self.url = url
        request = requests.get("https://api.netatmo.com/api/addwebhook?url=%s/webhook" % url,
                               headers={'Authorization': 'Bearer ' + self.get_token().access_token})
        if request.status_code != 200:
            print("Error setting webhook! " + request.json(), flush=True)
        else:
            js = request.json()
            if js["status"] != "ok":
                print("Error setting webhook!", flush=True)


class Event:
    """
    https://dev.netatmo.com/apidocumentation/security#events

    hush - Smoke Detector - When the smoke detection is activated or deactivated
    smoke - Smoke Detector - When smoke is detected or smoke is cleared
    tampered - Smoke Detector - When smoke detector is ready or tampered
    wifi_status - Smoke Detector - When wifi status is updated
    battery_status - Smoke Detector - When battery status is too low
    detection_chamber_status - Smoke Detector - When the detection chamber is dusty or clean
    sound_test - Smoke Detector - Sound test result
    """

    is_alert: bool = False
    is_severe: bool = False

    push_type: str = ""
    user_id: str = ""
    user_email: str = ""

    event_type: str = ""
    event_type_text: str = ""
    sub_type: str = ""
    sub_type_text: str = ""

    device_id: str = ""
    home_id: str = ""
    home_name: str = ""
    camera_id: str = ""
    event_id: str = ""

    device_name: str = ""

    datetime: datetime.datetime

    _event_types = {
        "hush": "The smoke detection is",
        "smoke": "SMOKE IS",
        "tampered": "The smoke detector is",
        "wifi_status": "The wifi status is updated to:",
        "battery_status": "The battery status is",
        "detection_chamber_status": "The detection chamber is",
        "sound_test": "Sound test result:"
    }

    _sub_types = {
        "hush": {
            0: "active",
            1: "temporarily disabled"
        },
        "smoke": {
            0: "Cleared!",
            1: "DETECTED!! ALERT!!!!!!"
        },
        "tampered": {
            0: "ready",
            1: "TAMPERED!"
        },
        "wifi_status": {
            0: "ERROR!",
            1: "Ok"
        },
        "battery_status": {
            0: "LOW!",
            1: "VERY LOW!!!"
        },
        "detection_chamber_status": {
            0: "Clean",
            1: "DUSTY!"
        },
        "sound_test": {
            0: "Ok",
            1: "ERROR!"
        }
    }

    def __str__(self):
        output = f"{self.event_type_text} <{self.sub_type_text}> on {self.device_name}@{self.home_name}. " \
                 f"(Push-Type: {self.push_type})"
        return output

    def json_dumps(self):
        return json.dumps({
            "event_id": self.event_id,
            "is_severe": self.is_severe,
            "push_type": self.push_type,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "event_type": self.event_type,
            "message": self.event_type_text + " " + self.sub_type_text + " on " + self.device_name + "@" + self.home_name,
            "sub_type": self.sub_type,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "home_id": self.home_id,
            "home_name": self.home_name,
            "datime": self.datetime.strftime("%Y-%m-%d %H:%M:%S")
        })

    def __init__(self, js: json):
        if "push_type" in js:
            self.push_type = js["push_type"]
            self.user_id = js["user_id"]
            self.datetime = datetime.datetime.now()
            if js["push_type"] == "webhook_activation":
                self.user_email = js["user"]["email"]
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
                print(f"Webhook activated for user {self.user_email}", flush=True)
            else:
                self.event_type = js["event_type"]
                try:
                    self.event_type_text = self._event_types[self.event_type]
                except KeyError:
                    self.event_type_text = "Unknown event type"
                self.sub_type = js["sub_type"]
                try:
                    self.sub_type_text = self._sub_types[self.event_type][self.sub_type]
                except KeyError:
                    self.sub_type_text = "Unknown event subtype"
                self.device_id = js["device_id"]
                self.home_id = js["home_id"]
                self.home_name = js["home_name"]
                self.camera_id = js["camera_id"]
                self.event_id = js["event_id"]
                if self.device_id in DEVICEMAP:
                    self.device_name = DEVICEMAP[self.device_id]
                else:
                    self.device_name = self.device_id
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
                print(f"Event received: {self}", flush=True)

                self.is_alert = True
                if self.event_type == "smoke" and self.sub_type == "1":
                    self.is_severe = True
