import argparse
import json
import logging
import math
import os
import smtplib
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage

from dotenv import load_dotenv

import cert_pull
import log

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

logger = log.setup_logs("cert_check", log.INFO)

if type(logger) != logging.Logger:
    print("cert_check: Incorrect logger setup")
    exit(1)

# load environment variables (gmail username, gmail password)
load_dotenv()

# ========================= CONFIG ==========================

# start asking for a renewal this many days before the certificate expires
WARN_DAYS = int(os.getenv("cert_warn_days", "30"))
# how often to send the warning again once we are inside that window
WARN_EVERY_DAYS = int(os.getenv("cert_warn_every_days", "1"))
# who gets told about it
NOTIFY = os.getenv("cert_notify", "depot@ucsc.edu")

# when we last warned, kept next to cert_pull's own state
STATE_PATH = os.path.join(cert_pull.STAGING_DIR, "check_state.json")


# -------------------- State helpers --------------------


def load_state():
    try:
        with open(STATE_PATH) as state_file:
            return json.load(state_file)
    # nothing warned about yet
    except FileNotFoundError:
        return {}
    # unreadable or corrupt - treat it as never having warned
    except (OSError, ValueError):
        logger.error(f"cert_check: could not read state: {traceback.format_exc()}")
        return {}


def save_state(state: dict):
    try:
        os.makedirs(cert_pull.STAGING_DIR, exist_ok=True)
        # write a temp file and rename it, same as cert_pull does
        tmp_path = STATE_PATH + ".tmp"
        with open(tmp_path, "w") as state_file:
            json.dump(state, state_file, indent=2, sort_keys=True)
        os.replace(tmp_path, STATE_PATH)
    except OSError:
        logger.error(f"cert_check: could not write state: {traceback.format_exc()}")


# -------------------- Expiry --------------------


def installed_expiry():
    # what nginx is actually serving is the date that matters
    try:
        with open(cert_pull.INSTALLED_CERT) as cert_file:
            return cert_pull.cert_expiry(cert_file.read())
    except OSError:
        logger.error(f"cert_check: could not read {cert_pull.INSTALLED_CERT}")
        return None


def newest_enrollment(pull_state: dict):
    # the latest certificate the mailbox has told us about, installed or not
    newest = None
    for ssl_id, record in pull_state.items():
        expires = record.get("expires")
        if not expires:
            continue
        try:
            when = datetime.fromisoformat(expires)
        # an old state file from before we recorded the expiry properly
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if not newest or when > newest[1]:
            newest = (ssl_id, when, record)
    return newest


def days_word(days: int):
    # "1 day", but "0 days" and "12 days"
    return "day" if abs(days) == 1 else "days"


