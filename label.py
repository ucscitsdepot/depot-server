import csv
import difflib
import re

# list of all departments & their appropriate abbreviations for the computer name prefixes
departments = {}
with open("departments.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        departments[row["d"]] = row["a"]


# class for setup Label tickets
class Label:
    def __init__(self, RITM):
        self.RITM = RITM  # RITM stored as an int
        self.software = ""  # list of software
        self.backup = False  # does the computer need to be backed up
        self.type = None  # Mac vs Windows
        self.client_cruzid = None  # client's username/computer's name if for individual
        self.client_name = None  # client's full name (primary name on ticket, user's name on local accounts)
        self.requestor_name = (
            None  # requestor's full name (may be different from client)
        )
        self.localA = None  # does the user/group want a local admin
        self.domain = ""  # what domain to enroll the computer in
        self.serial = []  # computer's serial/service tag
        self.returnLoc = ""  # return location on campus
        self.dept = None  # department prefix for computer name
        self.group = False  # group that will be using this computer
        self.printer = "No"  # does the user want a printer (No/Drivers/Drivers & Add)
        self.printer_notes = ""  # printer's names, etc
        self.printer_ip = ""  # printer's ip(s)
        self.notes = ""  # client ticket notes

    def __str__(self):
        strs = "RITM[" + str(self.RITM) + "]\n"
        strs += "dept[" + str(self.dept) + "]\n"
        strs += "software[" + str(self.software) + "]\n"
        strs += "backup[" + str(self.backup) + "]\n"
        strs += "type[" + str(self.type) + "]\n"
        strs += "client_cruzid[" + str(self.client_cruzid) + "]\n"
        strs += "client_name[" + str(self.client_name) + "]\n"
        strs += "requestor_name[" + str(self.requestor_name) + "]\n"
        strs += "localA[" + str(self.localA) + "]\n"
        strs += "domain[" + str(self.domain) + "]\n"
        strs += "serial[" + str(", ".join(self.serial)) + "]\n"
        strs += "printer[" + str(self.printer) + "]\n"
        strs += "printer_notes[" + str(self.printer_notes) + "]\n"
        strs += "printer_ip[" + str(self.printer_ip) + "]\n"
        strs += "notes[" + str(self.notes) + "]\n"
        return strs

    # append data to software field
    def setSoftware(self, soft):
        self.software = self.software + " " + soft.replace(",", " ")

    # set client data (cruzid, name)
    def setClient(self, user):
        self.client_cruzid = user[user.find("(") + 1 : user.find(")")]
        self.client_name = user[: user.find("(") - 1]

    # group username
    def setGroupLogin(self, group: str):
        self.group = True
        self.client_cruzid = group.replace(" ", "")

    # group's full user name
    def setGroupName(self, group: str):
        self.client_name = group.replace(",", " ")

    # requestor name (may be same as client)
    def setRequestor(self, user):
        self.requestor_name = user[: user.find("(") - 1]

    # Mac/Windows type
    def setType(self, type):
        self.type = type

    # return type of computer (Mac/Windows/None for other)
    def getType(self):
        if self.type and "Mac" in self.type:
            return "Mac"
        elif self.type and "PC\\Windows" in self.type:
            return "Windows"
        else:
            return None

    # set local admin username
    def setLocal(self):
        self.localA = ""
        if self.domain and self.domain != "Unknown":
            self.localA += ".\\"
        self.localA += "admin.%s" % self.client_cruzid

    # set local username
    def getUsername(self):
        username = ""
        if self.domain:
            username += ".\\"
        username += "admin.%s" % self.client_cruzid
        return username

    # get department from csv file, then set the pcname using it
    def setDepartment(self, dept, weak=False):
        if weak and self.dept is not None and self.dept != "___":
            return
        
        match = difflib.get_close_matches(dept, departments.keys(), 1, 0.7)
        if match != []:
            self.dept = departments[match[0]]
        elif self.dept is None:
            self.dept = "___"

    # fill out printer/printer_ip/printer_notes fields
    def setPrinter(self, notes):
        self.printer_notes = notes.replace(",", ";").split(" ")
        for i in self.printer_notes:
            validip = re.match(r"(.).*\1.*\1", i)
            if validip:
                self.printer_ip = self.printer_ip + " " + i
                self.printer_notes.remove(i)
        self.printer_notes = " ".join([str(elem) for elem in self.printer_notes])
        if self.printer_ip != "":
            self.printer = "DRIVERS & ADD"
        else:
            self.printer = "DRIVERS"

    # get client notes
    def setNotes(self, notes):
        self.notes = notes.replace(",", ";")
        self.notes = self.notes.replace("&nbsp;", " ")
