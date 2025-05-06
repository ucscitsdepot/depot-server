#!/bin/bash

parse_cmd="python parse.py"

# kill the previous parse.py process
pkill -f "${parse_cmd}"

# cd into the project directory & activate the virtual environment
cd "$(dirname "$(readlink -f "$0")")"
source venv/bin/activate

# start the parse.py script in the background
eval "${parse_cmd}" &>/dev/null &

# disown the process to prevent it from being killed when the terminal is closed
disown

# restart the depot-server service (the gunicorn server)
systemctl restart depot-server
