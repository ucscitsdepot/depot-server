import fcntl
from threading import Thread
import time

import numpy as np

MAX_ARGS = 7

ARG_COUNT = {
    "ewaste": 6,
    "ritm": 6,
    "macsetup": 7,
    "notes_printer": 5,
    "notes": 3,
    "username": 1,
    "winsetup": 7,
    "ritm_generic": 2,
    "inc_generic": 2,
}

# label types to not append "RITM" to
NON_RITM_TYPES = ["username", "inc_generic"]

print_history = None
try:
    print_history = np.genfromtxt("print_history.csv", dtype=str, delimiter=",")
    if len(print_history) < 1:
        raise Exception
except:
    print_history = np.array([[""] * (2 + MAX_ARGS)])

active_write_path = "/tmp/active_write_history"


def check_file():
    f = open(active_write_path, "a+")
    if f.writable():
        fcntl.flock(f, fcntl.LOCK_EX)
        return f

    return False


def close_file(f):
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()


def log(label_type, *args):
    global print_history

    cf = check_file()

    while not cf:
        time.sleep(0.1)
        cf = check_file()

    get_history()

    f = open("print_history.csv", "a+")
    row = (
        [str(int(time.time())), label_type]
        + [str(a) for a in args]
        + [""] * (MAX_ARGS - len(args))
    )
    print_history = np.vstack([print_history, row])
    for r in row[:-1]:
        f.write(r + ",")
    f.write(row[-1] + "\n")
    f.close()

    close_file(cf)


def log_thread(label_type, *args):
    t = Thread(target=log, args=[label_type] + list(args))
    t.start()


def reprint(row_num):
    get_history()
    row = print_history[row_num]
    return (row[1], row[2:])


def get_history(count=None):
    global print_history
    try:
        print_history = np.genfromtxt("print_history.csv", dtype=str, delimiter=",")
        if len(print_history) < 1:
            raise Exception
        elif len(print_history) > 1 and print_history[0][0] == "":
            print_history = print_history[1:]
    except:
        print_history = np.array([[""] * (2 + MAX_ARGS)])

    if count:
        if len(print_history) == 1 and print_history[0][0] == "":
            return []

        if count >= len(print_history):
            count = len(print_history)
            if print_history[0][0] == "":
                count -= 1

        return [
            (
                i,
                time.strftime(
                    "%b %d %I:%M %p", time.localtime(int(print_history[i][0]))
                ),
                print_history[i][1],
                print_history[i][2],
                print_history[i][1] not in NON_RITM_TYPES,
            )
            for i in range((len(print_history) - count), len(print_history))
        ]


if __name__ == "__main__":
    print(print_history, len(print_history))
    print()

    log(
        "ewaste",
        "0098765",
        "7/17/2024",
        "ASDF123",
        "3-Pass",
        "Surplus",
        True,
    )

    print(print_history, len(print_history))
    print()

    # reprint(1)
