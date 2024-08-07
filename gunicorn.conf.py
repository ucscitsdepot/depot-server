# Gunicorn configuration file
# https://docs.gunicorn.org/en/stable/configure.html#configuration-file
# https://docs.gunicorn.org/en/stable/settings.html
import multiprocessing
import os
from datetime import datetime, timedelta

max_requests = 1000
max_requests_jitter = 50

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# get date & datetime strings
now = datetime.now()
dt = now.strftime("%Y-%m-%d")
dttm = now.strftime("%Y-%m-%d %H:%M:%S")

# Create a new directory for logs if it doesn't exist
if not os.path.exists(path + "/logs/ui/" + dt):
    os.makedirs(path + "/logs/ui/" + dt)

# Set log path using timestamp
log_path = f"{dt}/{dttm}.log"

errorlog = path + "/logs/ui/" + log_path
accesslog = path + "/logs/ui/" + log_path

# don't use syslog
syslog = False

# set log level to debug - include all logs
loglevel = "debug"

# send any output to logs
capture_output = True

# set number of worker threads
workers = multiprocessing.cpu_count() * 2 + 1

# define Flask app path
wsgi_app = "app:app"

# 0.0.0.0 makes site available externally, and bind to port 80 (default http port)
bind = "0.0.0.0:80"
