# imports for WebsupportAPI class
import hmac
import hashlib
import time
import requests
from datetime import datetime, timezone
import json
import os
import logging.config

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isdir('logs'):
    print("test")
    os.mkdir('logs')

logging.config.fileConfig('logger.conf')
logger = logging.getLogger(__name__)


def get_public_ipv4():
    """Request public IP address from multiple API services

    Returns:
        str: Public IP address.
    """
    ip = None
    try:
        ip = requests.get("https://api.ipify.org").text
        logger.debug(f"ipify request succeeded, IP: {ip}")
    except requests.ConnectionError:
        logger.error("ipify request failed")
        try:
            ip = requests.get("https://checkip.amazonaws.com/").text
            logger.debug(f"aws checkip request succeeded, IP: {ip}")
        except requests.ConnectionError:
            logger.error("aws checkip request failed")
            logger.error("unable to obtain public ip address from external services, exiting...")
            exit(3)
    return ip


class WebsupportClient:
    """API client that handles connection with Websupport REST API"""

    def __init__(self, identifier, secret_key, domain):
        """Constructor for WebsupportClient.

        Args:
            identifier (string): Account API identifier
            secret_key (string): Account API secret key
            domain: (string): domain you want to manage, i.e. example.com
        """
        self.api = "https://rest.websupport.sk"
        self.default_path = "/v1/user/self"
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

        # testing login credentials
        login_response = self.s.get("%s%s%s" % (self.api, self.default_path, self.query)).json()
        if 'message' and 'code' in login_response:
            logger.error(f"Error occurred, response: {login_response}")
            logger.error("exiting...")
            exit(1)
        # testing domain access
        domain_response = self.s.get(f"{self.api}{self.default_path}/zone/{self.domain}").json()
        if 'message' and 'code' in domain_response:
            logger.error(f"Error occurred, response: {domain_response}")
            logger.error("exiting...")
            exit(2)

    def get_records(self, type_=None, id_=None, name=None, content=None, ttl=None, note=None):
        """Request list of records with values specified.

        Returns:
            List of records that match arguments specified above.
        """
        # create dict of arguments passed to method, filter out 'None' values
        # and 'self' argument, rename keys(remove "_" trailing)
        args = {k.replace("_", ""): v for k, v in locals().items() if v is not None and k != 'self'}

        # get data from api
        data = json.loads(self.s.get(f"{self.api}{self.default_path}/zone/{self.domain}/record{self.query}").content)
        records = data["items"]

        matched_records = list()
        for record in records:
            # keys to compare
            keys_to_compare = args.keys() & record.keys()
            # keys that have same value in record and arguments
            shared_elements = [k for k in keys_to_compare if record[k] == args[k]]
            # record is valid only if all values from args match
            matched_records.append(record) if len(shared_elements) == len(args) else None

        logger.debug(f"GETTING RECORDS:: arguments: {args},... found: {len(matched_records)} record(s)")
        return matched_records

    def create_record(self, type_, name, content, ttl=600, **kwargs):
        """Create record with arguments specified.

        Some types of records support additional arguments. In that case you can specify them as keyword argument.
        MX record for example requires parameter "prio", so you will have to specify it as well (i.e. prio=5).
        All parameters can be found inside REST API documentation.
        """

        args = {k.replace("_", ""): v for k, v in locals().items()}
        args.pop('self')
        args.pop('kwargs')
        args.update(**kwargs)

        log_response("CREATING RECORD", self.s.post(f"{self.api}{self.default_path}/zone/{self.domain}/record",
                                                    json=args).json())

    def edit_record(self, id_, **kwargs):
        """Edit record's keyword arguments specified, i.e. name="subdomain1"."""

        log_response("EDITING RECORD", self.s.put(f"{self.api}{self.default_path}/zone/{self.domain}/record/{id_}",
                                                  json=kwargs).json())

    def delete_record(self, id_):
        log_response("DELETING RECORD", self.s.delete(f"{self.api}{self.default_path}/zone/{self.domain}/record/{id_}")
                     .json())

    # return first record found
    # TO-DO: add error handling for not found record and multiple records found
    def get_record_id(self, type_, name, **kwargs):
        """Same functionality as get_records function, just return id of first record found.

        Returns:
            Id of the first record found.
        """
        record = self.get_records(type_=type_, name=name, **kwargs)
        return record[0]['id']


def log_response(action, record):
    """Format and log record response from REST API.

    Args:
        action (string): Name of action performed.
        record (dict): Dictionary containing all information about record.
    """

    record['item'].pop('zone')
    logger.info(f"{action}:: STATUS: {record['status']}, \tITEM: {record['item']}, \tERRORS: {record['errors']}")


def main():
    """Main function, check public IP address and change records with API client if address has changed."""

    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    client = WebsupportClient(config['websupport']['authentication']['identifier'],
                              config['websupport']['authentication']['secret_key'],
                              config['websupport']['registered_domain'])

    subdomains = config["websupport"]["subdomains"]
    ipv4 = get_public_ipv4()

    full_ddns_id = "websupportsk-ddns"
    # if custom ddns_id specified
    try:
        ddns_id = config['websupport']['ddns_id']
        if ddns_id:
            full_ddns_id += f"-{ddns_id}"
    except KeyError:
        pass

    change_occurred = False
    for subdomain in subdomains:
        change_occurred = False
        logger.debug(f"CHECKING SUBDOMAIN: {subdomain}")
        # if record for specific subdomain with correct ipv4 already exists but doesn't have correct note comment
        records = client.get_records(type_="A", name=subdomain, content=ipv4)
        if records and records[0]['note'] != full_ddns_id:
            logger.info(f"EDITING RECORD {subdomain}:: note is incorrect, editing... "
                        f"({records[0]['note']} -> {full_ddns_id})")
            client.edit_record(records[0]['id'], note=full_ddns_id)
            change_occurred = True
        elif records:
            logger.debug('Record note checked, valid')
        else:
            logger.debug('Record non-existent, possible that ipv4 changed, checking...')

        # if record exist bud ipv4 has changed(record must have correct note)
        records = client.get_records(type_="A", name=subdomain, note=full_ddns_id)
        if records and records[0]['content'] != ipv4:
            logger.info('EDITING RECORD:: IP address has changed, editing...')
            client.edit_record(records[0]['id'], content=ipv4)
            change_occurred = True
        elif records:
            logger.debug('IP address checked, unchanged')
        else:
            logger.debug('Record non-existent, will proceed to generation of new one...')

        # if record doesn't exit
        if not records:
            client.create_record(type_="A", name=subdomain, content=ipv4, note=full_ddns_id)
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
    main()
