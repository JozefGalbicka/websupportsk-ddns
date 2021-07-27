#!/bin/bash
# change dir to project path
DIR="$(dirname "$0")"
cd $DIR

# create and activate virtualenv
python3 -m venv venv
source ./venv/bin/activate

# install dependencies
pip3 install requests

# start script
python3 websupportsk_ddns/websupportsk_ddns.py