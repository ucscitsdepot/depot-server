#!/bin/bash

tmux new -ds label_printer
tmux send-keys -t label_printer 'python3 /home/depot/Auto-Label-Generator/parse.py' Enter
tmux new -ds label_printer_ui
tmux send-keys -t label_printer_ui 'python3 /home/depot/Auto-Label-Generator/app.py' Enter
