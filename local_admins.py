import re
import sqlite3
import time
import traceback
from threading import Thread


def get_sqlite3_thread_safety():

    # Map value from SQLite's THREADSAFE to Python's DBAPI 2.0
    # threadsafety attribute.
    sqlite_threadsafe2python_dbapi = {0: 0, 2: 1, 1: 3}
    conn = sqlite3.connect(":memory:")
    threadsafety = conn.execute(
        """
select * from pragma_compile_options
where compile_options like 'THREADSAFE=%'
"""
    ).fetchone()[0]
    conn.close()

    threadsafety_value = int(threadsafety.split("=")[1])

    return sqlite_threadsafe2python_dbapi[threadsafety_value]


if sqlite3.threadsafety == 3 or get_sqlite3_thread_safety() == 3:
    check_same_thread = False
else:
    check_same_thread = True

db = sqlite3.connect(
    "local_admins.db", autocommit=True, check_same_thread=check_same_thread
)
cursor = db.cursor()
sql = cursor.execute

sql(
    f"CREATE TABLE IF NOT EXISTS local_admins (timestamp INTEGER, ritm TEXT, serial TEXT, serial_orig TEXT, name TEXT, username TEXT)"
)


def log(ritm, serial, name, username):

    s = ""

    try:
        serial_list = serial.split(" ")

        unlikely = []
        likely = []

        for i in serial_list:
            if i != "" and i.isalnum() and (len(i) == 7 or 10 <= len(i) <= 12):
                if not bool(re.search(r"\d", i)):
                    unlikely.append(i)
                else:
                    likely.append(i)

        if len(likely) > 0:
            s = likely[-1]
        elif len(unlikely) > 0:
            s = unlikely[-1]
    except Exception:
        print(f"Error parsing serial: {traceback.format_exc()}")

    sql(
        "INSERT INTO local_admins (timestamp, ritm, serial, serial_orig, name, username) VALUES (?, ?, ?, ?, ?, ?)",
        (int(time.time()), ritm, s, serial, name, username),
    )


def log_thread(ritm, serial, name, username):
    t = Thread(target=log, args=[ritm, serial, name, username])
    t.start()


def lookup_local_admin(serial):
    row = sql(
        "SELECT name, username FROM local_admins WHERE serial = ? ORDER BY ROWID DESC",
        (serial,),
    ).fetchone()
    if row:
        return row
    else:
        return ["null"]


if __name__ == "__main__":
    # log("0012345", "ASDF123", "Admin Ishan Madan", "admin.imadan1")
    # log("0012346", "ASDF124", "Admin Ishan Madan 1", "admin.imadan2")
    # log("0012347", "ASDF125", "Admin Ishan Madan 2", "admin.imadan3")
    # log("0012348", "ASDF123", "Admin Ishan Madan 3", "admin.imadan4")
    print(lookup_local_admin("ASDF123"))
