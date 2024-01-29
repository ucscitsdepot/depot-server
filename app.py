import os
from datetime import datetime
from threading import Thread

from flask import Flask, flash, render_template, request

from write_pngs import *

os.chdir(os.path.dirname(os.path.realpath(__file__)))

# initialize flask app
app = Flask(__name__)
app.secret_key = os.urandom(12).hex()


# define this function to be the root page, accepts both GET requests (loading the page) and POST requests (submitted a form)
@app.route("/", methods=("GET", "POST"))
def server():
    print('help')
    # try/except in case something fails
    try:
        # if a form was submitted
        if request.method == "POST":
            print('post')
            # if the form response includes a RITM, capture it as a properly-formatted string
            ritm_text = (
                "0000000"
                if ("ritm" not in request.form or request.form["ritm"] == "")
                else str("%07d" % int(request.form["ritm"]))
            )
            # get the current date
            date = datetime.now().strftime("%m/%d/%Y")
            # if the ad label was submitted
            if request.form["label"] == "ad":
                # print the ad label in a thread (prevent the website from hanging while it prints)
                print_thread(file="static/ad.png")
            # if the depot label was submitted
            elif request.form["label"] == "depot":
                # print the depot label in a thread
                print_thread(file="static/depot.png")
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
                    True
                    if request.form["jamf"] == "Complete"
                    else (
                        False if request.form["jamf"] == "Incomplete" else None
                    ),  # if Complete, set to True; if Incomplete, set to False; otherwise (Unnecessary), set to None
                )
                # print the ewaste label in a thread
                print_thread()
            elif request.form["label"] == "macsetup":
                macsetup(
                    ritm_text,
                    str(request.form["macname"]),
                    str(request.form["serial"]),
                    str(request.form["client_name"]),
                    "backup" in request.form,
                    str(request.form["printers"]),
                    "admin" in request.form,
                )
                print_thread()
            elif request.form["label"] == "notes_printer":
                notes_printer(
                    ritm_text,
                    str(request.form["printerip"]),
                    str(request.form["printermodel"]),
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_thread()
            elif request.form["label"] == "notes":
                notes(
                    ritm_text,
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_thread()
            elif request.form["label"] == "ritm":
                ritm(
                    ritm_text,
                    str(request.form["client_name"]),
                    str(request.form["requestor_name"]),
                    date,
                    True
                    if request.form["migration"] == "Complete"
                    else (
                        False if (request.form["migration"] == "Incomplete") else None
                    ),
                    f"{str(request.form['index_1'])} of {str(request.form['index_2'])}",
                    str(request.form["returnloc"]),
                )
                print_thread()
            elif request.form["label"] == "tmpwd":
                print_thread(file="static/tmpwd.png")
            elif request.form["label"] == "username":
                username(str(request.form["username"]))
                print_thread()
            elif request.form["label"] == "winsetup":
                winsetup(
                    ritm_text,
                    str(request.form["pcname"]),
                    str(request.form["servicetag"]),
                    str(request.form["domain"]),
                    str(request.form["client_name"]),
                    "backup" in request.form,
                    str(request.form["printers"]),
                )
                print_thread()
            elif request.form["label"] == "ritm_generic":
                ritm_generic(
                    ritm_text,
                    str(request.form["notes"]),
                )
                print_thread()
            elif request.form["label"] == "inc_generic":
                inc_generic(
                    ritm_text,
                    str(request.form["notes"]),
                )
                print_thread()
            flash(f"Printed { request.form['label'] }")
    except Exception as e:
        print(e)
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
