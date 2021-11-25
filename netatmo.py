import datetime
import json
import os

import requests

DEVICEMAP = json.loads(os.environ.get("DEVICEMAP"))


class Token:
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
        print("Refreshed token valid until %s" % self._token.expire_date.strftime("%Y-%m-%d %H:%M:%S"))

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
            print("Logged in and got token valid until %s" % self._token.expire_date.strftime("%Y-%m-%d %H:%M:%S"))
            return self._token
        else:
            return self.get_token()

    def _add_webhook(self, url: str):
        self.url = url
        request = requests.get("https://api.netatmo.com/api/addwebhook?url=%s/webhook" % url,
                          headers={'Authorization': 'Bearer ' + self.get_token().access_token})
        if request.status_code != 200:
            print("Error setting webhook! " + request.json())
        else:
            js = request.json()
            if js["status"] != "ok":
                print("Error setting webhook!")


class Event:
    push_type: str
    user_id: str
    user_email: str

    event_type: str
    device_id: str
    home_id: str
    home_name: str
    camera_id: str
    event_id: str
    sub_type: str

    device_name: str

    def __str__(self):
        return self.push_type + " (" + self.event_type + ") from " + self.device_name + "@" + self.home_name

    def __init__(self, js: json):
        # print(js)
        if "push_type" in js:
            self.push_type = js["push_type"]
            self.user_id = js["user_id"]
            if js["push_type"] == "webhook_activation":
                self.user_email = js ["user"]["email"]
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
                print("Webhook activated for user %s " % self.user_email)
            else:
                self.event_type = js["event_type"]
                self.device_id = js["device_id"]
                self.home_id = js["home_id"]
                self.home_name = js["home_name"]
                self.camera_id = js["camera_id"]
                self.event_id = js["event_id"]
                self.sub_type = js["sub_type"]
                if self.device_id in DEVICEMAP:
                    self.device_name = DEVICEMAP[self.device_id]
                else:
                    self.device_name = self.device_id
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), end=": ")
                print("Event received: %s" % self)



