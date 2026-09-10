import argparse
import email
import imaplib
import json
import logging
import os
import re
import subprocess
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from html import unescape

from dotenv import load_dotenv

import log

# Change directory to current file location
path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)

logger = log.setup_logs("cert_pull", log.INFO)

if type(logger) != logging.Logger:
    print("cert_pull: Incorrect logger setup")
    exit(1)

# load environment variables (gmail username, gmail password)
load_dotenv()

# ========================= CONFIG ==========================

# gmail label (an imap folder) the InCommon enrollment mails are filtered into
MAILBOX = os.getenv("cert_mailbox", "Depot-Cert")
# the only common name we will ever install a certificate for
DOMAIN = os.getenv("cert_domain", "its-depot.ucsc.edu")
# where nginx reads the certificate from (see system/depot-server.conf)
INSTALLED_CERT = os.getenv("cert_path", "/etc/ssl/certs/depot-server.crt")
# root helper that installs it & reloads nginx (see system/depot-cert-install)
INSTALL_HELPER = os.getenv("cert_install_helper", "/usr/local/sbin/depot-cert-install")

# downloaded certificates are staged here before the helper installs them
STAGING_DIR = os.path.join(path, "certs")
# what we have already done with each enrollment, so mails are not re-handled
STATE_PATH = os.path.join(STAGING_DIR, "state.json")

# give up on an enrollment after this many tries - a certificate that does not
# validate will never start validating, and we do not want to fetch it forever
MAX_ATTEMPTS = 3

# only ever download from the sectigo/incommon cert manager, over https
DOWNLOAD_HOST = "cert-manager.com"
# "Certificate (w/ chain), PEM encoded" - leaf first, then the issuing chain,
# which is the order nginx wants for ssl_certificate
CHAIN_FORMAT = "x509"

# the download links, ex:
# https://cert-manager.com/customer/InCommon/ssl?action=download&sslId=19172807&format=x509
DOWNLOAD_RE = re.compile(
    r"https://cert-manager\.com/[^\s\"'<>]*?[?&]sslId=(\d+)[^\s\"'<>]*", re.I
)
# one certificate out of a PEM bundle
PEM_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.DOTALL
)
# "Common Name :  its-depot.ucsc.edu"
COMMON_NAME_RE = re.compile(r"Common\s+Name\s*:\s*([A-Za-z0-9.\-*]+)", re.I)
# "Expires :      11/08/2026 23:59 GMT"
EXPIRES_RE = re.compile(
    r"Expires\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", re.I
)
# "Your renew id: ujejB49NoSOJ2mQ67uCG" - worth quoting when asking for a renewal
RENEW_ID_RE = re.compile(r"renew\s+id\s*:\s*([A-Za-z0-9._-]+)", re.I)


# -------------------- State helpers --------------------


def load_state():
    try:
        with open(STATE_PATH) as state_file:
            return json.load(state_file)
    # no state file yet on the first ever run
    except FileNotFoundError:
        return {}
    # unreadable or corrupt - start over rather than crash the timer
    except (OSError, ValueError):
        logger.error(f"cert_pull: could not read state: {traceback.format_exc()}")
        return {}


def save_state(state: dict):
    try:
        os.makedirs(STAGING_DIR, exist_ok=True)
        # write a temp file and rename it, so an interrupted run cannot leave a
        # half written state file behind
        tmp_path = STATE_PATH + ".tmp"
        with open(tmp_path, "w") as state_file:
            json.dump(state, state_file, indent=2, sort_keys=True)
        os.replace(tmp_path, STATE_PATH)
    except OSError:
        logger.error(f"cert_pull: could not write state: {traceback.format_exc()}")


# -------------------- Mail parsing --------------------


