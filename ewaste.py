import re


class Ewaste:
    def __init__(self, RITM):
        self.RITM = RITM
        self.serial = ""
        self.erase_type = None
        self.export = None
        self.jamf = None

    def __str__(self):
        strs = "RITM[" + str(self.RITM) + "]\n"
        strs += "serial[" + str(self.serial) + "]\n"
        strs += "erase_type[" + str(self.erase_type) + "]\n"
        strs += "surplus[" + str(self.export) + "]\n"
        strs += "jamf[" + str(self.jamf) + "]\n"
        return strs

    def setEraseType(self, input):
        if "3 Pass" in input:
            self.erase_type = "3 Pass"
        elif "Crypto" in input:
            self.erase_type = "Crypto"
        elif "Destroy" in input:
            self.erase_type = "Destroy"
        else:
            self.erase_type = None

    def setExport(self, input):
        if "Y" in input:
            self.export = "Surplus"
        else:
            self.export = "Ewaste"

    def setJamf(self, input):
        if "Not Done" in input:
            self.jamf = ""
        elif "Complete" in input:
            self.jamf = "Done"
        else:
            self.jamf = "No"

    def getType(self):
        return "Ewaste"
