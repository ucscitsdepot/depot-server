#!/bin/bash

cd /home/depot/Auto-Label-Generator
source venv/bin/activate

parse_cmd="python parse.py"
eval "${parse_cmd}" &>/dev/null & disown;

ui_cmd="authbind gunicorn"
eval "${ui_cmd}" &>/dev/null & disown;