import json
import math
import os.path
import traceback
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFont

START = 0
ONGOING = 1

path = os.path.abspath(os.path.dirname(__file__))

# The When I Work feed url carries an access token, so it is kept out of here.
# See schedule_feed.json.example for the shape of the file.
FEED_PATH = os.path.join(path, "common/schedule_feed.json")

# Used only if the feed does not name its own timezone.
DEFAULT_TZ = "America/Los_Angeles"


def get_feed_url():
    with open(FEED_PATH) as f:
        return json.load(f)["url"]


def fetch_ics(url):
    request = urllib.request.Request(url, headers={"User-Agent": "depot-server"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def parse_ics(text):
    """Pull the VEVENTs out of an ics feed.

    The When I Work export has no RRULEs, so there is nothing to expand and
    each VEVENT is one shift.
    """
    # Unfold: ics wraps long lines at 75 characters, continuing with a space.
    text = text.replace("\r\n", "\n").replace("\n ", "").replace("\n\t", "")

    calendar = {}
    events = []
    event = None

    for line in text.split("\n"):
        if line == "BEGIN:VEVENT":
            event = {}
            continue
        if line == "END:VEVENT":
            events.append(event)
            event = None
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        params = key.split(";")
        name = params[0]

        target = calendar if event is None else event
        target[name] = value
        for param in params[1:]:
            if param.startswith("TZID="):
                target[f"{name}_tzid"] = param[len("TZID=") :]

    return calendar, events


def ics_datetime(value, tzid, tz):
    """20260903T180000Z, 20260903T180000 or 20260903 -> aware datetime in tz."""
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    elif "T" in value:
        dt = datetime.strptime(value, "%Y%m%dT%H%M%S")
        dt = dt.replace(tzinfo=ZoneInfo(tzid) if tzid else tz)
    else:
        dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=tz)

    return dt.astimezone(tz)


def get_colors():
    """Name -> #rrggbb. Missing or broken file just means uncoloured blocks."""
    try:
        with open(os.path.join(path, "common/schedule_colours.json")) as f:
            return json.load(f)
    except Exception:
        print(f"schedule.get_colors(): {traceback.format_exc()}")
        return {}


def linear_gradient(i, poly, p1, p2, c1, c2):

    # Draw initial polygon, alpha channel only, on an empty canvas of image size
    ii = Image.new("RGB", i.size, (0, 0, 0))
    draw = ImageDraw.Draw(ii, "RGBA")
    draw.polygon(poly, fill=(0, 0, 0, 255), outline=None)

    # Calculate angle between point 1 and 2
    p1 = np.array(p1)
    p2 = np.array(p2)
    angle = np.arctan2(p2[1] - p1[1], p2[0] - p1[0]) / np.pi * 180

    # Rotate and crop shape
    temp = ii.rotate(angle, expand=True)
    temp = temp.crop(temp.getbbox())
    wt, ht = temp.size

    # Create gradient from color 1 to 2 of appropriate size
    gradient = np.linspace(c1, c2, wt, True).astype(np.uint8)
    gradient = np.tile(gradient, [2 * ht, 1, 1])
    gradient = Image.fromarray(gradient)

    # Paste gradient on blank canvas of sufficient size
    temp = Image.new(
        "RGB",
        (max(i.size[0], gradient.size[0]), max(i.size[1], gradient.size[1])),
        (0, 0, 0),
    )
    temp.paste(gradient)
    gradient = temp

    # Rotate and translate gradient appropriately
    x = np.sin(angle * np.pi / 180) * ht
    y = np.cos(angle * np.pi / 180) * ht
    gradient = gradient.rotate(-angle, center=(0, 0), translate=(p1[0] + x, p1[1] - y))

    # Paste gradient on temporary image
    ii.paste(gradient.crop((0, 0, ii.size[0], ii.size[1])), mask=ii)

    # Paste temporary image on actual image
    i.paste(ii, mask=ii)

    return i


def get_events():
    try:
        calendar, raw = parse_ics(fetch_ics(get_feed_url()))
        tz = ZoneInfo(calendar.get("X-WR-TIMEZONE", DEFAULT_TZ))

        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        tonight = today + timedelta(days=1)

        schedule = []

        # Hours of the day the board has to span, as decimals past midnight.
        min_dec = 24.0
        max_dec = 0.0

        events_by_hour = defaultdict(list)

        for event in sorted(raw, key=lambda e: e.get("DTSTART", "")):
            if "SUMMARY" not in event or "DTSTART" not in event or "DTEND" not in event:
                continue

            dt_start = ics_datetime(event["DTSTART"], event.get("DTSTART_tzid"), tz)
            dt_end = ics_datetime(event["DTEND"], event.get("DTEND_tzid"), tz)

            # The board only shows today.
            if dt_end <= today or dt_start >= tonight:
                continue

            # A shift crossing midnight is clipped to the day being drawn.
            dt_start = max(dt_start, today)
            dt_end = min(dt_end, tonight)

            e = dict()

            # "Name (Shift as Depot Technician at Hardware Depot)" -> "Name".
            summary = event["SUMMARY"]
            cut = summary.find(" (")
            e["name"] = summary[:cut] if cut != -1 else summary

            e["start"] = dt_start.isoformat()
            e["end"] = dt_end.isoformat()

            # Measured from midnight, so a shift ending at midnight reads 24.
            e["start_dec"] = (dt_start - today).total_seconds() / 3600
            e["end_dec"] = (dt_end - today).total_seconds() / 3600

            min_dec = min(min_dec, e["start_dec"])
            max_dec = max(max_dec, e["end_dec"])

            e["idx"] = 0
            e["split"] = 1
            e["shift"] = True

            events_by_hour[math.floor(e["start_dec"])].append((len(schedule), START))
            for hr in range(math.floor(e["start_dec"]) + 1, math.ceil(e["end_dec"])):
                events_by_hour[hr].append((len(schedule), ONGOING))

            schedule.append(e)

        if schedule:
            start_hr = math.floor(min_dec)
            end_hr = math.ceil(max_dec)
        else:
            # Nothing on today - draw an empty working day rather than nothing.
            start_hr, end_hr = 8, 18

        # start_end_events.sort(key=lambda x: x[0])
        # idx = start.hour
        # for event in start_end_events:
        #     if event[2] == "start":
        #         events_by_hour[idx].append(event[1])
        #     else:
        #         concurrent -= 1
        #
        #     schedule[event[1]]["concurrent"] = concurrent

        shifted = False
        for hr in events_by_hour:
            starts = [e[0] for e in events_by_hour[hr] if e[1] == START]
            ongoings = [e[0] for e in events_by_hour[hr] if e[1] == ONGOING]

            if len(ongoings) > 0:
                shifted = not shifted
            else:
                shifted = False

            for idx in starts:
                schedule[idx]["idx"] = starts.index(idx)
                schedule[idx]["split"] = len(starts)
                schedule[idx]["shift"] = shifted

        w_img = 475
        h_img = 675
        img = Image.new("RGB", (w_img, h_img), color=(255, 255, 255))
        d = ImageDraw.Draw(img, "RGBA")

        font = ImageFont.truetype(os.path.join(path, "Roboto-Regular.ttf"), 20)
        max_hr_width = d.textlength("12AM", font=font)

        def get_y(hr):
            return 10 + (h_img / (end_hr - start_hr + 1)) * (hr - start_hr)

        for hr in range(start_hr, end_hr + 1):
            ampm = "AM" if hr < 12 else "PM"
            txt_hr = hr % 12
            if txt_hr == 0:
                txt_hr = 12

            d.text(
                (10, get_y(hr)),
                f"{txt_hr}{ampm}",
                font=font,
                fill=(0, 0, 0),
            )
            d.line(
                (
                    10,
                    get_y(hr),
                    w_img - 10,
                    get_y(hr),
                ),
                fill=(160, 160, 160),
                width=2,
            )

        colors = get_colors()

        max_event_width = w_img - 30 - max_hr_width

        for event in schedule:
            y = get_y(event["start_dec"])
            h = (h_img / (end_hr - start_hr + 1)) * (
                event["end_dec"] - event["start_dec"]
            )

            x = (
                max_hr_width
                + 20
                + max_event_width * event["idx"] / event["split"]
                + (
                    5 * ((event["split"] - event["idx"]) / event["split"])
                    if event["shift"]
                    else 0
                )
            )
            w = (max_event_width - (5 if event["shift"] else 0)) / event["split"]

            c = (255, 255, 255)
            if event["name"] in colors:
                c = tuple(
                    int((colors[event["name"]].lstrip("#"))[i : i + 2], 16)
                    for i in (0, 2, 4)
                )
            d.rectangle(
                [
                    (x, y),
                    (x + w, y + h),
                ],
                outline=(0, 0, 0),
                width=2,
                fill=(
                    (255, 255, 255, 127)
                    if event["name"] not in colors
                    else f"{colors[event["name"]]}7F"
                ),
            )
            # img = linear_gradient(
            #     img,
            #     [x, y, x + w, y + h],
            #     [x, y],
            #     [x, y + h],
            #     c + (255,),
            #     c + (127,),
            # )
            # d = ImageDraw.Draw(img, "RGBA")

            d.text(
                (x + 10, y + 10),
                event["name"],
                font=font,
                fill=(0, 0, 0),
            )

        now = datetime.now()
        if now.hour >= start_hr and now.hour <= end_hr:
            y = get_y(now.hour + now.minute / 60)
            d.line((10, y, w_img - 10, y), fill=(0, 0, 0), width=4)
            d.circle((w_img - 10, y), 10, fill=(0, 0, 0))

        img.save(os.path.join(path, "static", "schedule.png"))

        return schedule

    except Exception:
        print(f"schedule.get_events(): {traceback.format_exc()}")
        return []


if __name__ == "__main__":
    print(json.dumps(get_events(), indent=4))
