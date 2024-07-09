# class for Ewaste tickets
class Ewaste:
    def __init__(self, RITM):
        self.RITM = RITM  # RITM stored as an int
        self.serial = ""  # Serial/Service Tag stored as string
        self.erase_type = None
        self.export = None
        self.jamf = None

    # print label when generated
    def __str__(self):
        strs = "RITM[" + str(self.RITM) + "]\n"
        strs += "serial[" + str(self.serial) + "]\n"
        strs += "erase_type[" + str(self.erase_type) + "]\n"
        strs += "surplus[" + str(self.export) + "]\n"
        strs += "jamf[" + str(self.jamf) + "]\n"
        return strs

    # erase type - 3 pass wipe, cryptographic erase, physically destroy disk, no erase
    def setEraseType(self, input):
        if "3 Pass" in input:
            self.erase_type = "3 Pass"
        elif "Crypto" in input:
            self.erase_type = "Crypto"
        elif "Destroy" in input:
            self.erase_type = "Destroy"
        else:
            self.erase_type = None

    # Surplus or Ewaste
    def setExport(self, input):
        if "Y" in input:
            self.export = "Surplus"
        else:
            self.export = "Ewaste"

    # False: needs to be removed from Jamf
    # True: already removed from Jamf
    # None: Windows, does not need to be removed from Jamf
    def setJamf(self, input):
        if "Not Done" in input:
            self.jamf = False
        elif "Complete" in input:
            self.jamf = True
        else:
            self.jamf = None

    # the other label class distinguishes between "Mac" and "Windows" as types, so a getType() function here allows us to just call it on all label/ewaste objects
    def getType(self):
        return "Ewaste"
