import os
from datetime import datetime

from flask import Flask, flash, render_template, request
from write_pngs import *

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()


@app.route("/", methods=("GET", "POST"))
def server():
    try:
        if request.method == "POST":
            ritm_text = (
                "0000000"
                if ("ritm" not in request.form or request.form["ritm"] == "")
                else str("%07d" % int(request.form["ritm"]))
            )
            date = datetime.now().strftime("%m/%d/%Y")
            if request.form["label"] == "ad":
                print_label(file="png/ad.png")
            elif request.form["label"] == "depot":
                print_label(file="png/depot.png")
            elif request.form["label"] == "ewaste":
                ewaste(
                    ritm_text,
                    date,
                    str(request.form["serial"]),
                    str(request.form["erase_type"]),
                    str("Surplus" if "export" in request.form else "Ewaste"),
                    True
                    if request.form["jamf"] == "Complete"
                    else (False if request.form["jamf"] == "Incomplete" else None),
                )
                print_label()
            elif request.form["label"] == "macsetup":
                macsetup(
                    ritm_text,
                    str(request.form["macname"]),
                    str(request.form["serial"]),
                    str(request.form["client_name"]),
                    "backup" in request.form,
                    str(request.form["printers"]),
                    "admin" in request.form
                )
                print_label()
            elif request.form["label"] == "notes_printer":
                notes_printer(
                    ritm_text,
                    str(request.form["printerip"]),
                    str(request.form["printermodel"]),
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_label()
            elif request.form["label"] == "notes":
                notes(
                    ritm_text,
                    str(request.form["sw"]),
                    str(request.form["notes"]),
                )
                print_label()
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
                print_label()
            elif request.form["label"] == "tmpwd":
                print_label(file="png/tmpwd.png")
            elif request.form["label"] == "username":
                username(str(request.form["username"]))
                print_label()
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
                print_label()
            flash(f"Printed { request.form['label'] }")
    except Exception as e:
        print(e)
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