def html_to_text(body: str):
    body = body.replace("\r", "")
    # pull the target out of every link first - in the html version of the mail
    # the download urls only exist as href attributes, and stripping the tags
    # would throw them away
    body = re.sub(
        r"(?is)<a\b[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>", r"\2 \1 ", body
    )
    # turn line breaks & paragraph ends into newlines, then drop the rest of the tags
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</p>", "\n", body)
    body = re.sub(r"(?i)<[^>]+>", "", body)
    body = unescape(body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def get_body(email_message):
    plain = ""
    html = ""

    # iterate over the email, keeping the first text part of each kind
    for part in email_message.walk():
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        # decode using the charset the mail declares, if we know it
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")

        if content_type == "text/plain" and not plain:
            plain = text
        elif content_type == "text/html" and not html:
            html = text

    # the plain text part is the easy one, fall back to stripping the html
    if plain:
        return plain
    if html:
        return html_to_text(html)
    return ""


def get_download_url(body: str):
    match = DOWNLOAD_RE.search(body)
    if not match:
        return None, None

    ssl_id = match.group(1)
    # everything before the query string, ex ".../customer/InCommon/ssl"
    base = match.group(0).split("?")[0]

    # never follow a link out of a mail to somewhere unexpected
    if not base.lower().startswith(f"https://{DOWNLOAD_HOST}/"):
        logger.error(f"cert_pull: refusing download from unexpected host: {base}")
        return None, None

    # rebuild the url ourselves so the format is always the chain one, no matter
    # which of the links in the mail happened to match first
    return ssl_id, f"{base}?action=download&sslId={ssl_id}&format={CHAIN_FORMAT}"


def parse_mail_expiry(body: str):
    # the mail states the expiry as "Expires : 11/08/2026 23:59 GMT"
    match = EXPIRES_RE.search(body)
    if not match:
        return None

    month, day, year, hour, minute = match.groups()
    try:
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            tzinfo=timezone.utc,
        )
    # a date the mail states but the calendar does not have
    except ValueError:
        return None


# -------------------- Certificate helpers --------------------


