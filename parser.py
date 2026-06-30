import email
import imaplib
import logging
import os
import re
import time
import traceback
import unicodedata
from datetime import datetime
from html import unescape

from dotenv import load_dotenv

import log
from directory import lookup_cruzid
from local_admins import log_thread as log_admin

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

logger = log.setup_logs("parser", log.INFO)

if type(logger) != logging.Logger:
    print("parse: Incorrect logger setup")
    exit(1)

# import Ewaste/Label classes, all functions to output png files
from ewaste import Ewaste
from label import Label
from write_pngs import (
    ewaste,
    macsetup,
    notes,
    notes_printer,
    print_label,
    ritm,
    username,
    winsetup,
    resnet,
    resnet_name_ritm,
)

# load environment variables (gmail username, gmail password)
load_dotenv()


# remove non-unicode accents from text (names) so they can be properly processed and printed by python
def strip_accents(data):
    return unicodedata.normalize("NFD", data).encode("ascii", "ignore").decode("utf-8")


def html_to_text(body: str):
    body = body.replace("\r", "")
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</p>", "\n", body)
    body = re.sub(r"(?i)<[^>]+>", "", body)
    body = unescape(body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def parse_resnet_label(body: str):
    if (
        "Opened By:" not in body
        or "Client Name:" not in body
        or "Computer Model:" not in body
        or "Serial Number:" not in body
    ):
        return None

    text = html_to_text(body)
    ritm_match = re.search(r"RITM(\d+)", text)
    if not ritm_match:
        return None

    label = Label(ritm_match.group(1))
    label.setDepartment("Resnet Staff")

    opened_by = re.search(r"Opened By:\s*(.+)", text)
    client_name = re.search(r"Client Name:\s*(.+)", text)
    computer_model = re.search(r"Computer Model:\s*(.+)", text)
    serial_number = re.search(r"Serial Number:\s*(.+)", text)
    service_requested = re.search(r"Select list for service requested::\s*(.+)", text)
    description = re.search(r"Description:\s*(.+)", text)

    if opened_by:
        label.setRequestor(opened_by.group(1).strip())
    if client_name:
        client_value = client_name.group(1).strip()
        if "(" in client_value and ")" in client_value:
            label.setClient(client_value)
        else:
            label.client_name = client_value
    if computer_model:
        model = computer_model.group(1).strip()
        if "mac" in model.lower() or "apple" in model.lower():
            label.setType("Mac")
        else:
            label.setType("Windows")
    if serial_number:
        label.serial = [serial_number.group(1).strip()]

    notes = []
    if service_requested:
        notes.append(service_requested.group(1).strip())
    if description:
        notes.append(description.group(1).strip())
    if notes:
        label.setNotes(" ".join(notes))

    return label


# setup pngs and print labels
def labelExecute(label: Label | Ewaste):
    if type(label) == Label:
        # if label is a windows setup
        if label.getType() == "Windows":
            # iterate through serial numbers if multiple are provided in one ticket
            for position, serial in enumerate(label.serial):
                serial = serial.replace(",", "")
                # set domain to be printed
                if not label.domain:
                    dom = "Local"
                elif "Unknown" in label.domain:
                    dom = "__"
                else:
                    dom = label.domain

                # export ritm label (to be placed on outside of computer/box)
                ritm(
                    str(label.RITM),
                    strip_accents(str(label.client_name)),
                    strip_accents(str(label.requestor_name)),
                    datetime.now().strftime("%m/%d/%Y"),
                    False,
                    str(position + 1) + " of " + str(len(label.serial)),
                )
                # print label
                print_label(logger)

                # export windows setup label (next to trackpad on laptop)
                winsetup(
                    str(label.RITM),
                    str(label.dept),
                    str(serial),
                    str(dom),
                    strip_accents(str(label.client_name)),
                    label.backup,
                    str(label.printer),
                )
                # print label
                print_label(logger)

                # if client wants local admin
                if label.localA is not None:
                    # export username/password label
                    username(label.getUsername())
                    # print label
                    print_label(logger)

                    log_admin(
                        "RITM" + str(label.RITM),
                        str(serial),
                        strip_accents(str(label.client_name)),
                        label.getUsername(),
                    )

        # if label is a mac setup
        elif label.getType() == "Mac":
            # iterate through serial numbers if multiple are provided in one ticket
            for position, serial in enumerate(label.serial):
                # export ritm label (to be placed on outside of computer/box)
                ritm(
                    str(label.RITM),
                    strip_accents(str(label.client_name)),
                    strip_accents(str(label.requestor_name)),
                    datetime.now().strftime(
                        "%m/%d/%Y"
                    ),  # today's date (for intake date)
                    False,
                    str(position + 1) + " of " + str(len(label.serial)),
                )
                # print label
                print_label(logger)

                # export mac setup label (next to trackpad on laptop)
                macsetup(
                    str(label.RITM),
                    str(label.dept),
                    serial,
                    strip_accents(str(label.client_name))
                    + f" ({str(label.client_cruzid)})",
                    label.backup,
                    label.printer,
                    label.localA is not None,
                )
                # print label
                print_label(logger)

                # export password label
                print_label(logger, "static/tmpwd.png")

                if label.localA is not None:
                    log_admin(
                        "RITM" + str(label.RITM),
                        str(serial),
                        strip_accents(str(label.client_name)),
                        label.getUsername(),
                    )

        else:
            logger.error(
                f"parse: labelExecute: label type not recognized: {type(label)} {label}"
            )
            return
    elif type(label) == Ewaste and label.getType() == "Ewaste":
        # setup ewaste label for printing
        ewaste(
            str(label.RITM),
            datetime.now().strftime("%m/%d/%Y"),  # today's date (for intake date)
            str(label.serial),
            str(label.erase_type),
            str(label.export),
            label.jamf,
        )
        # print label
        print_label(logger)
    else:
        logger.error(
            f"parse: labelExecute: label type not recognized: {type(label)} {label}"
        )
        return

    # if label is a mac or windows
    if type(label) == Label and (
        label.getType() == "Windows" or label.getType() == "Mac"
    ):
        # if client wants a printer or has notes or has software requests (if notes need to be printed)
        if (
            label.printer.upper() != "NO"
            or len(label.notes) > 0
            or len(label.software) > 1
        ):
            # if no printer requested
            if label.printer.upper() == "NO":
                # print simple notes label - just software and notes
                for _ in range(len(label.serial)):
                    notes(label.RITM, label.software, label.notes)
                    print_label(logger)
            else:
                # print notes label w/ printer info, software, and notes
                for _ in range(len(label.serial)):
                    notes_printer(
                        label.RITM,
                        label.printer_ip.replace(".", "·"),
                        label.printer_notes,
                        label.software,
                        label.notes,
                    )
                    print_label(logger)
            # print whichever label was sent to tmp.png (notes.png or notes_printer.png)


if __name__ == "__main__":
    if type(logger) == log.logging.Logger:
        logger.info("parse: Starting...")
    else:
        print("Incorrect logger setup for parse")
        exit(1)

    while True:
        try:
            # get gmail account's username and password from environment variables
            app_username = os.getenv("app_username")
            app_password = os.getenv("app_password")

            if not app_username or not app_password:
                logger.error("parse: app username/password not found")
                exit(1)

            # login to email using imap
            gmail_host = "imap.gmail.com"
            mail = imaplib.IMAP4_SSL(gmail_host)
            mail.login(app_username, app_password)
            login_again = False

            logger.info("parse: Successfully logged in to email")

            # loop indefinitely
            while not login_again:
                print_this_round = False

                try:
                    # get Labels mailbox
                    mail.select("Labels", False)
                    # get unread label emails
                    _, selected_mails = mail.search(
                        None, '(TO "depot+labels@ucsc.edu")', "(UNSEEN)"
                    )
                    # print total number of unread label emails
                    # print("Total Intake Labels:", len(selected_mails[0].split()))
                    # print("==========================================\n")
                    if selected_mails[0].split():
                        logger.info(
                            f"parse: {len(selected_mails[0].split())} intake labels found"
                        )

                    labels = []
                    # iterate over selected emails
                    for num in selected_mails[0].split():
                        _, data = mail.fetch(num, "(RFC822)")
                        _, bytes_data = data[0]  # type: ignore
                        # mark email as read
                        mail.store(num, "+FLAGS", "\\Seen")

                        # parse string of bytes into readable email message, then iterate over it
                        email_message = email.message_from_bytes(bytes(bytes_data))
                        for part in email_message.walk():
                            # if email part is readable text, decode it and append it to labels
                            if (
                                part.get_content_type() == "text/plain"
                                or part.get_content_type() == "text/html"
                            ):
                                message = part.get_payload(decode=True)
                                labels.append(message.decode())  # type: ignore
                                break

                    if labels:
                        print_this_round = True

                    # iterate over list of labels (as email text)
                    for label in labels:
                        resnet_label = parse_resnet_label(label)
                        if resnet_label is not None:
                            logger.info(f"parse: label to print: {resnet_label}")
                            labelExecute(resnet_label)
                            continue

                        # split label by newlines
                        fields = re.split("<p>|<br>", label)
                        # remove closing html data from last line
                        fields[-1] = re.sub(r"<[^>]+>|\r\n", "", fields[-1])
                        # remove opening html data from first line, plus "RITM", plus heading format
                        m = re.search(r"RITM(\d+)", fields[0])                                                                                                           
                        ritm_number = m.group(1) if m else fields[0]                                                                                                     
                        # create label from RITM
                        label = Label(ritm_number)
                        # if ticket is from scotts valley campus, don't print a label
                        SVC = False

                        # iterate through email fields, using data to fill out fields of Label object
                        for field in fields:
                            if "Client: " in field:
                                field = field.replace("Client: ", "")
                                if field != "":
                                    label.setClient(field)
                            elif (
                                "Name of the new person who will be using this computer: "
                                in field
                            ):
                                field = field.replace(
                                    "Name of the new person who will be using this computer: ",
                                    "",
                                )
                                if field != "" and label.client_name != "":
                                    label.client_name = field
                                    label.client_cruzid = lookup_cruzid(field.strip()) or "____"
                            elif "Name of the current staff person who will be using the computer: " in field:
                                field = field.replace("Name of the current staff person who will be using the computer: ", "")
                                if field != "" and label.client_name != "":
                                    label.client_name = field
                                    label.client_cruzid = lookup_cruzid(field.strip()) or "____"
                            elif "Preferred username for login: " in field:
                                field = field.replace(
                                    "Preferred username for login: ", ""
                                )
                                if field != "":
                                    label.setGroupLogin(field)
                            elif (
                                "Group/position that will be using this computer: "
                                in field
                            ):
                                field = field.replace(
                                    "Group/position that will be using this computer: ",
                                    "",
                                )
                                if field != "":
                                    label.setGroupName(field)
                            elif "Client Phone: " in field:
                                phone = field.replace("Client Phone: ", "")
                            elif "Requestor: " in field:
                                label.setRequestor(field.replace("Requestor: ", ""))
                            elif "ComputerType: " in field:
                                label.setType(field.replace("ComputerType: ", ""))
                            elif "Scotts Valley: true" in field:
                                SVC = False
                                #break
                            elif "Client Department: " in field:
                                label.setDepartment(
                                    field.replace("Client Department: ", ""), weak=True
                                )
                                logger.info(f"client {label.dept}")
                            elif "Computer User's Department: " in field:
                                label.setDepartment(
                                    field.replace("Computer User's Department: ", "")
                                )
                                logger.info(f"user {label.dept}")
                            elif "Back up: " in field:
                                if "Yes" in field:
                                    label.backup = True
                                elif "No" in field:
                                    label.backup = False
                            elif "Adobe: " in field:
                                if "true" in field:
                                    label.setSoftware("CC")
                            elif "FileMaker 19: " in field:
                                if "true" in field:
                                    label.setSoftware("FM19")
                            elif "FileMaker 19.4: " in field:
                                if "true" in field:
                                    label.setSoftware("FM194")
                            elif "Firefox: " in field:
                                if "true" in field:
                                    label.setSoftware("FF")
                            elif "Project: " in field:
                                if "true" in field:
                                    label.setSoftware("Proj")
                            elif "Visio: " in field:
                                if "true" in field:
                                    label.setSoftware("Vis")
                            elif "Additional Software: " in field:
                                field = field.replace("Additional Software: ", "")
                                field = field.replace("\r\n", " ")
                                label.setSoftware(field)
                            elif "Additional Requirements and Information: " in field:
                                field = field.replace(
                                    "Additional Requirements and Information: ", ""
                                )
                                field = field.replace("\r\n", " ")
                                field = field.replace(",", "")
                                label.setNotes(field)
                            elif "Printer model:" in field:
                                field = field.replace("Printer model:", "")
                                field = field.replace("\r\n", "")
                                if len(field) != 0:
                                    label.setPrinter(field)
                            elif "Local Admin: " in field:
                                if "Yes" in field:
                                    label.setLocal()
                            elif "Domain: " in field:
                                if "know" in field:
                                    label.domain = "Unknown"
                                elif "None" in field:
                                    label.domain = ""
                                else:
                                    label.domain = field.replace("Domain: ", "")
                            elif "Serial Number or Service Tag: " in field:
                                serial = field.replace(
                                    "Serial Number or Service Tag: ", ""
                                )
                                label.serial = serial.split(", ")
                            elif "Return: " in field:
                                label.returnLoc = field.replace("Return: ", "")

                        if SVC:
                            logger.info("parse: SVC, skipping")
                            continue
                        # print text of label to console
                        logger.info(f"parse: label to print: {label}")

                        # setup label for printing & print it
                        labelExecute(label)
                        # print("==========================================\n")

                    # get Ewaste mailbox
                    mail.select("Ewaste", False)
                    # get unread ewaste emails
                    _, selected_mails = mail.search(
                        None, '(TO "depot+ewaste@ucsc.edu")', "(UNSEEN)"
                    )
                    # print total number of unread ewaste emails
                    # print("Total Ewaste Labels:", len(selected_mails[0].split()))
                    # print("==========================================\n")
                    if selected_mails[0].split():
                        logger.info(
                            f"parse: {len(selected_mails[0].split())} ewaste labels found"
                        )

                    labels = []
                    # iterate over selected emails
                    for num in selected_mails[0].split():
                        _, data = mail.fetch(num, "(RFC822)")
                        _, bytes_data = data[0]  # type: ignore
                        # mark email as read
                        mail.store(num, "+FLAGS", "\\Seen")

                        # parse string of bytes into readable email message, then iterate over it
                        email_message = email.message_from_bytes(bytes(bytes_data))
                        for part in email_message.walk():
                            # if email part is readable text, decode it and append it to labels
                            if (
                                part.get_content_type() == "text/plain"
                                or part.get_content_type() == "text/html"
                            ):
                                message = part.get_payload(decode=True)
                                labels.append(message.decode())  # type: ignore
                                break

                    if labels:
                        print_this_round = True

                    # iterate over list of labels (as email text)
                    for label in labels:
                        # remove carriage returns
                        fields = label.replace("\r", "")
                        # split label by newlines
                        fields = re.split("\n", fields)
                        # remove empty fields
                        fields = list(filter(None, fields))
                        # remove last field (Powered by AppSheet)
                        fields = fields[:-1]
                        # remove "RITM"
                        fields[0] = fields[0].replace("RITM", "")
                        # create label from RITM
                        label = Ewaste(fields[0])

                        # iterate through email fields, using data to fill out fields of Ewaste object
                        for field in fields:
                            if "Serial Number: " in field:
                                label.serial = field.replace("Serial Number: ", "")
                            elif "Data Disposition: " in field:
                                label.setEraseType(
                                    field.replace("Data Disposition: ", "")
                                )
                            elif "Surplus Form: " in field:
                                label.setExport(field.replace("Surplus Form: ", ""))
                            elif "Jamf Status: " in field:
                                label.setJamf(field.replace("Jamf Status: ", ""))

                        # print text of label to console
                        logger.info(f"parse: label to print: {label}")
                        # setup label for printing & print it
                        labelExecute(label)
                        # print("==========================================\n")

                    # Resnet mailbox (custom labels)
                    mail.select("Resnet", False)
                    # get unread resnet emails (folder already filtered), any unseen
                    _, selected_mails = mail.search(None, "(UNSEEN)")
                    if selected_mails[0].split():
                        logger.info(
                            f"parse: {len(selected_mails[0].split())} resnet labels found"
                        )

                    labels_resnet = []
                    # iterate over selected emails
                    for num in selected_mails[0].split():
                        _, data = mail.fetch(num, "(RFC822)")
                        _, bytes_data = data[0]  # type: ignore
                        # mark email as read
                        mail.store(num, "+FLAGS", "\\Seen")

                        # parse string of bytes into readable email message, then iterate over it
                        email_message = email.message_from_bytes(bytes(bytes_data))
                        for part in email_message.walk():
                            if (
                                part.get_content_type() == "text/plain"
                                or part.get_content_type() == "text/html"
                            ):
                                message = part.get_payload(decode=True)
                                labels_resnet.append(message.decode())  # type: ignore
                                break

                    if labels_resnet:
                        print_this_round = True

                    for body in labels_resnet:
                        try:
                            raw = body.replace("\r", "")
                            # Extract RITM from header or anywhere in the original body before stripping tags
                            ritm_top = ""
                            m = re.search(r"RITM\s*([0-9]+)", raw, re.IGNORECASE)
                            if m:
                                ritm_top = m.group(1)

                            # Normalize HTML breaks and strip simple tags
                            raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
                            raw = re.sub(r"(?i)</?p>", "", raw)
                            raw = re.sub(r"(?i)</?(html|body|head)>", "", raw)
                            raw = re.sub(r"(?is)<h3[^>]*>.*?</h3>", "", raw)
                            # Remove any other tags
                            raw = re.sub(r"<[^>]+>", "", raw)

                            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

                            opened_by = ""
                            requestor = ""
                            ritm_id = ""
                            computer_model = ""
                            device_serial = ""
                            power_adapter = ""
                            service_req = ""
                            card_provided = ""
                            card_serial = ""
                            os_version = ""
                            verified_access = False

                            for ln in lines:
                                if ln.startswith("Opened by:"):
                                    opened_by = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Requestor:"):
                                    requestor = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Originating Incident Number:"):
                                    ritm_id = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Computer Model:"):
                                    computer_model = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Serial Number:"):
                                    device_serial = ln.split(":", 1)[1].strip()
                                elif re.match(r"(?i)^Serial number:", ln):
                                    card_serial = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Power Adapter:"):
                                    power_adapter = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Select list for service requested:"):
                                    service_req = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Card provided:"):
                                    card_provided = ln.split(":", 1)[1].strip()
                                elif ln.startswith("OS version:"):
                                    os_version = ln.split(":", 1)[1].strip()
                                elif ln.startswith("Verified Access:"):
                                    val = ln.split(":", 1)[1].strip().lower()
                                    verified_access = val in ("true", "yes", "y", "1", "checked", "x")

                            name_val = requestor or opened_by
                            name_val = strip_accents(name_val) if name_val else ""

                            # Prefer RITM found in header; fall back to incident number if missing
                            ritm_used = ritm_top or ritm_id

                            # Build and print label
                            resnet(
                                name=name_val,
                                serial=device_serial,
                                ritm=ritm_used,
                                power_adapter=power_adapter,
                                service=service_req,
                                card_number=card_serial,
                                verified_access=verified_access,
                                os_version=os_version,
                            )
                            print_label(logger, "resnet.png")
                            logger.info("parse: printed resnet.png")

                            # If the ticket says it has a power adapter, also print a Name/RITM-only label
                            if power_adapter and power_adapter.strip().lower() not in {"no", "none", "n/a", "na", "false", "0"}:
                                resnet_name_ritm(name=name_val, ritm=ritm_used)
                                print_label(logger, "resnet_name_ritm.png")
                                logger.info("parse: printed resnet_name_ritm.png")

                            logger.info(
                                f"parse: resnet label: name={name_val}, serial={device_serial}, ritm={ritm_used}, power={power_adapter}, service={service_req}, card_serial={card_serial}, verified={verified_access}, os={os_version}"
                            )
                        except Exception:
                            logger.error(
                                f"parse: resnet parse error: {traceback.format_exc()}"
                            )
                except imaplib.IMAP4.abort as e:
                    logger.error(
                        f"parse: could not get mail from folder: {traceback.format_exc()}"
                    )
                    if "socket error" in str(e):
                        # gmail will throw a socket error if we have been logged in for too long.
                        login_again = True

                if print_this_round:
                    logger.info("parse: done")

                # delay 1 second between runs
                time.sleep(1)
        except Exception:
            logger.error(f"parse: {traceback.format_exc()}")
