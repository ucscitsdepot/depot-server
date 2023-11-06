import email
import imaplib
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from os import getenv

# import pyautogui
from dotenv import load_dotenv

from ewaste import Ewaste
from label import Label
from write_pngs import *

load_dotenv()

# path_to_ptouch = "C:\\Program Files (x86)\\Brother\\Ptedit54\\Ptedit54.exe"
# pyautogui.FAILSAFE = False


# def printlb(allsheets=True, number=1, ewaste=False):
#     pyautogui.keyDown("ctrl")
#     pyautogui.press("p")
#     pyautogui.keyUp("ctrl")
#     if allsheets and number == 1:
#         pyautogui.press("Tab", presses=8)
#         if not ewaste:
#             pyautogui.press("down")
#     elif allsheets and number != 1:
#         pyautogui.press("Tab", presses=6)
#         pyautogui.press(str(number))
#         pyautogui.press("Tab", presses=2)
#         pyautogui.press("down")
#     elif number != 1:
#         pyautogui.press("Tab", presses=6)
#         pyautogui.press(str(number))
#     pyautogui.press("enter")


def strip_accents(data):
    # return ''.join(x for x in unicodedata.normalize('NFKD', data) if x in string.printable)
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
            # winritm = open("out.txt", "w")
            # winritm.write(
            #     "RITM, ST, PCNAME, FULLUSERNAME, DOMAIN, PRINTER, REQUESTORNAME, BACKUP, RETURNLOC, ITEMS\n"
            # )
            # winritm.write(
            #     "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s\n"
            #     % (
            #         str(label.RITM),
            #         str(serial),
            #         str(label.pcname),
            #         strip_accents(str(label.client_name)),
            #         dom.upper(),
            #         str(label.printer),
            #         strip_accents(str(label.requestor_name)),
            #         str(label.backup),
            #         str(label.returnLoc),
            #         str(position + 1) + " of " + str(len(label.serial)),
            #     )
            # )
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

    # TODO: local admin for Macs
    elif label.getType() == "Mac":
        for position, serial in enumerate(label.serial):
            # macritm = open("out_mac.txt", "w")
            # macritm.write(
            #     "RITM, PCNAME, FULLUSERNAME, PRINTER, REQUESTORNAME, BACKUP, RETURNLOC, SERIAL, ITEMS\n"
            # )
            # macritm.write(
            #     "%s, %s, %s, %s, %s, %s, %s, %s, %s\n"
            #     % (
            #         label.RITM,
            #         label.pcname,
            #         strip_accents(label.client_name),
            #         label.printer,
            #         strip_accents(label.requestor_name),
            #         label.backup,
            #         label.returnLoc,
            #         serial,
            #         str(position + 1) + " of " + str(len(label.serial)),
            #     )
            # )

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
        # ewasteritm = open("out_ewaste.txt", "w")
        # ewasteritm.write("RITM, SERIAL, ERASE, EXPORT, JAMF\n")
        # ewasteritm.write(
        #     "%s, %s, %s, %s, %s\n"
        #     % (
        #         str(label.RITM),
        #         str(label.serial),
        #         str(label.erase_type),
        #         str(label.export),
        #         str(label.jamf),
        #     )
        # )

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
        # noteritm = open("out_note.txt", "w")
        # noteritm.write("RITM, IP, PRINTER, SOFT, NOTE\n")
        # noteritm.write(
        #     "%s, %s, %s, %s, %s\n"
        #     % (
        #         label.RITM,
        #         label.printer_ip.replace(".", "·"),
        #         label.printer_notes,
        #         label.software,
        #         label.notes,
        #     )
        # )
        # noteritm.close()
        # if label.printer == "NO" and len(label.notes) == 0 and len(label.software) == 1:
        #     time.sleep(2)
        #     return
        # elif label.printer == "NO":
        #     P = subprocess.Popen([path_to_ptouch, "noteritmsimple.lbx"])
        # else:
        #     P = subprocess.Popen([path_to_ptouch, "noteritm.lbx"])
        # time.sleep(10)
        # printlb(allsheets=False, number=len(label.serial))
        # time.sleep(2)
        # P.terminate()


app_username = getenv("app_username")
app_password = getenv("app_password")

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
