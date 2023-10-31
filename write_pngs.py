from PIL import Image, ImageDraw, ImageFont


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


def fit_text(img, text, color, font, x, y, w, h):
    draw = ImageDraw.Draw(img)
    pieces = list(break_fix(text, w, font, draw))
    # height = sum(p[2] for p in pieces)
    # if height > img.size[1]:
    #     raise ValueError("text doesn't fit")
    # y = (img.size[1] - height) // 2
    for t, _ in pieces:
        draw.text((x, y), t, font=font, fill=color)
        y += h


def write_ewaste(ritm, date, serial, erase_type, jamf):
    img = Image.open("png/ewaste.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((900, 120), "%07d" % ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 250)
    imgdraw.text((70, 530), date, (0, 0, 0), font=font)
    imgdraw.text((800, 870), serial, (0, 0, 0), font=font)
    imgdraw.text((1450, 1150), erase_type, (0, 0, 0), font=font)

    x = 715
    y = 1480
    w = 257
    h = 256
    if jamf is True:
        imgdraw.rectangle((x, y, x + w, y + h), "black")
    elif jamf is None:
        imgdraw.line((x, y) + (x + w, y + h), "black", width=20)
        imgdraw.line((x + w, y) + (x, y + h), "black", width=20)

    img.save("tmp.png")


def write_ritm(ritm, names, date, migration, index, returnloc):
    img = Image.open("png/ritm.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((900, 190), "%07d" % ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    imgdraw.text((1220, 1050), date, (0, 0, 0), font=font)

    fit_text(img, names, (0, 0, 0), small_font, 70, 800, 2800, 120)

    if len(index) <= 6:
        imgdraw.text((1760, 1400), index, (0, 0, 0), font=font)
    else:
        imgdraw.text((1825, 1455), index, (0, 0, 0), font=small_font)

    fit_text(img, returnloc, (0, 0, 0), small_font, 70, 1750, 2800, 120)

    x = 970
    y = 1395
    w = 135
    h = 120
    if migration is True:
        imgdraw.rectangle((x, y, x + w, y + h), "black")
    elif migration is None:
        imgdraw.line((x, y) + (x + w, y + h), "black", width=20)
        imgdraw.line((x + w, y) + (x, y + h), "black", width=20)

    img.save("tmp.png")


def write_macsetup(ritm, macname, serial, names, backup, printers):
    img = Image.open("png/macsetup.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((900, 120), "%07d" % ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    imgdraw.text((1050, 500), macname, (0, 0, 0), font=small_font)
    imgdraw.text((620, 700), serial, (0, 0, 0), font=small_font)

    fit_text(img, names, (0, 0, 0), small_font, 100, 1050, 2800, 120)

    if backup is False:
        imgdraw.text((1300, 1300), "No", (0, 0, 0), font=font)

    if printers is False:
        imgdraw.text((1150, 1800), "No", (0, 0, 0), font=font)

    img.save("tmp.png")


def write_notes_printer(ritm, printerip, printermodel, sw, notes):
    img = Image.open("png/notes_printer.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((920, 120), "%07d" % ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    if len(printerip) > 0:
        fit_text(img, printerip, (0, 0, 0), small_font, 90, 650, 2800, 120)
    if len(printermodel) > 0:
        fit_text(img, printermodel, (0, 0, 0), small_font, 90, 1100, 2800, 120)
    if len(sw) > 0:
        fit_text(img, sw, (0, 0, 0), small_font, 90, 1750, 2800, 120)
    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 2320, 2800, 120)

    img.save("tmp.png")


def write_notes(ritm, sw, notes):
    img = Image.open("png/notes.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    ritm_font = ImageFont.truetype("Roboto-Regular.ttf", 350)
    imgdraw.text((920, 120), "%07d" % ritm, (0, 0, 0), font=ritm_font)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)
    small_font = ImageFont.truetype("Roboto-Regular.ttf", 120)

    if len(sw) > 0:
        fit_text(img, sw, (0, 0, 0), small_font, 90, 670, 2800, 120)
    if len(notes) > 0:
        fit_text(img, notes, (0, 0, 0), small_font, 90, 1200, 2800, 120)

    img.save("tmp.png")


def write_username(username):
    img = Image.open("png/username.png", "r").convert("RGB")
    imgdraw = ImageDraw.Draw(img)
    font = ImageFont.truetype("Roboto-Regular.ttf", 230)

    imgdraw.text((530, 500), username, (0, 0, 0), font=font, align="center")

    img.save("tmp.png")


if __name__ == "__main__":
    # write_ewaste(87654, "10/31/2023", "H4TKT0ENQ6X3", "3 Pass", None)
    # write_ritm(
    #     123456,
    #     "Ishan Madan, Cédric Chartier, etc",
    #     "10/31/2023",
    #     None,
    #     "20 of 20",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )
    # write_macritm3(
    #     123456,
    #     "DGE-tobeusedasloanerlaptop-___",
    #     "H4TKT0ENQ6X3",
    #     "Ishan Madan, Cédric Chartier, etc",
    #     False,
    #     False,
    # )
    # write_noteritm(
    #     123456,
    #     "123.456.789.012",
    #     "QL-570",
    #     "CC FF",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )
    # write_noteritm_simple(
    #     123456,
    #     "CC FF",
    #     "WgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWgWg",
    # )
    write_username(".\\admin.imadan1")
