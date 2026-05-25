#!/usr/bin/env python3
"""
Web version of ITS Depot QR → ServiceNow Kiosk
- Flask view will call these helpers
- Gmail API (OAuth) send
- 2-phase scan logic with persistent state (Return & Close mode)
- Single-phase "close only" logic that always sends close message

Files used:
- credentials.json (OAuth client)
- scloser_token.json (Gmail OAuth token cache)
- seen.json (set of tickets seen once)
- scloser_last.json (last ticket+phase sent, used for resend)
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ========================= CONFIG ==========================
SERVICENOW_ADDR = "ucsc@service-now.com"  # ServiceNow inbound email

FIRST_SCAN_BODY_TEXT = """Hello,

This computer has been imaged and is ready to be returned to you, please schedule a time and place that works best for you [code]<a href=\"https://appt.link/itsdepot/receivecomputer\">here. </a> [/code]

Best,
Barry-6
ITS Depot
"""

SECOND_SCAN_BODY_TEXT = """Hello,

This computer and any associated accessories have been returned to you. As such we are closing out this request and will no longer see updates sent to this ticket. If you have further questions or concerns, please [code]<a href=\"https://ucsc.service-now.com/its?id=sc_cat_item&sys_id=631379d3db8b1410ef8cf4b5ae96190c\">open a new ticket here</a> [/code] and reference this RITM.

Best,
Barry-6
ITS Depot
"""

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CLIENT_SECRET_FILE = "credentials.json"
TOKEN_FILE = "scloser_token.json"
STATE_FILE = "seen.json"
LAST_FILE = "scloser_last.json"

RITM_PATTERN = re.compile(r"^(RITM\d+)$", re.IGNORECASE)


@dataclass
class ActionResult:
    ok: bool
    status_text: str
    last_ritm: Optional[str] = None
    last_phase: Optional[str] = None  # "first" | "second" | "close_only"


# -------------------- State helpers --------------------

def load_state() -> set[str]:
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def save_state(seen: set[str]):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(seen)), f)


def load_last() -> Tuple[Optional[str], Optional[str]]:
    if not os.path.exists(LAST_FILE):
        return None, None
    try:
        with open(LAST_FILE, "r") as f:
            data = json.load(f)
        return data.get("ritm"), data.get("phase")
    except Exception:
        return None, None


def save_last(ritm: str, phase: str):
    with open(LAST_FILE, "w") as f:
        json.dump({"ritm": ritm, "phase": phase}, f)


# -------------------- Gmail helpers --------------------

def get_gmail_service():
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            # On servers, avoid attempting to open a browser
            creds = flow.run_local_server(port=0, open_browser=False)
        with open(TOKEN_FILE, "w") as token_out:
            token_out.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def build_email_message(to_addr: str, subject: str, body_text: str) -> dict:
    mime_msg = MIMEText(body_text, "plain")
    mime_msg["to"] = to_addr
    mime_msg["subject"] = subject
    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_via_gmail(gmail_service, message: dict):
    gmail_service.users().messages().send(userId="me", body=message).execute()


def extract_ticket_from_url(scanned_text: str) -> Optional[str]:
    scanned_text = (scanned_text or "").strip().upper()
    # accept raw "RITMxxxx" or URL ending with it
    parts = scanned_text.split("/")
    candidate = parts[-1] if parts else scanned_text
    m = RITM_PATTERN.match(candidate)
    if m:
        return m.group(1)
    return None


# -------------------- Core actions --------------------

def _send_ticket_email(gmail_service, ritm: str, body_text: str, phase_label: str):
    subject = f"Re: {ritm}"
    msg = build_email_message(SERVICENOW_ADDR, subject, body_text)
    send_via_gmail(gmail_service, msg)
    save_last(ritm, phase_label)


def handle_return_close_mode(scanned_url: str) -> ActionResult:
    ritm = extract_ticket_from_url(scanned_url)
    if not ritm:
        return ActionResult(False, "Invalid scan", *load_last())

    seen = load_state()
    gmail = get_gmail_service()

    if ritm not in seen:
        # FIRST scan
        try:
            _send_ticket_email(gmail, ritm, FIRST_SCAN_BODY_TEXT, "first")
        except Exception as e:
            return ActionResult(False, f"ERROR sending {ritm}: {e}", *load_last())
        seen.add(ritm)
        save_state(seen)
        return ActionResult(True, f"{ritm}: READY FOR PICKUP sent", ritm, "first")
    else:
        # SECOND scan
        try:
            _send_ticket_email(gmail, ritm, SECOND_SCAN_BODY_TEXT, "second")
        except Exception as e:
            return ActionResult(False, f"ERROR sending {ritm}: {e}", *load_last())
        if ritm in seen:
            seen.remove(ritm)
            save_state(seen)
        return ActionResult(True, f"{ritm}: RETURN/CLOSED sent", ritm, "second")


def handle_close_only_mode(scanned_url: str) -> ActionResult:
    ritm = extract_ticket_from_url(scanned_url)
    if not ritm:
        return ActionResult(False, "Invalid scan", *load_last())

    gmail = get_gmail_service()
    try:
        _send_ticket_email(gmail, ritm, SECOND_SCAN_BODY_TEXT, "close_only")
    except Exception as e:
        return ActionResult(False, f"ERROR sending {ritm}: {e}", *load_last())
    return ActionResult(True, f"{ritm}: CLOSE MESSAGE sent", ritm, "close_only")


def handle_scan(scanned_url: str, mode: str) -> ActionResult:
    if mode == "close_only":
        return handle_close_only_mode(scanned_url)
    return handle_return_close_mode(scanned_url)


def resend_last() -> ActionResult:
    ritm, phase = load_last()
    if not ritm or not phase:
        return ActionResult(False, "No last ticket to resend", ritm, phase)

    body = FIRST_SCAN_BODY_TEXT if phase == "first" else SECOND_SCAN_BODY_TEXT
    gmail = get_gmail_service()
    try:
        _send_ticket_email(gmail, ritm, body, phase)
    except Exception as e:
        return ActionResult(False, f"ERROR resend {ritm}: {e}", ritm, phase)

    tag = "READY FOR PICKUP" if phase == "first" else ("RETURN/CLOSED" if phase == "second" else "CLOSE ONLY")
    return ActionResult(True, f"Resent {ritm} [{tag}]", ritm, phase)
