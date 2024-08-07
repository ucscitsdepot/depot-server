import logging
import os
import re
import shutil
from datetime import datetime

import mammoth
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from html2image import Html2Image

from history import get_history, reprint
from local_admins import lookup_local_admin
from print import *
from write_pngs import *

# note: using authbind & gunicorn to host on port 80:
# https://stackoverflow.com/questions/16225872/getting-gunicorn-to-run-on-port-80
# https://adamj.eu/tech/2021/12/29/set-up-a-gunicorn-configuration-file-and-test-it/
# to start, just run 'authbind gunicorn'

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

# init paramaters
hti = Html2Image(custom_flags=["--no-sandbox"], size=(800, 1000))
rtf_path = "ITS-Shipping-Form.rtf"
docx_path = "ITS-Shipping-Form.docx"
new_docx_path = "ITS-Shipping-Form-Copy.docx"
shutil.copy(docx_path, new_docx_path)
printer_name = "printername"
cmd = "lp -o fill blue_page.png"

# initialize flask app
app = Flask(__name__)
app.secret_key = os.urandom(12).hex()

logger = logging.getLogger("gunicorn.error")


# define this function to be the root page, accepts both GET requests (loading the page) and POST requests (submitted a form)
@app.route("/", methods=("GET", "POST"))
def server():
    # print("help")
    # try/except in case something fails
    h = None
    selected_type = None
    data = []
    try:
        # if a form was submitted
        if request.method == "POST":
            # print("post")
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
                print_thread(logger, file="static/ad.png")
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
            flash(f"Reload to repeat {request.form['label']}")

        h = get_history(23)
    except Exception as e:
        logger.error(e)
    return render_template(
        "index.html",
        history=reversed(h),
        history_count=-1 * len(h),
        selected_type=selected_type,
        data=data,
    )


@app.route("/<ritm_num>")
@app.route("/<ritm_num>/")
def ritm_link(ritm_num):
    try:
        ritm_text = str("RITM%07d" % int(re.sub("[^\d\.]", "", ritm_num)))
        return redirect(
            "https://ucsc.service-now.com/sc_req_item.do?sysparm_query=number="
            + ritm_text
        )
    except Exception as e:
        # print("error:")
        logger.error(e)
        return redirect(url_for("server"))


@app.route("/admin/<serial>")
def local_admin(serial):
    return jsonify(lookup_local_admin(serial))


@app.route("/ship")
def index():
    return render_template("ship.html")


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"]
    date = request.form["date"]
    phone = request.form["phone"]
    address1 = request.form["address1"]
    address2 = request.form["address2"]
    city = request.form["city"]
    state = request.form["state"]
    zip_code = request.form["zip"]
    mailcode = request.form["mailcode"]
    tracking_email = request.form["tracking_email"]
    approver = request.form["approver"]
    ritm = request.form["ritm"]
    inc = request.form["inc"]

    replace_string_in_docx(
        new_docx_path,
        "Name ____________________________",
        "Name: %s" % adjust_string_length(name, 29),
    )
    replace_string_in_docx(
        new_docx_path, "Date _____________", "Date: %s" % adjust_string_length(date, 10)
    )
    replace_string_in_docx(
        new_docx_path,
        "Phone _____________________",
        "Phone: %s" % adjust_string_length(phone, 5),
    )
    replace_string_in_docx(
        new_docx_path,
        "Address Line 1 __________________________________________________________________",
        "Address1: %s" % adjust_string_length(address1, 5),
    )
    replace_string_in_docx(
        new_docx_path,
        "Address Line 2 __________________________________________________________________",
        "Address2: %s" % adjust_string_length(address2, 5),
    )
    replace_string_in_docx(
        new_docx_path,
        "City ____________________",
        "City: %s" % adjust_string_length(city, 7),
    )
    replace_string_in_docx(
        new_docx_path, "State _________", "State: %s" % adjust_string_length(state, 2)
    )
    replace_string_in_docx(
        new_docx_path,
        "ZIP _____________",
        "Zip: %s" % adjust_string_length(zip_code, 5),
    )
    replace_string_in_docx(
        new_docx_path,
        "MailCode ________",
        "Mailcode: %s" % adjust_string_length(mailcode, 2),
    )
    replace_string_in_docx(
        new_docx_path,
        "depot@ucsc.edu | __________________________________",
        "depot@ucsc.edu | %s" % adjust_string_length(tracking_email, 14),
    )
    replace_string_in_docx(
        new_docx_path,
        "MailCode Approver _____________________________",
        "MailCode Approver: %s" % adjust_string_length(approver, 8),
    )
    replace_string_in_docx(
        new_docx_path, "RITM00_____________", "%s" % adjust_string_length(ritm, 5)
    )
    replace_string_in_docx(
        new_docx_path, "INC0_____________", "%s" % adjust_string_length(inc, 5)
    )

    custom_styles = "b => i"
    with open(new_docx_path, "rb") as docx_file:

        result = mammoth.convert_to_html(docx_file, style_map=custom_styles)
        text = result.value
        with open("output.html", "w") as html_file:
            html_file.write(text)

    hti.screenshot(html_file="output.html", save_as="blue_page.png")

    os.system(cmd)

    return "Form submitted successfully"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
