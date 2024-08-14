#!/bin/bash

tmux kill-session -t label_printer
tmux kill-session -t label_printer_ui

tmux new -ds label_printer
tmux send-keys -t label_printer 'python3 /home/depot/Auto-Label-Generator/parse.py' Enter
tmux new -ds label_printer_ui
# tmux send-keys -t label_printer_ui 'python3 /home/depot/Auto-Label-Generator/app.py' Enter
tmux send-keys -t label_printer_ui 'cd /home/depot/Auto-Label-Generator' Enter
tmux send-keys -t label_printer_ui 'authbind gunicorn' Enter
