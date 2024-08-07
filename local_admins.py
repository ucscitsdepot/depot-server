import fcntl
from threading import Thread
import time

import numpy as np

ARG_COUNT = 5  # date, ritm, serial, name, username

local_admins = None
active_write_path = "/tmp/active_write_local_admins"


def check_file():
    f = open(active_write_path, "a+")
    if f.writable():
        fcntl.flock(f, fcntl.LOCK_EX)
        return f

    return False


def close_file(f):
    fcntl.flock(f, fcntl.LOCK_UN)
    f.close()


THIRTY_DAYS = 60 * 60 * 24 * 30  # in seconds


def log(ritm, serial, name, username):
    global local_admins

    cf = check_file()

    while not cf:
        time.sleep(0.1)
        cf = check_file()

    f = open("local_admins.csv", "r")
    lines = f.read().splitlines(True)
    f.close()
    for i, line in enumerate(lines):
        if time.time() - int(line.split(",")[0]) <= THIRTY_DAYS:
            with open("local_admins.csv", "w") as f:
                f.writelines(lines[i:])
            break

    get_local_admins()

    f = open("local_admins.csv", "a+")
    row = [str(int(time.time())), ritm, serial, name, username]
    local_admins = np.vstack([local_admins, row])
    for r in row[:-1]:
        f.write(r + ",")
    f.write(row[-1] + "\n")
    f.close()

    close_file(cf)


def log_thread(ritm, serial, name, username):
    t = Thread(target=log, args=[ritm, serial, name, username])
    t.start()


def lookup_local_admin(serial):
    get_local_admins()
    for line in reversed(local_admins):
        if str(line[2]).lower() == str(serial).lower():
            return [str(line[3]), str(line[4])]
    return ["null"]


def get_local_admins():
    global local_admins
    try:
        local_admins = np.genfromtxt("local_admins.csv", dtype=str, delimiter=",")
        if len(local_admins) < 1:
            raise Exception
    except Exception as e:
        local_admins = np.array([[""] * (ARG_COUNT)])


if __name__ == "__main__":
    get_local_admins()
    print("b", local_admins, len(local_admins))
    print()

    # log(
    #     "ewaste",
    #     "0098765",
    #     "7/17/2024",
    #     "ASDF123",
    #     "3-Pass",
    #     "Surplus",
    #     True,
    # )

    log("0012345", "ASDF123", "Admin Ishan Madan", "admin.imadan1")
    # print("c", local_admins, len(local_admins))
    log("0012346", "ASDF124", "Admin Ishan Madan 1", "admin.imadan2")
    # print("d", local_admins, len(local_admins))
    log("0012347", "ASDF125", "Admin Ishan Madan 2", "admin.imadan3")

    print("e", local_admins, len(local_admins))
    print()

    print("f", lookup_local_admin("ASDF125"))

    # reprint(1)
