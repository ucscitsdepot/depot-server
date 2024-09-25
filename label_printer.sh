#!/bin/bash

tmux send-keys -t label_printer_ui C-c
tmux kill-session -t label_printer
tmux kill-session -t label_printer_ui

tmux new -ds label_printer
tmux send-keys -t label_printer 'cd /home/depot/Auto-Label-Generator' Enter
tmux send-keys -t label_printer 'source venv/bin/activate' Enter
tmux send-keys -t label_printer 'python parse.py' Enter

tmux new -ds label_printer_ui
tmux send-keys -t label_printer_ui 'cd /home/depot/Auto-Label-Generator' Enter
tmux send-keys -t label_printer_ui 'source venv/bin/activate' Enter
tmux send-keys -t label_printer_ui 'authbind gunicorn' Enter
