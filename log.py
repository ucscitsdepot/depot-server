import datetime
import logging
import os

CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

loggers = {}
file_handlers = {}


def get_log_path(name: str):
    # Change directory to repository root
    logs_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    )

    timestamp = datetime.datetime.now()
    folder = timestamp.strftime("%Y-%m-%d")
    filename = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # Create a new directory for date if it doesn't exist
    if not os.path.exists(os.path.join(logs_path, name, folder)):
        os.makedirs(os.path.join(logs_path, name, folder))

    # check for and remove existing latest symlink
    if os.path.islink(os.path.join(logs_path, name, "latest.log")) or os.path.exists(
        os.path.join(logs_path, name, "latest.log")
    ):
        os.remove(os.path.join(logs_path, name, "latest.log"))

    # Create a new symlink to the latest log file
    os.symlink(
        os.path.join(logs_path, name, folder, filename + ".log"),
        os.path.join(logs_path, name, "latest.log"),
    )
    return os.path.join(logs_path, name, folder, filename + ".log")


def setup_logs(
    name: str,
    level: int = INFO,
    additional_handlers: list[tuple[str, int]] = [],
):
    if name in loggers:
        return loggers[name]

    # Change directory to repository root
    logs_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    )

    timestamp = datetime.datetime.now()
    folder = timestamp.strftime("%Y-%m-%d")
    filename = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # create new logger with all levels
    logger = logging.getLogger(name)
    logger.setLevel(DEBUG)

    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s: %(message)s")

    # create list of handlers
    handlers = []

    additional_handlers.append((name, level))

    for h_name, h_level in additional_handlers:
        if h_name in file_handlers:
            handlers.append(file_handlers[h_name])
        else:
            # Create a new directory for file handler if it doesn't exist
            if not os.path.exists(os.path.join(logs_path, h_name, folder)):
                os.makedirs(os.path.join(logs_path, h_name, folder))

            fh = logging.FileHandler(
                os.path.join(logs_path, h_name, folder, filename + ".log")
            )
            # set the level of the file handler (info by default) and the formatter
            fh.setLevel(h_level)
            fh.setFormatter(formatter)
            # add the file handler to the list of handlers for this logger
            handlers.append(fh)
            # add the file handler to the list of additional handlers
            file_handlers[h_name] = fh

            # check for and remove existing latest symlink
            if os.path.islink(
                os.path.join(logs_path, h_name, "latest.log")
            ) or os.path.exists(os.path.join(logs_path, h_name, "latest.log")):
                os.remove(os.path.join(logs_path, h_name, "latest.log"))

            # Create a new symlink to the latest log file
            os.symlink(
                os.path.join(logs_path, h_name, folder, filename + ".log"),
                os.path.join(logs_path, h_name, "latest.log"),
            )

    # create console handler which only logs warnings (and above)
    ch = logging.StreamHandler()
    # set the level of the console handler (warnings and above) and the formatter
    ch.setLevel(WARNING)
    ch.setFormatter(formatter)
    # add the console handler to the list of handlers
    handlers.append(ch)

    for handler in handlers:
        # add the handlers to the logger
        logger.addHandler(handler)

    loggers[name] = logger

    return logger