def openssl(args: list[str], stdin: str | None = None):
    # run an openssl subcommand, returning (worked, output)
    try:
        result = subprocess.run(
            ["openssl"] + args,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        logger.error(f"cert_pull: openssl {args[0]} failed: {traceback.format_exc()}")
        return False, ""

    # on failure hand back the error text instead of the (empty) output
    if result.returncode != 0:
        return False, result.stderr.strip()

    return True, result.stdout.strip()


def parse_cert_date(value: str):
    # turn openssl's "notAfter=Nov  8 23:59:00 2026 GMT" into a datetime
    value = value.split("=", 1)[-1].strip()
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def get_field(pem: str, args: list[str]):
    # read one field off a certificate, ex get_field(leaf, ["-enddate"])
    ok, out = openssl(["x509", "-noout"] + args, stdin=pem)
    if not ok:
        logger.error(f"cert_pull: openssl x509 {' '.join(args)} failed: {out}")
        return ""
    return out


def get_fingerprint(pem: str):
    ok, out = openssl(["x509", "-noout", "-fingerprint", "-sha256"], stdin=pem)
    if not ok:
        return ""
    # openssl prints "SHA256 Fingerprint=AA:BB:.." - keep the hex
    return out.split("=", 1)[-1].strip()


def cert_expiry(pem_text: str):
    # notAfter of the leaf certificate in a PEM bundle
    certs = PEM_RE.findall(pem_text)
    if not certs:
        return None
    return parse_cert_date(get_field(certs[0], ["-enddate"]))


def names_match(pem: str):
    # the certificate is ours if the domain is the common name or one of the
    # subject alternative names, wildcards included
    subject = get_field(pem, ["-subject"])
    sans = get_field(pem, ["-ext", "subjectAltName"])
    haystack = f"{subject}\n{sans}".lower()

    candidates = [DOMAIN.lower()]
    # its-depot.ucsc.edu is also covered by a *.ucsc.edu certificate
    parent = DOMAIN.split(".", 1)
    if len(parent) == 2:
        candidates.append(f"*.{parent[1]}".lower())

    return any(candidate in haystack for candidate in candidates)


def validate(pem_text: str):
    # everything an unprivileged user can check; the private key match and the
    # nginx config test happen later, in the root install helper
    certs = PEM_RE.findall(pem_text)

    if not certs:
        return False, "no PEM certificate in download"

    # without the intermediates, clients cannot build a chain to the root
    if len(certs) < 2:
        return False, f"expected leaf + chain, got {len(certs)} certificate(s)"

    leaf = certs[0]

    # openssl has to be able to read it at all
    ok, _ = openssl(["x509", "-noout"], stdin=leaf)
    if not ok:
        return False, "leaf certificate is not parseable"

    # and it has to be for this site
    if not names_match(leaf):
        subject = get_field(leaf, ["-subject"])
        return False, f"certificate is not for {DOMAIN} ({subject})"

    # -checkend 0 exits non-zero once the certificate is past notAfter
    ok, _ = openssl(["x509", "-noout", "-checkend", "0"], stdin=leaf)
    if not ok:
        return False, f"certificate already expired ({get_field(leaf, ['-enddate'])})"

    # a post dated certificate would be rejected by every browser until it starts
    start = get_field(leaf, ["-startdate"])
    not_before = parse_cert_date(start)
    if not not_before:
        logger.warning(f"cert_pull: could not parse notBefore ({start})")
    elif not_before > datetime.now(timezone.utc):
        return False, f"certificate is not valid until {start}"

    # nginx wants the chain in order, each certificate signed by the next one
    issuer = get_field(leaf, ["-issuer"]).replace("issuer=", "").strip()
    next_subject = get_field(certs[1], ["-subject"]).replace("subject=", "").strip()
    if issuer != next_subject:
        return (
            False,
            f"chain out of order: leaf issued by '{issuer}', next is '{next_subject}'",
        )

    return True, ""


# -------------------- Download & install --------------------


def download(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "depot-server"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def already_installed(pem_text: str):
    # read whatever nginx is serving right now
    try:
        with open(INSTALLED_CERT) as cert_file:
            current = cert_file.read()
    # no certificate in place yet, so this one is certainly new
    except OSError:
        return False

    new_leaf = PEM_RE.findall(pem_text)
    old_leaf = PEM_RE.findall(current)
    if not new_leaf or not old_leaf:
        return False

    # same leaf fingerprint means there is nothing to do
    return get_fingerprint(new_leaf[0]) == get_fingerprint(old_leaf[0])


def install(staged_path: str, dry_run: bool):
    if dry_run:
        logger.info(f"cert_pull: dry run, not installing {staged_path}")
        return True

    # the helper is the only thing here that runs as root
    try:
        result = subprocess.run(
            ["sudo", "-n", INSTALL_HELPER, staged_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        logger.error(f"cert_pull: install helper failed: {traceback.format_exc()}")
        return False

    # keep what the helper said in our own log, so there is one place to look
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip():
            logger.info(f"cert_pull: install: {line.strip()}")

    return result.returncode == 0


# -------------------- Core actions --------------------


def handle_message(mail, num: bytes, state: dict, dry_run: bool):
    # returns True once the mail is dealt with & can be marked read
    _, data = mail.fetch(num, "(RFC822)")
    _, bytes_data = data[0]  # type: ignore

    # parse the string of bytes into a readable email message
    email_message = email.message_from_bytes(bytes(bytes_data))
    subject = email_message.get("Subject", "")
    body = get_body(email_message)

    if not body:
        logger.warning(f"cert_pull: no readable body in message ({subject})")
        return False

    ssl_id, url = get_download_url(body)
    if not ssl_id or not url:
        logger.warning(
            f"cert_pull: no certificate download link in message ({subject})"
        )
        return False

    # an enrollment we have already finished with, ex a mail marked unread again
    record = state.get(ssl_id, {})
    status = record.get("status")

    if status in ("installed", "current", "failed"):
        logger.info(f"cert_pull: enrollment {ssl_id} already handled ({status})")
        return True

    attempts = record.get("attempts", 0) + 1

    # the rest of the details block, for the log & for the expiry warnings
    common_name = COMMON_NAME_RE.search(body)
    common_name = common_name.group(1) if common_name else "?"

    renew_id = RENEW_ID_RE.search(body)
    renew_id = renew_id.group(1) if renew_id else ""

    mail_expiry = parse_mail_expiry(body)
    mail_expiry = mail_expiry.isoformat(timespec="seconds") if mail_expiry else ""

    logger.info(
        f"cert_pull: enrollment {ssl_id} for {common_name}, "
        f"expires {mail_expiry or '?'}, attempt {attempts}"
    )

    # write down how this attempt went before returning anywhere below
    def remember(new_status: str, detail: str = "", expires: str = ""):
        state[ssl_id] = {
            "status": new_status,
            "attempts": attempts,
            "common_name": common_name,
            "renew_id": renew_id,
            # off the certificate once installed, off the mail before that
            "expires": expires or mail_expiry,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": detail,
        }
        save_state(state)

    try:
        pem_text = download(url)
    except Exception:
        # network trouble is temporary: leave the mail unread and try again later
        logger.error(
            f"cert_pull: download failed for {ssl_id}: {traceback.format_exc()}"
        )
        remember("pending", "download failed")
        return False

    # a certificate that does not check out never goes near nginx
    valid, reason = validate(pem_text)
    if not valid:
        logger.error(f"cert_pull: enrollment {ssl_id} rejected: {reason}")
        # out of tries - stop fetching it, but say so loudly in the log
        if attempts >= MAX_ATTEMPTS:
            remember("failed", reason)
            return True
        remember("pending", reason)
        return False

    # nothing to do if this is the certificate already in place
    if already_installed(pem_text):
        logger.info(
            f"cert_pull: enrollment {ssl_id} is already the installed certificate"
        )
        remember("current", "already installed")
        return True

    # stage it where the sudoers rule allows the helper to read it from
    os.makedirs(STAGING_DIR, exist_ok=True)
    staged_path = os.path.join(STAGING_DIR, f"{DOMAIN}-{ssl_id}.crt")
    with open(staged_path, "w") as staged:
        staged.write(pem_text if pem_text.endswith("\n") else pem_text + "\n")
    os.chmod(staged_path, 0o644)

    # expires is the printable date for the log, expiry the one we store
    expires = get_field(PEM_RE.findall(pem_text)[0], ["-enddate"])
    expiry = cert_expiry(pem_text)
    expiry = expiry.isoformat(timespec="seconds") if expiry else ""
    logger.info(f"cert_pull: staged {staged_path} ({expires})")

    if not install(staged_path, dry_run):
        logger.error(f"cert_pull: install failed for {ssl_id}, nginx left unchanged")
        if attempts >= MAX_ATTEMPTS:
            remember("failed", "install helper failed")
            return True
        remember("pending", "install helper failed")
        return False

    # on a dry run nothing was installed, so the mail stays unread
    if dry_run:
        remember("pending", "dry run")
        return False

    logger.info(f"cert_pull: installed certificate for {common_name} ({expires})")
    remember("installed", expires, expiry)
    return True


def run_once(dry_run: bool):
    # get gmail account's username and password from environment variables
    app_username = os.getenv("app_username")
    app_password = os.getenv("app_password")

    if not app_username or not app_password:
        logger.error("cert_pull: app username/password not found")
        return

    state = load_state()

    # login to email using imap
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(app_username, app_password)

        # get the certificate mailbox
        status, _ = mail.select(MAILBOX, False)
        if status != "OK":
            logger.error(f"cert_pull: could not open mailbox '{MAILBOX}'")
            return

        # get unread certificate emails
        _, selected_mails = mail.search(None, "(UNSEEN)")
        messages = selected_mails[0].split()

        if not messages:
            return

        logger.info(f"cert_pull: {len(messages)} unread certificate mail(s)")

        # iterate over selected emails
        for num in messages:
            try:
                done = handle_message(mail, num, state, dry_run)
            except Exception:
                logger.error(f"cert_pull: {traceback.format_exc()}")
                done = False

            # only mark the email as read once we are finished with it, so a
            # failure gets retried and stays visible in the label meanwhile
            if done:
                mail.store(num, "+FLAGS", "\\Seen")
    finally:
        # log out even if something above threw
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install InCommon certificates mailed to the depot account"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="download and validate, but do not touch nginx",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="keep polling instead of exiting after one pass",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="seconds between polls when using --watch (default: 3600)",
    )
    args = parser.parse_args()

    logger.info("cert_pull: Starting...")

    while True:
        try:
            run_once(args.dry_run)
        except Exception:
            logger.error(f"cert_pull: {traceback.format_exc()}")

        # a single pass by default, since the systemd timer does the repeating
        if not args.watch:
            break

        time.sleep(args.interval)
