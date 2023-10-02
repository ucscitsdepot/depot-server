import imaplib
import email
from ewaste import Ewaste
import subprocess
import pyautogui
import time
import re
from os import getenv
from dotenv import load_dotenv
import unicodedata

load_dotenv()

path_to_ptouch = "C:\\Program Files (x86)\\Brother\\Ptedit54\\Ptedit54.exe"
pyautogui.FAILSAFE = False


def printlb(allsheets=True, number=1):
    pyautogui.keyDown("ctrl")
    pyautogui.press("p")
    pyautogui.keyUp("ctrl")
    if allsheets and number == 1:
        pyautogui.press("Tab", presses=8)
        # pyautogui.press("down")
    elif allsheets and number != 1:
        pyautogui.press("Tab", presses=6)
        pyautogui.press(str(number))
        pyautogui.press("Tab", presses=2)
        pyautogui.press("down")
    elif number != 1:
        pyautogui.press("Tab", presses=6)
        pyautogui.press(str(number))
    pyautogui.press("enter")


def labelExecute(label):
    if label.getType() == "Ewaste":
        ewasteritm = open("out_ewaste.txt", "w")
        ewasteritm.write("RITM, SERIAL, ERASE, EXPORT, JAMF\n")
        ewasteritm.write(
            "%s, %s, %s, %s, %s\n"
            % (
                str(label.RITM),
                str(label.serial),
                str(label.erase_type),
                str(label.export),
                str(label.jamf),
            )
        )
        ewasteritm.close()
        P = subprocess.Popen([path_to_ptouch, "Ewaste.lbx"])
        time.sleep(10)
        printlb()
        time.sleep(1)
        P.terminate()


username = getenv("app_username")
app_password = getenv("app_password")

gmail_host = "imap.gmail.com"
mail = imaplib.IMAP4_SSL(gmail_host)
mail.login(username, app_password)

while True:
    mail.select("Ewaste", False)
    _, selected_mails = mail.search(None, '(TO "depot+ewaste@ucsc.edu")', "(UNSEEN)")
    print("Total Labels:", len(selected_mails[0].split()))
    print("==========================================\n")
    pyautogui.press("F15")

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
        fields[0] = fields[0].replace("RITM00", "")

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
