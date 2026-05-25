#!/usr/bin/env python3
"""
ITS Depot QR → ServiceNow Kiosk
- Tkinter GUI
- Gmail API (OAuth) send
- 2-phase scan logic with persistent state (Return & Close mode)
- Single-phase "close only" logic that always sends close message

Behavior:
- QR code encodes a URL like https://its-depot.ucsc.edu/RITM0112991
- We extract "RITM0112991" and email ServiceNow with Subject: "Re: RITM0112991"
- Message body is plain text (not HTML rendered). We preserve [code]..[/code] literally.

Modes:
1. "Return & Close messages"
   - 1st scan of ticket -> first message (ready for pickup)
   - 2nd scan of same ticket -> second message (returned/closing), then ticket is cleared
2. "Close message only"
   - Every scan -> second message (returned/closing)
   - Ignores/doesn't update state

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
    Place your Google OAuth client JSON as ./credentials.json
    First run will open browser for Gmail send permission and create ./token.json
"""

import os
import re
import json
import base64
import datetime
from pathlib import Path
from urllib.parse import urlparse
from email.mime.text import MIMEText
import tkinter as tk
from tkinter import ttk

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


##############################################################################
# ========================= CONFIG (EDIT THIS PART) ==========================
##############################################################################

SERVICENOW_ADDR = "ucsc@service-now.com"   # ServiceNow inbound email
LOCATION_TAG    = "Depot Station Scanner"  # optional context tag; unused in body now

# FIRST SCAN MESSAGE (ready for pickup)
FIRST_SCAN_BODY_TEXT = """Hello,

This computer has been imaged and is ready to be returned to you, please schedule a time and place that works best for you [code]<a href="https://appt.link/itsdepot/receivecomputer">here. </a> [/code]

Best,
Barry-6
ITS Depot
"""

# SECOND SCAN MESSAGE (returned / closing out ticket)
SECOND_SCAN_BODY_TEXT = """Hello,

This computer and any associated accessories have been returned to you. As such we are closing out this request and will no longer see updates sent to this ticket. If you have further questions or concerns, please [code]<a href="https://ucsc.service-now.com/its?id=sc_cat_item&sys_id=631379d3db8b1410ef8cf4b5ae96190c">open a new ticket here</a> [/code] and reference this RITM.

Best,
Barry-6
ITS Depot
"""

# Gmail API OAuth scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# OAuth client secret file you already have (Google Cloud "installed" creds)
CLIENT_SECRET_FILE = "credentials.json"

# Token cache (auto-created after first login)
TOKEN_FILE = "token.json"

# Local state file to remember which tickets we've already scanned once
STATE_FILE = "seen.json"

# Pattern for valid ticket IDs after parsing
RITM_PATTERN = re.compile(r"^(RITM\d+)$", re.IGNORECASE)

##############################################################################
# ====================== END CONFIG (STOP EDITING) ===========================
##############################################################################


def get_gmail_service():
    """
    Get an authenticated Gmail API service object.
    Creates/refreshes token.json as needed.
    """
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh silently
            creds.refresh(Request())
        else:
            # First-time interactive login
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE,
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token_out:
            token_out.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def build_email_message(to_addr: str, subject: str, body_text: str) -> dict:
    """
    Build a Gmail API message for PLAIN TEXT email.
    We do NOT want HTML interpretation. We keep [code]...[/code] literal.
    """
    mime_msg = MIMEText(body_text, "plain")
    mime_msg["to"] = to_addr
    mime_msg["subject"] = subject

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_via_gmail(gmail_service, message: dict):
    """
    Send the message via Gmail API as the authorized user.
    """
    gmail_service.users().messages().send(userId="me", body=message).execute()


def load_state() -> set:
    """
    Load which tickets have already been scanned once.
    Returns a set like {"RITM0112991", "RITM0113000", ...}
    """
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        # If corrupt, just reset
        return set()


def save_state(seen: set):
    """
    Save the set of "seen-once" tickets.
    After a second scan, that ticket is removed again.
    """
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(seen)), f)


def extract_ticket_from_url(scanned_text: str) -> str | None:
    """
    Input example from scanner:
        https://its-depot.ucsc.edu/RITM0112991
    We return:
        RITM0112991
    """
    parsed = urlparse(scanned_text.strip())
    # parsed.path might be "/RITM0112991"
    path_bits = [p for p in parsed.path.split("/") if p]  # remove empty elements
    if not path_bits:
        return None

    candidate = path_bits[-1].upper()
    m = RITM_PATTERN.match(candidate)
    if m:
        return m.group(1)
    return None


