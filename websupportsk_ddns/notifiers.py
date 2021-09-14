import requests
import logging

logger = logging.getLogger(__name__)


def send_notifications(notifiers, message):
    for notifier in notifiers:
        notifier.send_notification(message)


class Pushover:
    def __init__(self, api_token, user_key):
        self.api_token = api_token
        self.user_key = user_key
        self.url = "https://api.pushover.net/1/messages.json"

    def send_notification(self, text):
        r = requests.post(self.url, data={
            "token": self.api_token,
            "user": self.user_key,
            "message": text
        })
        logger.debug(f"Pushover notification response: {r.text}")
        if "errors" in r.text:
            logger.error(f"Pushover error occured: {r.text}")


class Gotify:
    def __init__(self, url, api_token):
        self.api_token = api_token
        self.url = f"http://{url}/message?token={api_token}"

    def send_notification(self, text):
        r = requests.post(self.url, data={
            "message": text
        })
        logger.debug(f"Gotify notification response: {r.text}")
        if "error" in r.text:
            logger.error(f"Gotify error occured: {r.text}")