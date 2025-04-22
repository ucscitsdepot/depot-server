import logging
import os
import re
from datetime import datetime
import schedule

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

import cal
from history import get_history, reprint
from local_admins import lookup_local_admin
from write_pngs import *

# note: using authbind & gunicorn to host on port 80:
# https://stackoverflow.com/questions/16225872/getting-gunicorn-to-run-on-port-80
# https://adamj.eu/tech/2021/12/29/set-up-a-gunicorn-configuration-file-and-test-it/
# to start, just run 'authbind gunicorn'

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# initialize flask app
app = Flask(__name__)
app.secret_key = os.urandom(12).hex()
app.url_map.strict_slashes = True

logger = logging.getLogger("gunicorn.error")


# define this function to be the root page, accepts both GET requests (loading the page) and POST requests (submitted a form)
@app.route("/", methods=("GET", "POST"))
def server():
    # try/except in case something fails
    h = None
    selected_type = None
    data = []
    try:
        # if a form was submitted
        if request.method == "POST":
            # if the form response includes a RITM, capture it as a properly-formatted string
            ritm_text = (
                "0000000"
                if ("ritm" not in request.form or request.form["ritm"] == "")
                else str("%07d" % int(request.form["ritm"]))
            )
            # get the current date
            date = datetime.now().strftime("%m/%d/%Y")
            # if the au label was submitted
            if request.form["label"] == "au":
                # print the au label in a thread (prevent the website from hanging while it prints)
                print_thread(logger, file="static/au.png")
            # if the depot label was submitted
            elif request.form["label"] == "depot":
                # print the depot label in a thread
                print_thread(logger, file="static/depot.png")
            # if the ewaste label was submitted
            elif request.form["label"] == "ewaste":
                # get the form data
                ewaste(
                    ritm_text,
                    date,
                    str(request.form["serial"]),  # serial/service tag
                    str(
                        request.form["erase_type"]
                    ),  # erase type (3 Pass, Crypto, Destroy, None)
                    str(
                        "Surplus" if "export" in request.form else "Ewaste"
                    ),  # if "Surplus?" box was checked, Surplus, if unchecked it will not show up in the request.form dict --> Ewaste
                    (
                        True
                        if request.form["jamf"] == "Complete"
                        else (False if request.form["jamf"] == "Incomplete" else None)
                    ),  # if Complete, set to True; if Incomplete, set to False; otherwise (Unnecessary), set to None
                )
                # print the ewaste label in a thread
                print_thread(logger)
            elif request.form["label"] == "kiosk":
                # get the form data
                kiosk(
                    str(request.form["serial"]), date, str(request.form["destination"])
                )
                # print the kiosk label in a thread
                print_thread(logger)
            elif request.form["label"] == "macsetup":
                macsetup(
                    ritm_text,
                    str(request.form["dept"]),
                    str(request.form["serial"]),
                    str(request.form["client_name"]),
                    "backup" in request.form,
                    str(request.form["printers"]),
                    "admin" in request.form,
                )
                print_thread(logger)
            elif request.form["label"] == "notes_printer":
                notes_printer(
                    ritm_text,
                    str(request.form["printerip"]),
                    str(request.form["printermodel"]),
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_thread(logger)
            elif request.form["label"] == "notes":
                notes(
                    ritm_text,
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_thread(logger)
            elif request.form["label"] == "ritm":
                ritm(
                    ritm_text,
                    str(request.form["client_name"]),
                    str(request.form["requestor_name"]),
                    date,
                    (
                        True
                        if request.form["migration"] == "Complete"
                        else (
                            False
                            if (request.form["migration"] == "Incomplete")
                            else None
                        )
                    ),
                    f"{str(request.form['index_1'])} of {str(request.form['index_2'])}",
                )
                print_thread(logger)
            elif request.form["label"] == "tmpwd":
                print_thread(logger, file="static/tmpwd.png")
            elif request.form["label"] == "username":
                username(str(request.form["username"]))
                print_thread(logger)
            elif request.form["label"] == "winsetup":
                winsetup(
                    ritm_text,
                    str(request.form["dept"]),
                    str(request.form["servicetag"]),
                    str(request.form["domain"]),
                    str(request.form["client_name"]),
                    "backup" in request.form,
                    str(request.form["printers"]),
                )
                print_thread(logger)
            elif request.form["label"] == "ritm_generic":
                ritm_generic(
                    ritm_text,
                    str(request.form["notes"]),
                )
                print_thread(logger)
            elif request.form["label"] == "inc_generic":
                inc_generic(
                    ritm_text,
                    str(request.form["notes"]),
                )
                print_thread(logger)
            elif request.form["label"] == "history":
                row_num = int(request.form["row_num"])
                selected_type, data = reprint(row_num)
            elif request.form["label"] == "refurbished":
                refurbished(
                    str(request.form["name"]),
                    str(request.form["cpu"]),
                    0 if request.form["ram"] == "" else int(request.form["ram"]),
                    (
                        0
                        if request.form["storage"] == ""
                        else int(request.form["storage"])
                    ),
                    str(request.form["storage_type"]),
                    str(request.form["os"]),
                    str(request.form["notes"]),
                )
                print_thread(logger)

            if request.form["label"] != "history":
                flash(f"Reload to repeat {request.form['label']}")

        h = get_history(23)
    except Exception as e:
        logger.error(f"app.server: {e}")

    return render_template(
        "index.html",
        history=[] if not h else h,
        last_row_num=0 if not h else h[-1][0],
        selected_type=selected_type,
        data=data,
    )


@app.route("/kiosk/")
def print_kiosk():
    serial = request.args.get("serial")
    destination = request.args.get("destination")

    if not serial:
        serial = ""

    if not destination:
        destination = ""

    # create kiosk label w/ serial & date
    kiosk(serial.upper(), datetime.now().strftime("%m/%d/%Y"), destination)
    # print the kiosk label in a thread
    print_thread(logger)
    return f"Printed kiosk label for {serial} going to {destination}"


@app.route("/<ritm_num>/")
def ritm_link(ritm_num):
    try:
        if not ritm_num or not re.sub("[^0-9]", "", ritm_num).isnumeric():
            return redirect(url_for("server"))

        ritm_text = str("RITM%07d" % int(re.sub("[^0-9]", "", ritm_num)))
        return redirect(
            "https://ucsc.service-now.com/sc_req_item.do?sysparm_query=number="
            + ritm_text
        )
    except Exception as e:
        logger.error(f"app.ritm_link: {e}")
        return redirect(url_for("server"))


@app.route("/admin/<serial>/")
def local_admin(serial):
    return jsonify(lookup_local_admin(serial))


@app.route("/calendar/")
def calendar():
    days, events = cal.get_events()
    try:
        schedule.get_events()
    except:
        pass
    return render_template(
        "calendar.html", days=days, events=events, today="Today" in days
    )


@app.route("/ip-db/")
def ip_db():
    name = request.args.get("name")
    ip = request.args.get("ip")

    logger.info(f"app.ip_db: name = '{name}', ip = '{ip}'")

    db_path = os.path.dirname(os.path.abspath(__file__)) + "/ip_db"

    if not name or not ip:
        return "fail", 400

    if not os.path.exists(db_path):
        os.makedirs(db_path)

    with open(db_path + "/" + name, "w") as f:
        f.write(ip)

    return "success"


locker_files = {
    "anyconnect_linux": "cisco-secure-client-linux64-5.1.5.65-predeploy-k9.tar.gz",
    "linux_installer": "linux-test.sh",
    "slack_linux": "slack-desktop-4.39.95-amd64.deb",
    "secureconnect_setup": "cisco_setup.sh",
    "csc_prelogin": "prelogin.sh",
    "fireeyesh": "fireeye.sh",
    "fireeyepkg": "fireeye.tgz",
    "sentinalonesh": "sentinal-one.sh",
    "sentinalonepkg": "SentinelAgent_linux_x86_64_v24_3_1_29.deb",
    "ubuntu_autoinstall.yaml": "autoinstall.yaml",  # endpoint must end in .yaml for ubuntu to accept it
    "wififinal": "wififinal.sh",
    "aupair": "au-pair.sh",
}


@app.route("/lockers/<filename>/")
def locker(filename):
    if filename not in locker_files:
        return "file does not exist", 400
    return redirect(url_for("static", filename="lockers/" + locker_files[filename]))


@app.route("/docs/")
def docs():
    return redirect(
        "https://drive.google.com/drive/folders/1PTKgPiy2x6h6OWhg23mexzbbkpQi6XQw"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