class ScannerApp:
    """
    Tkinter GUI app for scanning and sending emails.

    Modes:
      - "return_close": two-phase flow using seen.json
          * 1st scan of a ticket sends FIRST_SCAN_BODY_TEXT
          * 2nd scan of the same ticket sends SECOND_SCAN_BODY_TEXT,
            then removes it from seen.json
      - "close_only": single-phase flow
          * every scan sends SECOND_SCAN_BODY_TEXT
          * does NOT touch seen.json
    """

    def __init__(self, root):
        self.root = root
        self.root.title("ITS Depot Ticket Scanner")
        self.root.geometry("650x460")
        self.root.resizable(False, False)

        # Dark-ish theme styling
        self.root.configure(bg="#1e1e1e")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e1e")
        style.configure(
            "TLabel",
            background="#1e1e1e",
            foreground="#ffffff",
            font=("Segoe UI", 11)
        )
        style.configure(
            "Header.TLabel",
            background="#1e1e1e",
            foreground="#ffffff",
            font=("Segoe UI", 16, "bold")
        )
        style.configure("Status.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("TButton", font=("Segoe UI", 11))
        style.configure("TRadiobutton",
                        background="#1e1e1e",
                        foreground="#ffffff",
                        font=("Segoe UI", 11))
        style.map("TRadiobutton",
          background=[("active", "#1e1e1e")],
          foreground=[("active", "#ffffff")])


        # Gmail service + local state
        self.gmail_service = get_gmail_service()
        self.seen_once = load_state()

        # Keep last ticket/phase for "Resend last"
        self.last_ticket = None
        self.last_phase = None  # "first" or "second"

        # Mode variable (tk.StringVar) to switch behavior
        # "return_close"  -> 2-phase return+close flow
        # "close_only"    -> always send second-phase close message
        self.mode_var = tk.StringVar(value="return_close")

        # Layout frames
        top_frame = ttk.Frame(root)
        top_frame.pack(fill="x", padx=16, pady=(16, 8))

        mode_frame = ttk.Frame(root)
        mode_frame.pack(fill="x", padx=16, pady=(0, 8))

        status_frame = ttk.Frame(root)
        status_frame.pack(fill="x", padx=16, pady=8)

        log_frame = ttk.Frame(root)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        # Header / instructions
        self.header_label = ttk.Label(
            top_frame,
            text="Scan ticket QR to notify ServiceNow",
            style="Header.TLabel"
        )
        self.header_label.pack(anchor="w")

        self.sub_label = ttk.Label(
            top_frame,
            text="Mode decides what gets sent when you scan.",
            style="TLabel"
        )
        self.sub_label.pack(anchor="w", pady=(4,0))

        # Radio buttons for mode selection
        # return_close mode description
        self.return_close_radio = ttk.Radiobutton(
            mode_frame,
            text="Return & Close messages  (1st scan = ready for pickup, 2nd scan = returned/closed)",
            value="return_close",
            variable=self.mode_var,
            style="TRadiobutton"
        )
        self.return_close_radio.pack(anchor="w")

        # close_only mode description
        self.close_only_radio = ttk.Radiobutton(
            mode_frame,
            text='Close message only  (every scan sends the "returned/closed" message)',
            value="close_only",
            variable=self.mode_var,
            style="TRadiobutton"
        )
        self.close_only_radio.pack(anchor="w", pady=(4,0))

        # Entry row for scanner input
        entry_row = ttk.Frame(top_frame)
        entry_row.pack(fill="x", pady=(12,0))

        ttk.Label(entry_row, text="Scanned URL:", style="TLabel").pack(side="left")
        self.scan_entry = ttk.Entry(entry_row, font=("Consolas", 11), width=50)
        self.scan_entry.pack(side="left", fill="x", expand=True, padx=(8,8))
        self.scan_entry.bind("<Return>", self.handle_scan_enter)

        self.resend_button = ttk.Button(
            entry_row,
            text="Resend last",
            command=self.resend_last
        )
        self.resend_button.pack(side="left")

        # Status label
        self.status_label = ttk.Label(
            status_frame,
            text="Ready.",
            style="Status.TLabel",
            anchor="center"
        )
        self.status_label.pack(fill="x", pady=(8,4))

        # Log box
        ttk.Label(log_frame, text="Activity Log:", style="TLabel").pack(anchor="w")
        self.log_text = tk.Text(
            log_frame,
            bg="#252526",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=("Consolas", 10),
            state="disabled",
            height=12
        )
        self.log_text.pack(fill="both", expand=True, pady=(4,0))

        # Always focus on the entry so scanner can just fire
        self.scan_entry.focus_set()

    def log(self, msg: str):
        """Append a line to the activity log with timestamp."""
        self.log_text.configure(state="normal")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_status(self, text: str, ok: bool | None):
        """
        Update the big status label color + text.
        ok=True  => success (green)
        ok=False => error (red)
        ok=None  => neutral (white)
        """
        if ok is True:
            fg = "#00ff88"
        elif ok is False:
            fg = "#ff5555"
        else:
            fg = "#ffffff"
        self.status_label.configure(text=text, foreground=fg)

    def _send_ticket_email(self, ritm: str, body_text: str, phase_label: str):
        """
        Internal helper to build and send a message to ServiceNow,
        update logs/status bookkeeping.
        phase_label is just for UI/log messages ("first", "second", etc.)
        """
        subject = f"Re: {ritm}"
        message = build_email_message(
            to_addr=SERVICENOW_ADDR,
            subject=subject,
            body_text=body_text
        )

        send_via_gmail(self.gmail_service, message)

        # Remember last send for "Resend last"
        self.last_ticket = ritm
        self.last_phase = phase_label

    def handle_return_close_mode(self, ritm: str):
        """
        Mode: "return_close"
        - If RITM not seen: send FIRST_SCAN_BODY_TEXT, mark as seen.
        - If RITM already seen: send SECOND_SCAN_BODY_TEXT, clear it.
        """
        is_second_scan = ritm in self.seen_once
        if not is_second_scan:
            # FIRST scan
            try:
                self._send_ticket_email(ritm, FIRST_SCAN_BODY_TEXT, "first")
            except Exception as e:
                self.set_status(f"ERROR sending {ritm}", ok=False)
                self.log(f"!! SEND ERROR [{ritm} / first]: {e}")
                return

            # update state to mark as seen-once
            self.seen_once.add(ritm)
            save_state(self.seen_once)

            self.set_status(f"{ritm}: READY FOR PICKUP sent", ok=True)
            self.log(f"OK FIRST (ready for pickup) sent for {ritm}")
        else:
            # SECOND scan
            try:
                self._send_ticket_email(ritm, SECOND_SCAN_BODY_TEXT, "second")
            except Exception as e:
                self.set_status(f"ERROR sending {ritm}", ok=False)
                self.log(f"!! SEND ERROR [{ritm} / second]: {e}")
                return

            # remove from state so it's reset for future cycles
            if ritm in self.seen_once:
                self.seen_once.remove(ritm)
                save_state(self.seen_once)

            self.set_status(f"{ritm}: RETURN/CLOSED sent", ok=True)
            self.log(f"OK SECOND (returned/closed) sent for {ritm}")

    def handle_close_only_mode(self, ritm: str):
        """
        Mode: "close_only"
        - Every scan sends the SECOND_SCAN_BODY_TEXT.
        - We do NOT read or write seen.json here.
        """
        try:
            self._send_ticket_email(ritm, SECOND_SCAN_BODY_TEXT, "close_only")
        except Exception as e:
            self.set_status(f"ERROR sending {ritm}", ok=False)
            self.log(f"!! SEND ERROR [{ritm} / close_only]: {e}")
            return

        self.set_status(f"{ritm}: CLOSE MESSAGE sent", ok=True)
        self.log(f"OK CLOSE-ONLY (returned/closed) sent for {ritm}")

    def handle_scan_enter(self, event=None):
        """
        Called when scanner 'presses Enter'.
        - Reads scanned URL
        - Extracts ticket number
        - Dispatches based on selected mode
        """
        raw_val = self.scan_entry.get().strip()
        self.scan_entry.delete(0, "end")  # clear ASAP

        if not raw_val:
            return

        self.log(f"Scan received: {raw_val}")
        ritm = extract_ticket_from_url(raw_val)

        if ritm is None:
            self.set_status("Invalid scan", ok=False)
            self.log("!! Could not parse ticket from scan.")
            return

        mode = self.mode_var.get()
        if mode == "close_only":
            # always send the "close" message
            self.handle_close_only_mode(ritm)
        else:
            # default: two-phase return & close behavior
            self.handle_return_close_mode(ritm)

    def resend_last(self):
        """
        Manually resend the last sent message.
        Uses self.last_ticket + self.last_phase to pick which body.
        This respects the mode that was active at the time we sent.
        """
        if not self.last_ticket or not self.last_phase:
            self.set_status("No last ticket to resend", ok=None)
            self.log("Resend skipped (no last ticket).")
            return

        ritm = self.last_ticket
        phase_label = self.last_phase
        self.log(f"Resending last: {ritm} [{phase_label}]")

        # Figure out which body to resend
        if phase_label == "first":
            body_text = FIRST_SCAN_BODY_TEXT
        else:
            # "second" and "close_only" both get the close message
            body_text = SECOND_SCAN_BODY_TEXT

        try:
            self._send_ticket_email(ritm, body_text, phase_label)
        except Exception as e:
            self.set_status(f"ERROR resend {ritm}", ok=False)
            self.log(f"!! RESEND ERROR [{ritm}/{phase_label}]: {e}")
            return

        # GUI feedback
        if phase_label == "first":
            self.set_status(f"Resent {ritm} [READY FOR PICKUP]", ok=True)
            self.log(f"OK resent FIRST for {ritm}")
        elif phase_label == "second":
            self.set_status(f"Resent {ritm} [RETURN/CLOSED]", ok=True)
            self.log(f"OK resent SECOND for {ritm}")
        else:  # close_only
            self.set_status(f"Resent {ritm} [CLOSE ONLY]", ok=True)
            self.log(f"OK resent CLOSE-ONLY for {ritm}")


def main():
    root = tk.Tk()
    app = ScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
