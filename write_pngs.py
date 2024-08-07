import fcntl
import subprocess
import time
from threading import Thread

from PIL import Image, ImageDraw, ImageFont

from history import log_thread


# find correct textlength to fit in desired size
# derived from https://stackoverflow.com/questions/58041361/break-long-drawn-text-to-multiple-lines-with-pillow
def break_fix(text, width, font, draw):
    if not text:
        return
    lo = 0
    hi = len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        t = text[:mid]
        w = draw.textlength(t, font=font)
        if w <= width:
            lo = mid
        else:
            hi = mid - 1
    t = text[:lo]
    w = draw.textlength(t, font=font)
    yield t, w
    yield from break_fix(text[lo:], width, font, draw)


# draw text to fit within certain width using break_fix()
def fit_text(img, text, color, font, x, y, w, h):
    draw = ImageDraw.Draw(img)
    pieces = list(break_fix(text, w, font, draw))
    for t, _ in pieces:
        draw.text((x, y), t, font=font, fill=color)
        y += h


# setup ewaste label
def ewaste(ritm: str, date: str, serial: str, erase_type: str, export: str, jamf: bool):
    log_thread("ewaste", ritm, date, serial, erase_type, export, jamf)
    img = Image.open("static/ewaste.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)

    # import fonts
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    font = ImageFont.truetype("Roboto-Regular.ttf", 250)

    # draw text for ritm, date, export type, serial, and erase type
    imgdraw.text((900, 120), ritm, (0, 0, 0), font=ritm_font)
    imgdraw.text((70, 530), date, (0, 0, 0), font=font)
    imgdraw.text((1570, 530), export, (0, 0, 0), font=font)
    imgdraw.text((800, 870), serial, (0, 0, 0), font=font)
    imgdraw.text((1450, 1150), erase_type, (0, 0, 0), font=font)

    x = 715
    y = 1480
    w = 257
    h = 256
    if jamf is True:
        # if jamf is done, fill in jamf checkbox
        imgdraw.rectangle((x, y, x + w, y + h), "black")
    elif jamf is None:
        # if jamf not needed, strikethrough the jamf field
        imgdraw.line(
            (70, y + h / 2 - 20) + (70 + x + w, y + h / 2 - 20), "black", width=20
        )

    img.save("tmp.png")


def ritm(
    ritm: str,
    client_name: str,
    requestor_name: str,
    date: str,
    migration: bool,
    index: str,
):
    log_thread("ritm", ritm, client_name, requestor_name, date, migration, index)
    img = Image.open("static/ritm.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)

    # import fonts
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    name_font = ImageFont.truetype("Roboto-Italic.ttf", 200)
    large_name_font = ImageFont.truetype("Roboto-Italic.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 160)

    # draw text for ritm, date, requestor name, client name
    imgdraw.text((900, 190), ritm, (0, 0, 0), font=ritm_font)
    imgdraw.text((70, 625), "Client & Requestor:", (0, 0, 0), font=font)
    imgdraw.text((70, 850), client_name, (0, 0, 0), font=large_name_font)
    imgdraw.text((70, 1100), requestor_name, (0, 0, 0), font=large_name_font)
    imgdraw.text((70, 1330), "Intake Date:", (0, 0, 0), font=font)
    imgdraw.text((1300, 1330), date, (0, 0, 0), font=font)

    imgdraw.rectangle((1770, 1600, 1700 + 750, 1600 + 300), None, "black", 10)

    # print index (X of Y), make it smaller if necessary
    if len(index) <= 6:
        imgdraw.text((1815, 1610), index, (0, 0, 0), font=font)
    else:
        imgdraw.text((1815, 1660), index, (0, 0, 0), font=small_font)

    # # print return location, wrap text
    # fit_text(img, returnloc, (0, 0, 0), small_font, 70, 1750, 2800, 120)

    imgdraw.text((70, 1600), "Migration", (0, 0, 0), font=font)

    box_x = 1100
    box_y = 1615
    box_w = 250
    box_h = 250
    imgdraw.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), None, "black", 10)

    if migration is True:
        gap = 30
        x = box_x + gap
        y = box_y + gap
        w = box_w - gap * 2
        h = box_h - gap * 2
        imgdraw.rectangle((x, y, x + w, y + h), "black")
    elif migration is None:
        # x = 70
        # y = 1615
        # w = 1070
        # h = 0
        # imgdraw.line((x, y) + (x + w, y + h), "black", width=20)
        # imgdraw.line((x + w, y) + (x, y + h), "black", width=20)
        imgdraw.text((1400, 1620), "No", (0, 0, 0), font=name_font)

    img.save("tmp.png")


def macsetup(
    ritm: str,
    dept: str,
    serial: str,
    client_name: str,
    backup: bool,
    printers: str,
    localA: bool,
):
    log_thread("macsetup", ritm, dept, serial, client_name, backup, printers, localA)
    img = Image.open("static/macsetup.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((900, 120), ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    name_font = ImageFont.truetype("Roboto-Italic.ttf", 200)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    if imgdraw.textlength(dept + "-" + serial[-7:], font) > 1800:
        imgdraw.text((1050, 500), dept + "-" + serial[-7:], (0, 0, 0), font=small_font)
    else:
        imgdraw.text((1050, 430), dept + "-" + serial[-7:], (0, 0, 0), font=font)

    imgdraw.text((620, 650), serial, (0, 0, 0), font=font)
    imgdraw.text((100, 1050), client_name, (0, 0, 0), font=name_font)

    if backup is False:
        imgdraw.text((1300, 1300), "No", (0, 0, 0), font=name_font)

    if localA:
        imgdraw.text((1700, 1275), "Admin", (0, 0, 0), font=font)
        x = 2400
        y = 1305
        w = 200
        h = 200
        imgdraw.rectangle((x, y, x + w, y + h), None, "black", 7)

    imgdraw.text((1150, 1800), printers, (0, 0, 0), font=font)

    img.save("tmp.png")


def notes_printer(ritm: str, printerip: str, printermodel: str, sw: str, notes: str):
    log_thread("notes_printer", ritm, printerip, printermodel, sw, notes)
    img = Image.open("static/notes_printer.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((920, 120), ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 160)

    if len(printerip) > 0:
        fit_text(img, printerip, (0, 0, 0), small_font, 90, 650, 2800, 160)
    if len(printermodel) > 0:
        fit_text(img, printermodel, (0, 0, 0), small_font, 90, 1100, 2800, 160)
    if len(sw) > 0:
        fit_text(img, sw, (0, 0, 0), small_font, 90, 1750, 2800, 160)
    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 2320, 2800, 160)

    img.save("tmp.png")


def notes(ritm: str, sw: str, notes: str):
    log_thread("notes", ritm, sw, notes)
    img = Image.open("static/notes.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((920, 120), ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 160)

    if len(sw) > 0:
        fit_text(img, sw, (0, 0, 0), small_font, 90, 670, 2800, 160)
    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 1200, 2800, 160)

    img.save("tmp.png")


def username(username: str):
    log_thread("username", username)
    img = Image.open("static/username.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    font = ImageFont.truetype("Roboto-Medium.ttf", 230)

    imgdraw.text((1450, 540), username, (0, 0, 0), font=font, anchor="mt")

    img.save("tmp.png")


def winsetup(
    ritm: str,
    dept: str,
    servicetag: str,
    domain: str,
    client_name: str,
    backup: bool,
    printers: str,
):
    log_thread("winsetup", ritm, dept, servicetag, domain, client_name, backup, printers)
    img = Image.open("static/winsetup.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((930, 120), ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    name_font = ImageFont.truetype("Roboto-Italic.ttf", 200)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    imgdraw.text((1300, 450), servicetag, (0, 0, 0), font=font)

    if imgdraw.textlength(dept + "-" + servicetag, font) > 2800:
        imgdraw.text((100, 850), dept + "-" + servicetag, (0, 0, 0), font=small_font)
    else:
        imgdraw.text((100, 850), dept + "-" + servicetag, (0, 0, 0), font=font)

    imgdraw.text((100, 1300), client_name, (0, 0, 0), font=name_font)
    imgdraw.text((2300, 1500), domain, (0, 0, 0), font=font)

    if backup is False:
        imgdraw.text((1200, 2170), "No", (0, 0, 0), font=font)

    imgdraw.text((1000, 2400), printers, (0, 0, 0), font=font)

    img.save("tmp.png")


def ritm_generic(ritm: str, notes: str):
    log_thread("ritm_generic", ritm, notes)
    img = Image.open("static/ritm_generic.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 330)
    imgdraw.text((860, 25), ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 160)

    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 520, 2800, 160)

    img.save("tmp.png")


def inc_generic(inc: str, notes: str):
    log_thread("inc_generic", inc, notes)
    img = Image.open("static/inc_generic.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 330)
    imgdraw.text((630, 25), inc, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 160)

    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 520, 2800, 160)

    img.save("tmp.png")


# file path to lock on, the exact path is not important as long as it's identical across processes
active_write_path = "/tmp/active_write_print"

# device address for printer
try:
    address = open("address").readline().strip()
except:
    address = "file:///dev/usb/lp0"


def print_label(logger, file="tmp.png"):
    # attempt to acquire a lock on the tmp file using flock
    f = check_file()
    # if check_file fails for some reason (it shouldn't though), repeat
    while not f:
        time.sleep(0.1)
        f = check_file()
    # call printer library - this is blocking but non-exclusive, so multiple simultaneous calls to this will just cause one to succeed and the rest to error
    p = subprocess.run(
        ["brother_ql", "-m", "QL-570", "-p", address, "print", "-l", "62", file],
        capture_output=True,
    )
    # while printer proces is still running, delay
    while type(p) is not subprocess.CompletedProcess:
        time.sleep(0.05)
    # release lock on tmp file
    fcntl.flock(f, fcntl.LOCK_UN)
    # close tmp file (optional since we're not writing to the file itself)
    f.close()

    if p.stdout:
        logger.info(f"brother_ql stdout: {p.stdout}")
    if p.stderr:
        logger.info(f"brother_ql stderr: {p.stderr}")


def print_thread(logger, file="tmp.png"):
    # create a thread & run print_label in it, so the website can reload after the POST request and not just hang while waiting for the printer process to finish
    thr = Thread(target=print_label, args=(), kwargs={"logger": logger, "file": file})
    thr.start()


def check_file():
    # open tmp file
    f = open(active_write_path, "a+")
    # if there are no permissions errors and the tmp file is writable by us
    if f.writable():
        # acquire an exclusive lock on f (if another process holds a lock, this will block)
        # https://linux.die.net/man/2/flock
        fcntl.flock(f, fcntl.LOCK_EX)
        return f

    return False


if __name__ == "__main__":
    process = list()
    # ewaste("87654", "10/31/2023", "H4TKT0ENQ6X3", "3 Pass", "Ewaste", None)
    # process.append(print_label())
    # ritm(
    #     "123456",
    #     "Ishan Madan",
    #     "Michael Andres-Larsen",
    #     "10/31/2023",
    #     None,
    #     "20 of 20",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )

    # process.append(print_label())
    # macsetup(
    #     "123456",
    #     "DGE-sanity-___",
    #     "H4TKT0ENQ6X3",
    #     "Ishan Madan",
    #     False,
    #     "No",
    #     True
    # )
    # print_label()
    # process.append(print_label())
    # notes_printer(
    #     "123456",
    #     "123.456.789.012",
    #     "QL-570",
    #     "CC FF",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )
    # process.append(print_label())
    # notes(
    #     "123456",
    #     "CC FF FM19 FM194 Proj Vis i want more things from you",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )
    # process.append(print_label())
    # username(".\\admin.imadan1")
    # process.append(print_label())
    # winsetup(
    #     "123456",
    #     "DGE-loaner-___",
    #     "7PCA52G",
    #     "__",
    #     "Ishan Madan",
    #     False,
    #     "No",
    # )
    # process.append(print_label())
    # ritm_generic(
    #     "0012345",
    #     "the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog.",
    # )
    inc_generic(
        "0012345",
        "the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog.",
    )
