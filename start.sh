#!/bin/bash

pkill -f "python parse.py"
pkill gunicorn

cd "$(dirname "$(readlink -f "$0")")"
source venv/bin/activate

parse_cmd="python parse.py"
eval "${parse_cmd}" &>/dev/null & disown;

authbind gunicorn
