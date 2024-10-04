import os.path
from datetime import date, datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

TYPE_INBOUND_EWASTE = "🔥🗑️🔥"
TYPE_INBOUND_COMPUTER = "📦"
TYPE_UNKNOWN = "⁉️"
TYPE_OUTBOUND = "🖥️✨"
TYPE_EWASTE = "🚚"

TICKET_STRING = "RITM or INC #\n--------------------\n"

creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
        token.write(creds.to_json())


def get_events():
    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        # TODO: pushed back 2 days
        now = (
            datetime.now()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
        ).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
                eventTypes="default",
            )
            .execute()
        )
        events = events_result.get("items", [])

        appointments = []

        current_day = None

        # Prints the start and name of the next 10 events
        for event in events:
            if event["summary"] == "Lunch":
                continue

            e = dict()
            e["time"] = datetime.fromisoformat(str(event["start"]["dateTime"]))
            if e["time"] < datetime.now(timezone.utc) and datetime.fromisoformat(
                str(event["end"]["dateTime"])
            ) > datetime.now(timezone.utc):
                e["now"] = True
            elif datetime.fromisoformat(str(event["end"]["dateTime"])) < datetime.now(
                timezone.utc
            ) or datetime.fromisoformat(str(event["end"]["dateTime"])) > datetime.now(
                timezone.utc
            ) + timedelta(
                days=7
            ):
                continue
            else:
                e["now"] = False

            if e["time"].date() == date.today():
                e["day"] = "Today"
                e["time"] = e["time"].strftime("%I:%M %p")
            elif e["time"].date() == date.today() + timedelta(days=1):
                e["day"] = "Tomorrow"
                e["time"] = e["time"].strftime("%I:%M %p")
            elif e["time"].date() - date.today() < timedelta(days=7):
                e["day"] = e["time"].strftime("%a")
                e["time"] = e["time"].strftime("%I:%M %p")
            else:
                e["day"] = e["time"].strftime("%b %d")
                e["time"] = e["time"].strftime("%I:%M %p")

            if e["day"] == current_day:
                e["day"] = ""
            else:
                current_day = e["day"]

            e["name"] = str(event["summary"]).split(" -- ")[-1]

            # print(event["summary"])
            # print(event["description"])
            event["description"] = str(event["description"]).replace("<br>", "\n")

            if "(Inbound) Receive Computer" in str(event["summary"]) or "(Inbound) Give Computer to Depot" in str(event["summary"]):
                e["dir"] = TYPE_INBOUND_COMPUTER
            elif "(Inbound) Receive e-Waste" in str(event["summary"]):
                e["dir"] = TYPE_INBOUND_EWASTE
            elif "(Outbound)" in str(event["summary"]):
                e["dir"] = TYPE_OUTBOUND
            elif "Coming to Depot (Pickup or Dropoff)" in str(event["summary"]):
                e["loc"] = "🏠 Depot"
                if (
                    "Type of appointment\n--------------------\nComputer Setup (Dropoff)"
                    in str(event["description"])
                ):
                    e["dir"] = TYPE_INBOUND_COMPUTER
                elif (
                    "Type of appointment\n--------------------\nComputer Setup (Pickup)"
                    in str(event["description"])
                ):
                    e["dir"] = TYPE_OUTBOUND
                else:
                    e["dir"] = TYPE_UNKNOWN
            elif "e-waste to receiving" in str(event["summary"]):
                e["name"] = "E-waste to Receiving"
                e["loc"] = "🚚 Barn H"
                e["dir"] = TYPE_EWASTE
            else:
                e["dir"] = TYPE_UNKNOWN

            if "loc" not in e:
                if "depot" in str(event["location"]).lower():
                    e["loc"] = "🏠 Depot"
                else:
                    e["loc"] = "📍 " + str(event["location"]).replace(
                        ", Santa Cruz, CA, USA", ""
                    )

            if TICKET_STRING in str(event["description"]):
                ticket_start = str(event["description"]).index(TICKET_STRING) + len(
                    TICKET_STRING
                )
                ticket_end = str(event["description"]).index("\n", ticket_start)
                e["ticket"] = str(event["description"])[ticket_start:ticket_end]
                if (
                    "RITM" not in e["ticket"]
                    and "INC" not in e["ticket"]
                    and "REQ" not in e["ticket"]
                ):
                    e["ticket"] = "No ticket"
            else:
                e["ticket"] = "No ticket"

            print(e)
            appointments.append(e)

        appointments = appointments
        days = [e["day"] for e in appointments]

        return days, appointments

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []


if __name__ == "__main__":
    print(get_events())
