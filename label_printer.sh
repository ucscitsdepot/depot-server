#!/bin/bash

tmux new -ds label_printer
tmux send-keys -t label_printer 'python3 /home/depot/Auto-Label-Generator/parse.py' Enter
