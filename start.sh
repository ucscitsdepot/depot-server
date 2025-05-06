#!/bin/bash

parse_cmd="python parse.py"

pkill -f "${parse_cmd}"

cd "$(dirname "$(readlink -f "$0")")"
source venv/bin/activate

eval "${parse_cmd}" &>/dev/null &
disown
