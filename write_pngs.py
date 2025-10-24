import fcntl
import os
import time
from threading import Thread

from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
from brother_ql.raster import BrotherQLRaster
from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.image.pil import PilImage

from history import log_thread as log_history

fonts = {}


def FONT_REG(size):
    if f"reg_{size}" not in fonts:
        fonts[f"reg_{size}"] = ImageFont.truetype("Roboto-Regular.ttf", size)
    return fonts[f"reg_{size}"]


def FONT_ITALIC(size):
    if f"italic_{size}" not in fonts:
        fonts[f"italic_{size}"] = ImageFont.truetype("Roboto-Italic.ttf", size)
    return fonts[f"italic_{size}"]


def FONT_BOLD(size):
    if f"bold_{size}" not in fonts:
        fonts[f"bold_{size}"] = ImageFont.truetype("Roboto-Medium.ttf", size)
    return fonts[f"bold_{size}"]


FONT_RITM = FONT_REG(350)


# find correct textlength to fit in desired size
# derived from https://stackoverflow.com/questions/58041361/break-long-drawn-text-to-multiple-lines-with-pillow
def break_fix(
    text: str, width: int, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw
):
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
def fit_text(
    img: Image.Image,
    text: str,
    color: tuple[int, int, int],
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    w: int,
    h: int,
):
    draw = ImageDraw.Draw(img)
    pieces = list(break_fix(text.strip(), w, font, draw))
    for t, _ in pieces:
        draw.text((x, y), t.strip(), font=font, fill=color)
        y += h

    return len(pieces)


