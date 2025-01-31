from collections import defaultdict
import json
import math
import os.path
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# If modifying these scopes, delete the file cal_token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

CALENDAR_ID = "cu1q702bdajlgk26ptpq88177d4g00ke@import.calendar.google.com"

START = 0
ONGOING = 1

creds = None
# The file cal_token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists("cal_token.json"):
    creds = Credentials.from_authorized_user_file("cal_token.json", SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("cal_token.json", "w") as token:
        token.write(creds.to_json())


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
    events = []
    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        today = (
            datetime.now()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
        )

        tonight = today + timedelta(days=1)

        events_result = (
            service.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=today.isoformat(),
                timeMax=tonight.isoformat(),
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
                eventTypes="default",
            )
            .execute()
        )
        events = events_result.get("items", [])

        schedule = []

        start = tonight
        end = today

        # start_end_events = []
        events_by_hour = defaultdict(list)

        for event in events:
            if (
                "summary" not in event
                or "start" not in event
                or "dateTime" not in event["start"]
            ):
                continue

            e = dict()
            e["name"] = event["summary"][: event["summary"].find(" (")]
            e["start"] = event["start"]["dateTime"]
            e["end"] = event["end"]["dateTime"]

            dt_start = datetime.fromisoformat(e["start"])
            if dt_start < start:
                start = dt_start

            dt_end = datetime.fromisoformat(e["end"])
            if dt_end > end:
                end = dt_end

            e["start_dec"] = dt_start.hour + dt_start.minute / 60
            e["end_dec"] = dt_end.hour + dt_end.minute / 60
            e["idx"] = 0
            e["split"] = 1
            e["shift"] = True

            # start_end_events.append((e["start_dec"], len(schedule), "start"))
            # start_end_events.append((e["end_dec"], len(schedule), "end"))

            events_by_hour[math.floor(e["start_dec"])].append((len(schedule), START))
            for hr in range(math.floor(e["start_dec"]) + 1, math.ceil(e["end_dec"])):
                events_by_hour[hr].append((len(schedule), ONGOING))

            schedule.append(e)

        start = start.replace(minute=0, second=0, microsecond=0)
        end = end.replace(minute=0, second=0, microsecond=0)

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

        font = ImageFont.truetype("Roboto-Regular.ttf", 20)
        max_hr_width = d.textlength("12AM", font=font)

        def get_y(hr):
            return 10 + (h_img / (end.hour - start.hour + 1)) * (hr - start.hour)

        for hr in range(start.hour, end.hour + 1):
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

        colors = json.load(open("schedule_colors.json"))

        max_event_width = w_img - 30 - max_hr_width

        for event in schedule:
            y = get_y(event["start_dec"])
            h = (h_img / (end.hour - start.hour + 1)) * (
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
        if now.hour >= start.hour and now.hour <= end.hour:
            y = get_y(now.hour + now.minute / 60)
            d.line((10, y, w_img - 10, y), fill=(0, 0, 0), width=4)
            d.circle((w_img - 10, y), 10, fill=(0, 0, 0))

        img.save("static/schedule.png")

        return schedule

    except HttpError as e:
        print(f"An error occurred: {e}")
        return []


if __name__ == "__main__":
    print(json.dumps(get_events(), indent=4))
