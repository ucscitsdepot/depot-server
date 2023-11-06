import email
import imaplib
import re
import subprocess
import time
import unicodedata
from datetime import datetime
import os

# import pyautogui
from dotenv import load_dotenv

os.chdir(os.path.dirname(os.path.realpath(__file__)))

from ewaste import Ewaste
from label import Label
from write_pngs import *

load_dotenv()


def strip_accents(data):
    return unicodedata.normalize("NFD", data).encode("ascii", "ignore").decode("utf-8")


def labelExecute(label):
    processes = list()
    if label.getType() == "Windows":
        for position, serial in enumerate(label.serial):
            serial = serial.replace(",", "")
            if label.domain is None:
                dom = "Local"
            elif "Unknown" in label.domain:
                dom = "__"
            else:
                dom = label.domain
            ritm(
                str(label.RITM),
                strip_accents(str(label.client_name)),
                strip_accents(str(label.requestor_name)),
                datetime.now().strftime("%m/%d/%Y"),
                False,
                str(position + 1) + " of " + str(len(label.serial)),
                str(label.returnLoc),
            )
            processes.append(print_label())

            winsetup(
                str(label.RITM),
                str(label.pcname),
                str(serial),
                strip_accents(str(label.client_name)),
                label.backup,
                str(label.printer),
            )
            processes.append(print_label())

            if label.localA is not None:
                username(label.getUsername())
                processes.append(print_label())

    elif label.getType() == "Mac":
        for position, serial in enumerate(label.serial):
            ritm(
                str(label.RITM),
                strip_accents(str(label.client_name)),
                strip_accents(str(label.requestor_name)),
                datetime.now().strftime("%m/%d/%Y"),
                False,
                str(position + 1) + " of " + str(len(label.serial)),
                str(label.returnLoc),
            )
            processes.append(print_label())

            macsetup(
                str(label.RITM),
                label.pcname,
                serial,
                strip_accents(str(label.client_name)),
                label.backup,
                label.printer,
            )
            processes.append(print_label())

            if label.localA is not None:
                username(strip_accents(str(label.client_name)))
                processes.append(print_label())
                username("Admin " + strip_accents(str(label.client_name)))
                processes.append(print_label())
            else:
                processes.append(print_label("png/tmpwd.png"))

    elif label.getType() == "Ewaste":
        ewaste(
            str(label.RITM),
            datetime.now().strftime("%m/%d/%Y"),
            str(label.serial),
            str(label.erase_type),
            str(label.export),
            label.jamf,
        )

    if label.getType() == "Windows" or label.getType() == "Mac":
        if label.printer != "NO" or len(label.notes) > 0 or len(label.software) > 1:
            if label.printer == "NO":
                notes(label.RITM, label.software, label.notes)
            else:
                notes_printer(
                    label.RITM,
                    label.printer_ip.replace(".", "·"),
                    label.printer_notes,
                    label.software,
                    label.notes,
                )
            processes.append(print_label())


app_username = os.getenv("app_username")
app_password = os.getenv("app_password")

gmail_host = "imap.gmail.com"
mail = imaplib.IMAP4_SSL(gmail_host)
mail.login(app_username, app_password)