# setup ewaste label
def ewaste(
    ritm: str, date: str, serial: str, erase_type: str, export: str, jamf: bool | None
):
    log_history("ewaste", ritm, date, serial, erase_type, export, jamf)
    img = Image.open("static/ewaste.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)

    # import fonts
    font = FONT_REG(250)

    # draw text for ritm, date, export type, serial, and erase type
    imgdraw.text((900, 120), ritm, (0, 0, 0), font=FONT_RITM)
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
    migration: bool | None,
    index: str,
):
    log_history("ritm", ritm, client_name, requestor_name, date, migration, index)
    img = Image.open("static/ritm.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)

    # import fonts
    ritm_font = FONT_RITM
    font = FONT_REG(230)
    name_font = FONT_ITALIC(200)
    large_name_font = FONT_ITALIC(230)
    small_font = FONT_REG(160)

    # Draw QR top-right (short link, smaller)
    try:
        qr_side = 500
        qr = qrcode.QRCode(border=2, box_size=10)
        qr.add_data(f"https://its-depot.ucsc.edu/ritm{ritm}")
        qr.make(fit=True)
        qr_img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white").get_image()
        qr_img = qr_img.resize((qr_side, qr_side), resample=Image.Resampling.NEAREST)
        img.paste(qr_img, (img.size[0] - 100 - qr_side, 80))
    except Exception:
        pass

    # draw text for ritm, date, requestor name, client name (no additional nudges)
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
    log_history("macsetup", ritm, dept, serial, client_name, backup, printers, localA)
    img = Image.open("static/macsetup.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(350)
    font = FONT_REG(230)
    name_font = FONT_ITALIC(200)
    small_font = FONT_REG(120)

    imgdraw.text((900, 120), ritm, (0, 0, 0), font=ritm_font)

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
    log_history("notes_printer", ritm, printerip, printermodel, sw, notes)
    img = Image.open("static/notes_printer.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(350)
    small_font = FONT_REG(160)

    imgdraw.text((920, 120), ritm, (0, 0, 0), font=ritm_font)

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
    log_history("notes", ritm, sw, notes)
    img = Image.open("static/notes.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(350)
    small_font = FONT_REG(160)

    imgdraw.text((920, 120), ritm, (0, 0, 0), font=ritm_font)

    if len(sw) > 0:
        fit_text(img, sw, (0, 0, 0), small_font, 90, 670, 2800, 160)
    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 1200, 2800, 160)

    img.save("tmp.png")


def username(username: str):
    log_history("username", username)
    img = Image.open("static/username.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    font = FONT_BOLD(230)

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
    log_history(
        "winsetup", ritm, dept, servicetag, domain, client_name, backup, printers
    )
    img = Image.open("static/winsetup.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(350)
    font = FONT_REG(230)
    small_font = FONT_REG(120)
    name_font = FONT_ITALIC(200)
    small_name_font = FONT_ITALIC(120)
    label_font = FONT_BOLD(220)

    imgdraw.text((100, 70), "RITM" + ritm, (0, 0, 0), font=ritm_font)
    imgdraw.text((100, 430), "PC Name:", (0, 0, 0), font=label_font)

    if imgdraw.textlength(dept + "-" + servicetag, font) > 1785:
        imgdraw.text((1100, 500), dept + "-" + servicetag, (0, 0, 0), font=small_font)
    else:
        imgdraw.text((1100, 430), dept + "-" + servicetag, (0, 0, 0), font=font)

    imgdraw.text((100, 680), "Full User's Name:", (0, 0, 0), font=label_font)

    if imgdraw.textlength(client_name, name_font) > 2770:
        imgdraw.text((100, 910), client_name, (0, 0, 0), font=small_name_font)
    else:
        imgdraw.text((100, 910), client_name, (0, 0, 0), font=name_font)

    def rect(x, y):
        box_w = 200
        box_h = 200
        y += 20
        imgdraw.rectangle((x, y, x + box_w, y + box_h), None, "black", 10)

    items = [
        f"BACKUP{' (No)' if not backup else '!!!'}",
        "BIOS",
        "Image",
        "DCU",
        "Encrypt",
        "Default SW",
        "Other SW",
        f"Domain ({domain})",
        "Printers",
    ]

    x_start = 100  # left align
    y_start = 1130  # top of first row
    x_pos = x_start
    y_pos = y_start
    for text in items:
        # if text will overflow (w/ a 50px margin)
        if (
            text == "Printers"
            or x_pos + font.getlength(text) + 20 + 250 > img.size[0] - 100
        ):
            x_pos = x_start  # start back at beginning of line (left)
            y_pos += 270  # go down one line
        imgdraw.text((x_pos, y_pos), text, (0, 0, 0), font=font)  # draw text
        x_pos += font.getlength(text) + 20  # move x_pos after text w/ 20px margin
        rect(x_pos, y_pos)  # draw box
        x_pos += 250  # move x_pos after box w/ some margin

    imgdraw.text((x_pos, y_pos), printers, (0, 0, 0), font=font)

    img.save("tmp.png")


# TODO: shorten both generic labels vertically to only fit the height of the notes


def ritm_generic(ritm: str, notes: str):
    log_history("ritm_generic", ritm, notes)
    img = Image.open("static/ritm_generic.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(330)
    small_font = FONT_REG(160)

    imgdraw.text((860, 25), ritm, (0, 0, 0), font=ritm_font)

    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 520, 2800, 160)

    img.save("tmp.png")


def inc_generic(inc: str, notes: str):
    log_history("inc_generic", "INC" + inc, notes)
    img = Image.open("static/inc_generic.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(330)
    small_font = FONT_REG(160)

    # Add QR code (INC) top-right with short link, smaller
    try:
        qr_side = 500
        qr = qrcode.QRCode(border=2, box_size=10)
        inc_num = inc if str(inc).startswith("INC") else f"INC{inc}"
        qr.add_data(f"https://its-depot.ucsc.edu/{inc_num.lower()}")
        qr.make(fit=True)
        qr_img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white").get_image()
        qr_img = qr_img.resize((qr_side, qr_side), resample=Image.Resampling.NEAREST)
        img.paste(qr_img, (img.size[0] - 100 - qr_side, 80))
    except Exception:
        pass

    imgdraw.text((630, 25), inc, (0, 0, 0), font=ritm_font)

    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 520, 2800, 160)

    img.save("tmp.png")


def kiosk(servicetag: str, date: str, destination: str):
    log_history("kiosk", servicetag, destination)
    img = Image.open("static/kiosk.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)

    ritm_font = FONT_REG(250)
    font = FONT_REG(200)
    name_font = FONT_ITALIC(200)
    st_font = FONT_BOLD(200)

    imgdraw.text((100, 120), f"SCP-{servicetag}-KSK", (0, 0, 0), font=ritm_font)
    imgdraw.text((100, 400), "Service Tag:", (0, 0, 0), font=st_font)
    imgdraw.text((1250, 410), servicetag, (0, 0, 0), font=font)

    def rect(x, y):
        box_w = 200
        box_h = 200
        y += 20
        imgdraw.rectangle((x, y, x + box_w, y + box_h), None, "black", 10)

    items = [
        "BIOS",
        "Image",
        "DeleteAU",
        "DefaultSW",
        "CC",
        "WEPA",
        "Battery",
        "MATLAB",
        "Guard",
        "Kurz",
        "Shortcuts",
        "DCU",
        "Encrypt",
        "BindAU",
        "gpupdate",
    ]

    x_start = 100  # left align
    y_start = 650  # top of first row
    x_pos = x_start
    y_pos = y_start
    for text in items:
        # if text will overflow (w/ a 50px margin)
        if x_pos + font.getlength(text) + 20 + 250 > img.size[0] - 100:
            x_pos = x_start  # start back at beginning of line (left)
            y_pos += 250  # go down one line
        imgdraw.text((x_pos, y_pos), text, (0, 0, 0), font=font)  # draw text
        x_pos += font.getlength(text) + 20  # move x_pos after text w/ 20px margin
        rect(x_pos, y_pos)  # draw box
        x_pos += 250  # move x_pos after box w/ some margin

    imgdraw.text(
        (img.size[0] - 100, y_pos + 40),
        f"Imgd {date}",
        (0, 0, 0),
        font=name_font,
        anchor="rt",
    )

    imgdraw.text((100, y_pos + 40 + 250), destination, (0, 0, 0), font=name_font)

    img.save("tmp.png")


def refurbished(
    name: str,
    cpu: str,
    ram: int | str,
    storage: int | str,
    storage_type: str,
    os: str,
    notes: str,
):
    img = Image.new("RGB", (2900, 1250), color=(255, 255, 255))
    imgdraw = ImageDraw.Draw(img)
    ritm_font = FONT_REG(250)
    font = FONT_REG(200)
    st_font = FONT_BOLD(200)

    name_shift = len(list(break_fix(name, 2800, ritm_font, imgdraw))) * 250
    notes_shift = len(list(break_fix(notes, 2800, font, imgdraw))) * 200

    img = Image.new(
        "RGB",
        (2900, 1250 + name_shift + notes_shift),
        color=(255, 255, 255),
    )
    imgdraw = ImageDraw.Draw(img)

    # imgdraw.text((100, 120), name, (0, 0, 0), font=ritm_font)
    fit_text(img, name, (0, 0, 0), ritm_font, 100, 120, 2800, 250)
    imgdraw.text((100, 150 + name_shift), "CPU:", (0, 0, 0), font=st_font)
    imgdraw.text((950, 160 + name_shift), cpu, (0, 0, 0), font=font)

    imgdraw.text((100, 400 + name_shift), "RAM:", (0, 0, 0), font=st_font)
    imgdraw.text((950, 410 + name_shift), f"{ram}GB RAM", (0, 0, 0), font=font)

    imgdraw.text((100, 650 + name_shift), "Storage:", (0, 0, 0), font=st_font)
    imgdraw.text(
        (950, 660 + name_shift), f"{storage}GB {storage_type}", (0, 0, 0), font=font
    )

    imgdraw.text((100, 900 + name_shift), "OS:", (0, 0, 0), font=st_font)
    imgdraw.text((950, 910 + name_shift), os, (0, 0, 0), font=font)

    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), font, 100, 1150 + name_shift, 2800, 200)

    img.save("tmp.png")


def blank(text: str):
    if text.strip() != "":
        # don't log an empty label
        log_history("blank", text)

    img = Image.new("RGB", (2900, 100), color=(255, 255, 255))

    small_font = FONT_REG(160)

    lines = fit_text(img, text, (0, 0, 0), small_font, 50, 50, 2800, 160)

    if lines > 1:
        height = 100 + lines * 160

        img = Image.new("RGB", (2900, height), color=(255, 255, 255))
        fit_text(img, text, (0, 0, 0), small_font, 50, 50, 2800, 160)
    else:
        img = Image.new("RGB", (2900, 260), color=(255, 255, 255))
        imgdraw = ImageDraw.Draw(img)
        imgdraw.text(
            (2900 / 2, 50),
            text,
            (0, 0, 0),
            font=small_font,
            anchor="ma",
            align="center",
        )

    img.save("tmp.png")


# file path to lock on, the exact path is not important as long as it's identical across processes
active_write_path = "/tmp/active_write_print"

# printer details
try:
    address = open("address").readline().strip()
except:
    address = "file:///dev/usb/lp0"

model = "QL-800"
backend = "linux_kernel"
label_id = "62"


def print_label(logger, file="tmp.png"):
    # attempt to acquire a lock on the tmp file using flock
    f = check_file()
    # if check_file fails for some reason (it shouldn't though), repeat
    while not f:
        time.sleep(0.1)
        f = check_file()

    # temp file to disable printing
    if "NOPRINT" not in os.listdir():
        # call printer library - this is blocking but non-exclusive, so multiple simultaneous calls to this will just cause one to succeed and the rest to error
        qlr = BrotherQLRaster(model)
        qlr.exception_on_warning = True
        instructions = convert(qlr=qlr, images=[file], label=label_id)
        send(
            instructions=instructions,
            printer_identifier=address,
            backend_identifier=backend,
            blocking=True,
        )

    # release lock on tmp file
    fcntl.flock(f, fcntl.LOCK_UN)
    # close tmp file (optional since we're not writing to the file itself)
    f.close()


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

def resnet(
    name: str,
    serial: str,
    ritm: str,
    power_adapter: str,
    service: str,
    card_number: str = "",
    verified_access: bool = False,
    os_version: str = "",
):
    log_history("resnet", name, serial, ritm, power_adapter, service, card_number, verified_access, os_version)

    # Fonts and layout metrics
    label_font = FONT_BOLD(220)
    font = FONT_REG(200)
    # We'll use consistent line heights for wrapping
    LH_TITLE = 220
    LH = 200

    # Precompute line counts using a temporary draw context
    tmp_img = Image.new("RGB", (2900, 1200), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp_img)

    # Content widths: leave room on the right for a QR and margins
    left_margin = 100
    right_margin = 100
    qr_size = 500  # sized down
    content_width = 2900 - left_margin - right_margin - qr_size - 100  # ~1900px

    # Measure wrapped lines for each block
    name_lines = list(break_fix(f"Name: {name}", content_width, font, tmp_draw))
    serial_lines = list(break_fix(f"Serial: {serial}", content_width, font, tmp_draw))
    power_lines = list(break_fix(f"Power Adapter: {power_adapter}", content_width, font, tmp_draw))

    # For Service, reserve width for checkbox on the right of the first line
    box_w = 200
    box_h = 200
    box_margin = 20
    service_wrap_width = max(100, content_width - (box_w + box_margin))
    service_text = f"Service: {service}"
    service_lines = list(break_fix(service_text, service_wrap_width, font, tmp_draw))

    # Optional fields
    card_lines = list(break_fix(f"Card Number: {card_number}", content_width, font, tmp_draw)) if card_number else []
    os_lines = list(break_fix(f"OS Version: {os_version}", content_width, font, tmp_draw)) if os_version else []

    top_margin = 100
    between_blocks = 30
    bottom_margin = 100

    # Calculate total height needed
    total_height = top_margin
    total_height += LH_TITLE  # RITM line
    total_height += len(name_lines) * LH + between_blocks
    total_height += len(serial_lines) * LH + between_blocks
    total_height += len(power_lines) * LH + between_blocks
    # Service block must fit text and the 200px checkbox
    total_height += max(len(service_lines) * LH, box_h + 40) + between_blocks
    if card_lines:
        total_height += len(card_lines) * LH + between_blocks
    if verified_access:
        total_height += max(LH, 100) + between_blocks  # include 100px checkbox
    if os_lines:
        total_height += len(os_lines) * LH + between_blocks
    total_height += bottom_margin

    # Ensure tall enough for QR area
    min_for_qr = 80 + qr_size + 100
    total_height = max(total_height, min_for_qr)

    # Render on final image
    img = Image.new("RGB", (2900, total_height), color=(255, 255, 255))
    imgdraw = ImageDraw.Draw(img)

    # Draw QR top-right (short link, smaller)
    qr_url = f"https://its-depot.ucsc.edu/ritm{ritm}"
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white").get_image()
    qr_img = qr_img.resize((qr_size, qr_size), resample=Image.Resampling.NEAREST)
    qr_x = img.size[0] - right_margin - qr_size
    qr_y = 80
    img.paste(qr_img, (qr_x, qr_y))

    x = left_margin
    y = top_margin

    # RITM (single line)
    imgdraw.text((x, y), f"RITM{ritm}", (0, 0, 0), font=label_font)
    y += LH_TITLE

    # Name
    y += fit_text(img, f"Name: {name}", (0, 0, 0), font, x, y, content_width, LH) * 0  # no-op to keep API similar
    for t, _ in name_lines:
        imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
        y += LH
    y += between_blocks

    # Serial
    for t, _ in serial_lines:
        imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
        y += LH
    y += between_blocks

    # Power Adapter
    for t, _ in power_lines:
        imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
        y += LH
    y += between_blocks

    # Service text with checkbox after first line
    # Draw the service text within the reserved width
    line_y_start = y
    drawn_first_line_width = 0
    for i, (t, w) in enumerate(service_lines):
        imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
        if i == 0:
            drawn_first_line_width = w
        y += LH
    # Place checkbox aligned with the first line
    box_x = x + drawn_first_line_width + box_margin
    box_x = min(box_x, img.size[0] - right_margin - box_w)
    box_y = line_y_start + 20
    imgdraw.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), None, "black", 10)
    # Move y past the taller of text block vs checkbox
    y = max(line_y_start + len(service_lines) * LH, box_y + box_h) + between_blocks

    # Card Number (optional)
    if card_lines:
        for t, _ in card_lines:
            imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
            y += LH
        y += between_blocks

    # Verified Access (optional) - draw label and empty 100x100 box
    if verified_access:
        label = "Verified Access:"
        imgdraw.text((x, y), label, (0, 0, 0), font=font)
        label_w = imgdraw.textlength(label, font=font)
        va_w = 100
        va_h = 100
        # Place box immediately after the label and vertically centered on the line
        va_box_x = x + label_w + 20
        va_box_y = y + (LH - va_h) // 2
        imgdraw.rectangle((va_box_x, va_box_y, va_box_x + va_w, va_box_y + va_h), None, "black", 7)
        # Advance by one line height
        y += LH + between_blocks

    # OS Version (optional)
    if os_lines:
        for t, _ in os_lines:
            imgdraw.text((x, y), t.strip(), fill=(0, 0, 0), font=font)
            y += LH
        y += between_blocks

    img.save("resnet.png")


def resnet_name_ritm(name: str, ritm: str):
    log_history("resnet_name_ritm", name, ritm)

    # Fonts and metrics
    title_font = FONT_BOLD(260)
    font = FONT_REG(220)
    LH_TITLE = 260
    LH = 220
    left_margin = 100
    right_margin = 100

    # Measure wrapped lines for name
    tmp_img = Image.new("RGB", (2900, 300), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp_img)
    name_lines = list(break_fix(f"Name: {name}", 2900 - left_margin - right_margin, font, tmp_draw))

    top_margin = 100
    between = 30
    bottom_margin = 100

    total_height = top_margin + LH_TITLE + between + len(name_lines) * LH + bottom_margin

    img = Image.new("RGB", (2900, total_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    y = top_margin
    draw.text((left_margin, y), f"RITM{ritm}", (0, 0, 0), font=title_font)
    y += LH_TITLE + between

    for t, _ in name_lines:
        draw.text((left_margin, y), t.strip(), (0, 0, 0), font=font)
        y += LH

    img.save("resnet_name_ritm.png")


# Renamed from name_date to food_label

def food_label(name: str, date: str):
    log_history("food_label", name, date)

    name_font = FONT_BOLD(260)
    date_font = FONT_REG(220)
    LH_NAME = 260
    LH_DATE = 220
    left_margin = 100
    right_margin = 100

    # Measure wrapping
    tmp_img = Image.new("RGB", (2900, 300), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp_img)
    name_lines = list(break_fix(f"Name: {name}", 2900 - left_margin - right_margin, name_font, tmp_draw))
    date_lines = list(break_fix(f"Date: {date}", 2900 - left_margin - right_margin, date_font, tmp_draw))

    top_margin = 100
    between = 40
    bottom_margin = 100

    total_height = top_margin + len(name_lines) * LH_NAME + between + len(date_lines) * LH_DATE + bottom_margin

    img = Image.new("RGB", (2900, total_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    y = top_margin
    for t, _ in name_lines:
        draw.text((left_margin, y), t.strip(), (0, 0, 0), font=name_font)
        y += LH_NAME

    y += between

    for t, _ in date_lines:
        draw.text((left_margin, y), t.strip(), (0, 0, 0), font=date_font)
        y += LH_DATE

    img.save("food_label.png")


if __name__ == "__main__":
    # process = list()
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
    #     "0000000", "ITS", "ASDF123", "AU", "Ishan Madan (imadan1)", False, "No"
    # )
    # process.append(print_label())
    # ritm_generic(
    #     "0012345",
    #     "the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog.",
    # )
    # inc_generic(
    #     "0012345",
    #     "the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog. the quick brown fox jumped over the lazy dog.",
    # )

    # from datetime import datetime

    # date = datetime.now().strftime("%m/%d/%Y")
    # kiosk("7ZRCMN3", date)
    # kiosk("                  ", "00/00/0000")
    # kiosk("SRVICETAG", date)
    # kiosk("BCWNLN3", date, "McHenry")

    # refurbished(
    #     "[Computer Name]", "[CPU Name]", "[x]", "[x]", "[Type]", "[OS]", "[Notes]"
    # )
    pass


