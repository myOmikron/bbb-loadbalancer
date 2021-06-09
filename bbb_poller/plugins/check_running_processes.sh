#!/bin/bash

SSH_SERVER=$1
SSH_USER=$2
PROCESS=$3

if ssh $SSH_USER@$SSH_SERVER "pgrep -fl '$PROCESS'" > /dev/null; then
  echo "$PROCESS is running"
  exit 0
fi

echo "$PROCESS is not running"
exit 1