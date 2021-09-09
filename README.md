# Websupport.sk DDNS
[Websupport.sk](https://websupport.sk) DDNS handler for networks with dynamic public IP.

This project automates the process of handling a dynamic IP address on your network by 
managing A records using the Websupport Remote API.

`websupportsk-ddns` handles most of the busy work with python script that fetches public
IPv4 address and then creates/updates DNS records for each specified subdomain through
Websupport Remote API.

Python 3.7+ is recommended.

## Installation
First copy the example configuration file into the real one.
```commandline
cp config-example.json config.json
```
Open `config.json` and specify your own credentials and settings.

```json
{
  "websupport": {
    "authentication": {
      "identifier": "api_identifier_here",
      "secret_key": "api_secret_key_here"
    },
    "registered_domain": "example.com",
    "subdomains": [
      "subdomain1",
      "subdomain2"
    ],
    "ddns_id": "01"
  },
  "pushover": {
    "api_token": "your_api_token",
    "user_key": "your_user_key"
  },
  "gotify": {
    "url": "gotify.example.com",
    "api_token": "your_api_token"
  }
}
```
### Some values explained
```
"registered_domain": "Domain that you want to manage",
"subdomains": "List of subdomains you want to associate with your public IP. '@' stands for domain
            without use of subdomain, '*' on the other hand works as wildcard subdomain. You can
            specify as much subdomains as you need"
"ddns_id"(optional): "ID of your network, you can specify any value that suits your needs
            - i.e. if you specify value '01', result value will be 'websupportsk-ddns-01'.
            This value is then inserted into 'note' field of your records created from within
            the network of script, so you know to which network every public IP address belongs.
            This is fundamental when you have same subdomain pointing to multiple public 
            IP addressess(networks). Basically all you have to do in that case is to setup
            this script inside all of these networks. First network can have ddns_id '01',
            second '02' and so on. Without this implementation could one network change 
            public address of another network and not its own. If you are using single
            network, there is no problem if you won't specify this value'"
"pushover"(optional): "If specified with credential values, script will push important
            notifications to your pushover app."
"gotify"(optional): "Same as pushover, you just need to self-host your own gotify server.
            `Both notifiers can be used alongside each other.`" 
```

## Deploy with cron 
1. Download/clone this repository and give permission to the bash script by running 
`chmod u+x ./run-sync`. Now you can execute `./run-sync`, which will set up virtualenv, pull needed dependencies
and start the script.
   
2. Run `crontab -e`
   
3. Create crontab job to sync DNS records every 5 minutes. Edit path and timing by your needs.
```bash
*/5 * * * * /home/your_username_here/websupportsk-ddns/run-sync
```

## Deploy with docker
Pre-compiled images are available via [official Docker Hub Container Image Library(missing link)]()

```yaml
version: "3.7"
services:
  websupportsk-ddns:
    image: crypsde/websupportsk-ddns:latest
    container_name: websupportsk-ddns
    init: true
    volumes:
      - /YOUR/PATH/HERE/config.json:/app/websupportsk_ddns/config.json
    restart: unless-stopped
```

### Running
    docker-compose up -d