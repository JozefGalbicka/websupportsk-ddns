# imports for WebsupportAPI class
import hmac
import hashlib
import time
import requests
from datetime import datetime, timezone
import json

import logging
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_public_ip4():
    ip4 = None
    try:
        ip4 = requests.get("https://api.ipify.org").text
        logger.info(f"ipify request succeeded, IP: {ip4}")
    except requests.ConnectionError:
        logger.error("ipify request failed")
        try:
            ip4 = requests.get("https://checkip.amazonaws.com/").text
            logger.info(f"aws checkip request succeeded, IP: {ip4}")
        except requests.ConnectionError:
            logger.error("aws checkip request failed")
            logger.error("unable to obtain public ip address from external services")
    return ip4


class WebsupportClient:
    def __init__(self, identifier, secret_key, domain):
        self.default_path = "/v1/user/self"
        self.api = "https://rest.websupport.sk"
        self.query = ""  # query part is optional and may be empty
        self.domain = domain

        # creating signature
        method = "GET"
        timestamp = int(time.time())
        canonical_request = "%s %s %s" % (method, self.default_path, timestamp)
        signature = hmac.new(bytes(secret_key, 'UTF-8'), bytes(canonical_request, 'UTF-8'), hashlib.sha1).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Date": datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        }

        # creating session
        self.s = requests.Session()
        self.s.auth = (identifier, signature)
        self.s.headers.update(headers)
        login_response = self.s.get("%s%s%s" % (self.api, self.default_path, self.query)).content

    def get_records(self, type_=None, id_=None, name=None, content=None, ttl=None, note=None):
        # create dict of arguments passed, filter out 'None' values and 'self' argument, rename keys(remove "_"
        # trailing)
        args = {k.replace("_", ""): v for k, v in locals().items() if v is not None and k != 'self'}
        # get data from api
        data = json.loads(self.s.get(f"{self.api}{self.default_path}/zone/{self.domain}/record{self.query}").content)
        items = data["items"]

        records = list()
        for item in items:
            shared_keys = args.keys() & item.keys()
            # intersection dict of shared items
            intersection_dict = {k: item[k] for k in shared_keys if item[k] == args[k]}
            # record is valid only if all values from args match
            records.append(item) if len(intersection_dict) == len(args) else None

        logger.info(f"GETTING RECORDS:: arguments: {args},... found: {len(records)} record(s)")
        return records

    def create_record(self, type_, name, content, ttl=600, **kwargs):
        # print(get_records(type_=type_, name=name, content=content))

        args = {k.replace("_", ""): v for k, v in locals().items()}
        args.pop('self')
        args.pop('kwargs')
        args.update(**kwargs)
        # print(f"Creating record: type:{type_}, name:{name}, content:{content}", end="    ")
        log_response("CREATING RECORD", self.s.post(f"{self.api}{self.default_path}/zone/{self.domain}/record",
                                                    json=args).json())

    def edit_record(self, id_, **kwargs):
        log_response("EDITING RECORD", self.s.put(f"{self.api}{self.default_path}/zone/{self.domain}/record/{id_}",
                                                  json=kwargs).json())

    def delete_record(self, id_):
        log_response("DELETING RECORD", self.s.delete(f"{self.api}{self.default_path}/zone/{self.domain}/record/{id_}")
                     .json())

    # return first record found
    # TO-DO: add error handling for not found record and multiple records found
    def get_record_id(self, type_, name, **kwargs):
        record = self.get_records(type_=type_, name=name, **kwargs)
        return record[0]['id']
        # return record[0]['id'] if len(record) == 1 and type(record) == list else None


def log_response(action, r):
    r['item'].pop('zone')
    logger.info(f"{action}:: STATUS: {r['status']}, \tITEM: {r['item']}, \tERRORS: {r['errors']}")


if __name__ == "__main__":

    with open("config.json", "r") as config_file:
        config = json.load(config_file)

    client = WebsupportClient(config['websupport']['authentication']['identifier'],
                              config['websupport']['authentication']['secret_key'],
                              config['websupport']['registered_domain'])

    subdomains = config["websupport"]["subdomains"]
    ip4 = get_public_ip4()
    full_ddns_id = "websupportsk-ddns"
    try:
        ddns_id = config['websupport']['ddns_id']
        if ddns_id:
            full_ddns_id += f"-{ddns_id}"
    except KeyError:
        pass

    for subdomain in subdomains:
        logger.info(f"NOW CHECKING SUBDOMAIN: {subdomain}")
        # if record for specific subdomain with correct ip4 already exists but doesn't have note comment
        records = client.get_records(type_="A", name=subdomain, content=ip4)
        if records and records[0]['note'] != full_ddns_id:
            logger.info('EDITING RECORD:: note is incorrect, editing...')
            client.edit_record(records[0]['id'], note=full_ddns_id)
        else:
            logger.info('Record note checked, valid')

        # if record exist bud ip4 has changed
        records = client.get_records(type_="A", name=subdomain, note=full_ddns_id)
        if records and records[0]['content'] != ip4:
            logger.info('EDITING RECORD:: IP address has changed, editing...')
            client.edit_record(records[0]['id'], content=ip4)
        else:
            logger.info('IP address checked, unchanged')

        # if record doesn't exit
        if not records:
            client.create_record(type_="A", name=subdomain, content=ip4, note=full_ddns_id)

    logger.info("NOW SEARCHING FOR SUBDOMAINS TO REMOVE")
    all_a_records = client.get_records(type_="A", note=full_ddns_id)
    removed = 0
    for r in all_a_records:
        if r['note'] == full_ddns_id:
            if r['name'] not in subdomains:
                client.delete_record(r['id'])
                removed += 1
    logger.info(f"Removed {removed} record(s)")

