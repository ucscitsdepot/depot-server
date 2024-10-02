import logging
import os
from datetime import datetime


def setup_logs(name="root", path=str(os.path.abspath(__file__)), path_only=False):
    # get date & datetime strings
    now = datetime.now()
    path += f"/logs/{name}/{now.strftime("%Y-%m-%d")}"

    # Create a new directory for logs if it doesn't exist
    if not os.path.exists(path):
        os.makedirs(path)

    path += f"/{now.strftime("%Y-%m-%d %H:%M:%S")}.log"

    if path_only:
        return path
    
    # create new logger with all levels
    logger = logging.getLogger("root")
    logger.setLevel(logging.DEBUG)

    # create file handler which logs debug messages (and above - everything)
    fh = logging.FileHandler(path)
    fh.setLevel(logging.DEBUG)

    # create console handler which only logs warnings (and above)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    # create formatter and add it to the handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s: %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
