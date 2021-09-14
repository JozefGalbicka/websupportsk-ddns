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


def run_update():
    """Main function, check public IP address and change records with API client if address has changed."""

    client = None
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    try:
        client = websupportsk.Client(config['websupport']['authentication']['identifier'],
                                     config['websupport']['authentication']['secret_key'],
                                     config['websupport']['registered_domain'])
    except websupportsk.exceptions.WebsupportError as e:
        logger.error(f"Error occurred, {e.code}: {e.message}")
        exit(1)

    subdomains = config["websupport"]["subdomains"]
    ipv4 = get_public_ipv4()

    full_ddns_id = "websupportsk-ddns"

    # if custom ddns_id specified

    notification_handlers = list()
    try:
        full_ddns_id += f"-{config['websupport']['ddns_id']}"
    except KeyError:
        pass

    try:
        notification_handlers.append(
            notifiers.Pushover(config['pushover']['api_token'], config['pushover']['user_key']))
    except KeyError:
        pass

    try:
        notification_handlers.append(notifiers.Gotify(config['gotify']['url'], config['gotify']['api_token']))
    except KeyError:
        pass

    change_occurred = False
    for subdomain in subdomains:
        # logger.debug(f"CHECKING SUBDOMAIN: {subdomain}")

        # if record for specific subdomain with correct ipv4 already exists but doesn't have correct note comment
        records = client.get_records(type_="A", name=subdomain, content=ipv4)
        if records and records[0]['note'] != full_ddns_id:
            message = f"Subdomain `{subdomain}`, IP `{ipv4}`:: note is incorrect, editing... " \
                      f"(`{records[0]['note']}` -> `{full_ddns_id}`)"
            logger.info(message)
            notifiers.send_notifications(notification_handlers, message)

            response = client.edit_record(records[0]['id'], note=full_ddns_id)
            logger.debug(f"Response: {response}")
            change_occurred = True
        elif records:
            logger.debug(f"Subdomain `{subdomain}`, IP `{ipv4}`:: note is valid")
        else:
            logger.debug(f"Subdomain `{subdomain}`, IP `{ipv4}`:: record not found, possible IP change, checking...")

        # if record exist bud ipv4 has changed(record must have correct note)
        records = client.get_records(type_="A", name=subdomain, note=full_ddns_id)
        if records and records[0]['content'] != ipv4:
            message = f"Subdomain `{subdomain}`, Note `{full_ddns_id}`:: IP address has changed, editing... " \
                      f"(`{records[0]['content']}` -> `{ipv4}`)"
            logger.info(message)
            notifiers.send_notifications(notification_handlers, message)

            response = client.edit_record(records[0]['id'], content=ipv4)
            logger.debug(f"Response: {response}")
            change_occurred = True
        elif records:
            logger.debug(f"Subdomain `{subdomain}`, Note `{full_ddns_id}`:: IP address valid, no changes made.")
        else:
            logger.debug(f"Subdomain `{subdomain}`, Note `{full_ddns_id}`:: Record non-existent, will proceed "
                         f"to generation of new one...")

        # if record doesn't exit
        if not records:
            response = client.create_record(type_="A", name=subdomain, content=ipv4, note=full_ddns_id)
            message = f"Creating record: Subdomain `{subdomain}`, IP `{ipv4}`, Note `{full_ddns_id}`"
            logger.info(message)
            notifiers.send_notifications(notification_handlers, message)

            logger.debug(f"Response: {response}")
            change_occurred = True

    logger.debug("SEARCHING FOR SUBDOMAINS TO REMOVE")
    all_a_records = client.get_records(type_="A", note=full_ddns_id)
    removed = 0
    for r in all_a_records:
        if r['note'] == full_ddns_id:
            if r['name'] not in subdomains:
                client.delete_record(r['id'])
                removed += 1

    if removed > 0:
        change_occurred = True
        logger.info(f"Removed {removed} redundant record(s)")

    if not change_occurred:
        logger.info("No change occurred")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    logger = logging.getLogger(__name__)
    if len(sys.argv) > 1:
        if sys.argv[1] == "--repeat":
            delay = 5 * 60
            loop_thread = LoopThread()
            run_update()
            while True:
                if loop_thread.event.wait(delay):
                    break
                run_update()
        else:
            print(f"Unrecognized parameter '{sys.argv[1]}'. Exiting now.")
    else:
        run_update()
