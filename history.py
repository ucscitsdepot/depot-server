import sqlite3
import time
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
    "print_history.db", autocommit=True, check_same_thread=check_same_thread
)
cursor = db.cursor()
sql = cursor.execute

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
    "kiosk": 1,
}

MAX_ARGS = max(ARG_COUNT.values())

ARG_TEXT = ", ".join([f"data{i} TEXT" for i in range(MAX_ARGS)])

sql(f"CREATE TABLE IF NOT EXISTS history (timestamp INTEGER, type TEXT, {ARG_TEXT})")

# label types to not append "RITM" to
NON_RITM_TYPES = ["username", "inc_generic", "kiosk"]


def log(label_type, *args):
    arg_text = ", ".join([f"data{i}" for i in range(len(args))])
    q_marks = ", ".join(["?"] * (len(args) + 2))
    sql(
        f"INSERT INTO history (timestamp, type, {arg_text}) VALUES ({q_marks})",
        (int(time.time()), label_type) + tuple([str(a) for a in args]),
    )


def log_thread(label_type, *args):
    t = Thread(target=log, args=[label_type] + list(args))
    t.start()


def reprint(row_num):
    row = sql("SELECT * FROM history WHERE ROWID = ?", (row_num,)).fetchone()
    return (row[1], row[2:])


def get_history(count):
    print_history = sql(
        "SELECT ROWID, timestamp, type, data0 FROM history ORDER BY ROWID DESC LIMIT ?",
        (count,),
    ).fetchall()

    return [
        (
            print_history[i][0],
            time.strftime("%b %d %I:%M %p", time.localtime(int(print_history[i][1]))),
            print_history[i][2],
            print_history[i][3],
            print_history[i][2] not in NON_RITM_TYPES,
        )
        for i in range(len(print_history))
    ]


if __name__ == "__main__":
    h = get_history(10)
    print(h, len(h))
    # print()

    # log(
    #     "ewaste",
    #     "0098765",
    #     "7/17/2024",
    #     "ASDF123",
    #     "3-Pass",
    #     "Surplus",
    #     True,
    # )

    # h = get_history(10)
    # print(h, len(h))
    # print()

    # with open("print_history.csv") as f:
    #     for line in f.readlines():
    #         line = line.strip().strip('\n').split(',')
    #         line[0] = int(line[0])
    #         log(line[1], line[0], *line[2:])

    print(reprint(1))
