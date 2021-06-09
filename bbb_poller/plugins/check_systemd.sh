#!/bin/bash

SSH_SERVER=$1
SSH_USER=$2
SYSTEMD=$3

if ssh $SSH_USER@$SSH_SERVER "systemctl status '$SYSTEMD'" > /dev/null; then
  echo "$SYSTEMD is running"
  exit 0
fi

echo "$SYSTEMD is not running"
exit 1