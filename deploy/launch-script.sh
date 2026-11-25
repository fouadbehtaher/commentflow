#!/bin/bash
# PRIVATE TEMPLATE, UNTESTED. Lightsail launch script (Ubuntu). Contains NO secrets and NO settings:
# launch-script text is stored with the instance, so nothing sensitive may go here.
set -eux
apt-get update && apt-get install -y docker.io docker-compose-v2 git curl python3
mkdir -p /opt/commentflow /etc/commentflow && chmod 700 /etc/commentflow
git clone https://github.com/fouadbehtaher/commentflow /opt/commentflow/src
# After boot, secrets and settings are entered once on the server: sudo /opt/commentflow/src/deploy/setup.sh
