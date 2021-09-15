# imports for WebsupportAPI class
import signal
import threading

import requests
import json
import os
import logging.config
import logging.handlers
import websupportsk
import websupportsk.exceptions
import socket
import sys

import logging_handlers
import notifiers


def check_ip_address_validity(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def get_public_ipv4():
    """Request public IP address from multiple API services

    Returns:
        str: Public IP address.
    """
    ip = None
    try:
        ip = requests.get("https://api.ipify.org").text.strip()
        if not check_ip_address_validity(ip):
            raise ValueError
        logger.debug(f"ipify request succeeded, IP: {ip}")
    except (requests.ConnectionError, ValueError):
        logger.error("ipify request failed, trying aws...")
        try:
            ip = requests.get("https://checkip.amazonaws.com/").text.strip()
            if not check_ip_address_validity(ip):
                raise ValueError
            logger.debug(f"aws checkip request succeeded, IP: {ip}")
        except (requests.ConnectionError, ValueError):
            logger.error("aws checkip request failed")
            logger.error("unable to obtain public ip address from external services, exiting...")
            exit(3)
    return ip


class LoopThread:
    def __init__(self):
        self.event = threading.Event()
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.event.set()


class WebsupportDDNS:
    """Main class, check public IP address and change records with API client if address has changed."""

    def __init__(self):
        with open("config.json", "r") as config_file:
            self.config = json.load(config_file)
        try:
            self.client = websupportsk.Client(self.config['websupport']['authentication']['identifier'],
                                         self.config['websupport']['authentication']['secret_key'],
                                         self.config['websupport']['registered_domain'])
        except websupportsk.exceptions.WebsupportError as e:
            logger.error(f"Error occurred, {e.code}: {e.message}")
            exit(1)

        self.subdomains = self.config["websupport"]["subdomains"]
        ipv4 = get_public_ipv4()

        self.full_ddns_id = "websupportsk-ddns"

        # if custom ddns_id specified
        try:
            self.full_ddns_id += f"-{self.config['websupport']['ddns_id']}"
        except KeyError:
            pass

        self.notification_handlers = list()
        try:
            self.notification_handlers.append(
                notifiers.Pushover(self.config['pushover']['api_token'], self.config['pushover']['user_key']))
        except KeyError:
            pass

        try:
            self.notification_handlers.append(notifiers.Gotify(self.config['gotify']['url'], self.config['gotify']['api_token']))
        except KeyError:
            pass

    def check_note_change(self, subdomain, ipv4):
        # if record for specific subdomain with correct ipv4 already exists but doesn't have correct note comment
        records = self.client.get_records(type_="A", name=subdomain, content=ipv4)
        if records and records[0]['note'] != self.full_ddns_id:
            message = f"Subdomain `{subdomain}`, IP `{ipv4}`:: note is incorrect, editing... " \
                      f"(`{records[0]['note']}` -> `{self.full_ddns_id}`)"
            logger.info(message)
            notifiers.send_notifications(self.notification_handlers, message)

            response = self.client.edit_record(records[0]['id'], note=self.full_ddns_id)
            logger.debug(f"Response: {response}")
            return True
        elif records:
            logger.debug(f"Subdomain `{subdomain}`, IP `{ipv4}`:: note is valid")
        else:
            logger.debug(f"Subdomain `{subdomain}`, IP `{ipv4}`:: record not found, possible IP change, checking...")
        return False

    def check_ip_change(self, subdomain, ipv4):
        # if record exist bud ipv4 has changed(record must have correct note)
        records = self.client.get_records(type_="A", name=subdomain, note=self.full_ddns_id)
        if records and records[0]['content'] != ipv4:
            message = f"Subdomain `{subdomain}`, Note `{self.full_ddns_id}`:: IP address has changed, editing... " \
                      f"(`{records[0]['content']}` -> `{ipv4}`)"
            logger.info(message)
            notifiers.send_notifications(self.notification_handlers, message)

            response = self.client.edit_record(records[0]['id'], content=ipv4)
            logger.debug(f"Response: {response}")
            return True
        elif records:
            logger.debug(f"Subdomain `{subdomain}`, Note `{self.full_ddns_id}`:: IP address valid, no changes made.")
        else:
            logger.debug(f"Subdomain `{subdomain}`, Note `{self.full_ddns_id}`:: Record non-existent, will proceed "
                         f"to generation of new one...")
        return False

    def check_missing_records(self, subdomain, ipv4):
        records = self.client.get_records(type_="A", name=subdomain, note=self.full_ddns_id)
        # if record doesn't exit
        if not records:
            response = self.client.create_record(type_="A", name=subdomain, content=ipv4, note=self.full_ddns_id)
            message = f"Creating record: Subdomain `{subdomain}`, IP `{ipv4}`, Note `{self.full_ddns_id}`"
            logger.info(message)
            notifiers.send_notifications(self.notification_handlers, message)

            logger.debug(f"Response: {response}")
            return True
        else:
            return False

    def check_redundant_records(self):
        logger.debug("SEARCHING FOR SUBDOMAINS TO REMOVE")
        all_a_records = self.client.get_records(type_="A", note=self.full_ddns_id)
        removed = 0
        for r in all_a_records:
            if r['note'] == self.full_ddns_id:
                if r['name'] not in self.subdomains:
                    self.client.delete_record(r['id'])
                    removed += 1

        if removed > 0:
            logger.info(f"Removed {removed} redundant record(s)")
            return True
        else:
            return False

    def run_update(self):
        ipv4 = get_public_ipv4()

        change_occurred = False
        for subdomain in self.subdomains:
            if (
                self.check_note_change(subdomain, ipv4) |
                self.check_ip_change(subdomain, ipv4) |
                self.check_missing_records(subdomain, ipv4) |
                self.check_redundant_records()
            ):
                change_occurred = True

        if not change_occurred:
            logger.info("No change occurred")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    logger = logging.getLogger(__name__)
    ddns = WebsupportDDNS()
    if len(sys.argv) > 1:
        if sys.argv[1] == "--repeat":
            delay = 5 * 60
            loop_thread = LoopThread()
            ddns.run_update()
            while True:
                if loop_thread.event.wait(delay):
                    break
                ddns.run_update()
        else:
            print(f"Unrecognized parameter '{sys.argv[1]}'. Exiting now.")
    else:
        ddns.run_update()
