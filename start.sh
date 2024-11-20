#!/bin/bash

pkill python
pkill gunicorn

cd /home/depot/depot-server
source venv/bin/activate

parse_cmd="python parse.py"
eval "${parse_cmd}" &>/dev/null & disown;

authbind gunicorn