while True:
    mail.select("Labels", False)
    _, selected_mails = mail.search(None, '(TO "depot+labels@ucsc.edu")', "(UNSEEN)")
    print("Total Intake Labels:", len(selected_mails[0].split()))
    print("==========================================\n")
    # pyautogui.press("F15")

    labels = []
    for num in selected_mails[0].split():
        _, data = mail.fetch(num, "(RFC822)")
        _, bytes_data = data[0]
        mail.store(num, "+FLAGS", "\Seen")

        email_message = email.message_from_bytes(bytes_data)
        for part in email_message.walk():
            if (
                part.get_content_type() == "text/plain"
                or part.get_content_type() == "text/html"
            ):
                message = part.get_payload(decode=True)
                # print(message)
                labels.append(message.decode())
                break

    for label in labels:
        # fields = label.split('<br>')
        fields = re.split("<p>|<br>", label)
        fields[-1] = fields[-1].replace("</p></body></html>\r\n", "")
        fields[0] = (
            fields[0].replace('<html><head></head><body><h3 id="main">RITM', "")
        ).replace("&nbsp;</h3>\r\n", "")
        # print(fields)
        # fields.remove('')
        label = Label(fields[0])
        SVC = False

        for field in fields:
            if "Client: " in field:
                field = field.replace("Client: ", "")
                if field != "":
                    label.setClient(field)
            elif "Name of the new person who will be using this computer: " in field:
                field = field.replace(
                    "Name of the new person who will be using this computer: ", ""
                )
                if field != "" and label.client_name != "":
                    label.client_name = field
                    label.client_cruzid = "____"
            elif "Preferred username for login: " in field:
                field = field.replace("Preferred username for login: ", "")
                if field != "":
                    label.setGroupLogin(field)
            elif "Group/position that will be using this computer: " in field:
                field = field.replace(
                    "Group/position that will be using this computer: ", ""
                )
                if field != "":
                    label.setGroupName(field)
            elif "Requestor: " in field:
                label.setRequestor(field.replace("Requestor: ", ""))
            elif "ComputerType: " in field:
                label.setType(field.replace("ComputerType: ", ""))
            elif "Scotts Valley: true" in field:
                SVC = True
                break
            elif "Client Department: " in field:
                label.setDepartment(field.replace("Client Department: ", ""))
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
                field = field.replace("Additional Requirements and Information: ", "")
                field = field.replace("\r\n", " ")
                field = field.replace(",", "")
                label.setNotes(field)
            elif "Printer model:" in field:
                field = field.replace("Printer model:", "")
                field = field.replace("\r\n", " ")
                if len(field) != 0:
                    label.setPrinter(field)
            elif "Local Admin: " in field:
                if "Yes" in field:
                    label.setLocal()
            elif "Domain: " in field:
                if "know" in field:
                    label.domain = "Unknown"
                elif "None" in field:
                    label.domain = None
                else:
                    label.domain = field.replace("Domain: ", "")
            elif "Serial Number or Service Tag: " in field:
                label.serial = field.replace("Serial Number or Service Tag: ", "")
                label.serial = label.serial.split(", ")
            elif "Return: " in field:
                label.returnLoc = field.replace("Return: ", "")
                if label.returnLoc == "":
                    label.returnLoc = None

        if SVC:
            continue
        print(label)
        labelExecute(label)
        print("==========================================\n")

    mail.select("Ewaste", False)
    _, selected_mails = mail.search(None, '(TO "depot+ewaste@ucsc.edu")', "(UNSEEN)")
    print("Total Ewaste Labels:", len(selected_mails[0].split()))
    print("==========================================\n")
    # pyautogui.press("F15")

    labels = []
    for num in selected_mails[0].split():
        _, data = mail.fetch(num, "(RFC822)")
        _, bytes_data = data[0]
        mail.store(num, "+FLAGS", "\Seen")

        email_message = email.message_from_bytes(bytes_data)
        for part in email_message.walk():
            if (
                part.get_content_type() == "text/plain"
                or part.get_content_type() == "text/html"
            ):
                message = part.get_payload(decode=True)
                # print(message)
                labels.append(message.decode())
                break

    for label in labels:
        fields = label.replace("\r", "")
        fields = re.split("\n", fields)
        fields = list(filter(None, fields))
        fields = fields[:-1]
        fields[0] = fields[0].replace("RITM", "")

        print(fields)
        label = Ewaste(fields[0])

        for field in fields:
            if "Serial Number: " in field:
                label.serial = field.replace("Serial Number: ", "")
            elif "Data Disposition: " in field:
                label.setEraseType(field.replace("Data Disposition: ", ""))
            elif "Surplus Form: " in field:
                label.setExport(field.replace("Surplus Form: ", ""))
            elif "Jamf Status: " in field:
                label.setJamf(field.replace("Jamf Status: ", ""))

        print(label)
        labelExecute(label)
        print("==========================================\n")
    time.sleep(1)