def days_left(expiry: datetime):
    remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
    # already gone - count whole days elapsed, and say so
    if remaining < 0:
        return -int(-remaining // 86400), True
    # round up, so a certificate that dies tomorrow evening reads "1 day"
    return math.ceil(remaining / 86400), False


# -------------------- The warning mail --------------------


def build_warning(days: int, expired: bool, expiry: datetime, pending, renew_id: str):
    # the line the depot asked for, first thing in the subject & the body
    if expired:
        ago = abs(days)
        when = "today" if ago == 0 else f"{ago} {days_word(ago)} ago"
        headline = f"The certificate for {cert_pull.DOMAIN} expired {when}."
        subject = f"{cert_pull.DOMAIN}: certificate EXPIRED {when}"
    else:
        headline = f"I need a new certificate in {days} {days_word(days)}."
        subject = (
            f"{cert_pull.DOMAIN}: I need a new certificate "
            f"in {days} {days_word(days)}"
        )

    # then what whoever picks this up needs to know
    lines = [
        headline,
        "",
        f"Host:    {cert_pull.DOMAIN}",
        f"Expires: {expiry.strftime('%Y-%m-%d %H:%M')} GMT",
        f"In use:  {cert_pull.INSTALLED_CERT}",
    ]

    # quoting the renew id saves them digging the old mail back up
    if renew_id:
        lines.append(f"Renew id: {renew_id}")

    lines.append("")

    if pending:
        # a certificate did arrive, it just is not the one nginx is serving, so
        # asking for another one would not fix anything
        ssl_id, when, record = pending
        lines += [
            "A newer certificate was already emailed to this account but is NOT",
            "installed, so renewing again will not help until it is sorted out:",
            f"  enrollment {ssl_id}, expires {when.strftime('%Y-%m-%d')}, "
            f"status {record.get('status', '?')}",
            f"  reason: {record.get('detail') or 'unknown'}",
            "",
            "Check logs/cert_pull/latest.log on the server.",
        ]
    else:
        # nothing has arrived, so somebody has to go and renew it
        lines += [
            "No renewal has arrived in the Depot-Cert label yet. Renew the",
            "certificate through the InCommon cert manager; the new one gets",
            "installed automatically once the confirmation mail arrives.",
            "",
            "Keep the renewal on the existing private key, or the install will",
            "stop and ask for the matching key to be put in place by hand.",
        ]

    return subject, "\n".join(lines) + "\n"


def send(subject: str, body: str, dry_run: bool):
    # on a dry run print the mail instead of sending it
    if dry_run:
        logger.info(f"cert_check: dry run, would email {NOTIFY}: {subject}")
        print(f"To: {NOTIFY}\nSubject: {subject}\n\n{body}")
        return True

    # get gmail account's username and password from environment variables
    app_username = os.getenv("app_username")
    app_password = os.getenv("app_password")

    if not app_username or not app_password:
        logger.error("cert_check: app username/password not found")
        return False

    message = EmailMessage()
    message["From"] = app_username
    message["To"] = NOTIFY
    message["Subject"] = subject
    message.set_content(body)

    # the same account we read the certificate mails from sends the warning
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(app_username, app_password)
            smtp.send_message(message)
    except Exception:
        logger.error(f"cert_check: could not send mail: {traceback.format_exc()}")
        return False

    logger.info(f"cert_check: emailed {NOTIFY}: {subject}")
    return True


def due_to_warn(state: dict, days: int, force: bool):
    if force:
        return True

    # never warned about anything before
    last = state.get("last_warned")
    if not last:
        return True

    try:
        when = datetime.fromisoformat(last)
    except ValueError:
        return True

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    # enough time has gone by to say it again
    since = (datetime.now(timezone.utc) - when).total_seconds() / 86400
    if since >= WARN_EVERY_DAYS:
        return True

    # otherwise only speak up if things got worse since the last mail
    return days < state.get("last_days", days)


# -------------------- Core actions --------------------


def run(pull: bool, dry_run: bool, force: bool):
    # look for a renewal before deciding there is not one
    if pull:
        try:
            cert_pull.run_once(False)
        except Exception:
            logger.error(f"cert_check: mailbox check failed: {traceback.format_exc()}")

    state = load_state()
    pull_state = cert_pull.load_state()

    expiry = installed_expiry()
    newest = newest_enrollment(pull_state)

    # with no readable certificate on disk, go by what the mail said
    if not expiry:
        if not newest:
            logger.error("cert_check: no certificate and no enrollment mail to go on")
            return 1
        expiry = newest[1]
        logger.warning("cert_check: using the expiry from the mail, not the disk")

    days, expired = days_left(expiry)
    logger.info(
        f"cert_check: {cert_pull.DOMAIN} expires "
        f"{expiry.strftime('%Y-%m-%d')} ({days} {days_word(days)})"
    )

    # a newer certificate that exists but is not the one being served
    pending = None
    if newest and newest[1] > expiry and newest[2].get("status") != "installed":
        pending = newest

    renew_id = newest[2].get("renew_id", "") if newest else ""

    # still plenty of time - forget any warning we sent for the old certificate
    if days > WARN_DAYS and not force:
        if state.get("last_warned"):
            logger.info("cert_check: certificate renewed, clearing warning state")
        save_state({"expiry": expiry.isoformat(timespec="seconds")})
        return 0

    if not due_to_warn(state, days, force):
        logger.info(
            f"cert_check: already warned within {WARN_EVERY_DAYS} "
            f"{days_word(WARN_EVERY_DAYS)}, not sending again"
        )
        return 0

    subject, body = build_warning(days, expired, expiry, pending, renew_id)

    if not send(subject, body, dry_run):
        return 1

    # a dry run has not really warned anybody, so do not record that it did
    if not dry_run:
        save_state(
            {
                "expiry": expiry.isoformat(timespec="seconds"),
                "last_warned": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "last_days": days,
            }
        )

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Warn the depot when the TLS certificate is close to expiring"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the warning instead of emailing it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="warn even if the certificate is fine or one was just sent",
    )
    parser.add_argument(
        "--no-pull",
        action="store_true",
        help="do not check the mailbox for a new certificate first",
    )
    args = parser.parse_args()

    try:
        exit(run(not args.no_pull, args.dry_run, args.force))
    except Exception:
        logger.error(f"cert_check: {traceback.format_exc()}")
        exit(1)
