#!/bin/bash
# Put the certificate automation in place on the depot server.
#
# Installs the root install helper, the sudoers rule that lets the depot user
# call it, and the two systemd timers (hourly pull, daily expiry warning).
# Safe to re-run; use --uninstall to take it all back out.
#
#   sudo ./cert_setup.sh
#   sudo ./cert_setup.sh --uninstall

set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
HELPER=/usr/local/sbin/depot-cert-install
SUDOERS=/etc/sudoers.d/depot-cert
UNIT_DIR=/etc/systemd/system
UNITS=(depot-cert.service depot-cert.timer depot-cert-check.service depot-cert-check.timer)
TIMERS=(depot-cert.timer depot-cert-check.timer)

CERT="${cert_path:-/etc/ssl/certs/depot-server.crt}"
KEY="${cert_key_path:-/etc/ssl/private/depot-server.key}"

FORCE=0
UNINSTALL=0

problems=0
warnings=0

ok()   { echo "  [ ok ] $*"; }
warn() { echo "  [warn] $*"; warnings=$((warnings + 1)); }
bad()  { echo "  [FAIL] $*"; problems=$((problems + 1)); }
die()  { echo "cert_setup: error: $*" >&2; exit 1; }

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) die "unknown option: $arg" ;;
    esac
done

[ "$(id -u)" -eq 0 ] || die "must run as root (try: sudo $0)"

# the repository is owned by the account the services will run as
RUN_USER="$(stat -c %U "$REPO")"
RUN_GROUP="www-data"
getent group "$RUN_GROUP" >/dev/null 2>&1 || RUN_GROUP="$(id -gn "$RUN_USER")"

# -------------------- Uninstall --------------------

if [ "$UNINSTALL" -eq 1 ]; then
    echo "Removing the certificate automation..."
    for timer in "${TIMERS[@]}"; do
        systemctl disable --now "$timer" 2>/dev/null || true
    done
    for unit in "${UNITS[@]}"; do
        rm -f "$UNIT_DIR/$unit"
    done
    systemctl daemon-reload
    rm -f "$HELPER" "$SUDOERS"
    echo "Removed the timers, the helper and the sudoers rule."
    echo "Left alone: $CERT, $KEY, $REPO/certs, /var/backups/depot-cert"
    exit 0
fi

# -------------------- Preflight checks --------------------

echo "Checking this machine before changing anything..."
echo "  repository: $REPO"
echo "  runs as:    $RUN_USER:$RUN_GROUP"
echo

# this is the depot server, not somebody's laptop
if [ "$RUN_USER" = "root" ]; then
    bad "$REPO is owned by root; it should belong to the service account"
elif ! id "$RUN_USER" >/dev/null 2>&1; then
    bad "user $RUN_USER does not exist"
else
    ok "service account $RUN_USER exists"
fi

if command -v nginx >/dev/null 2>&1; then
    ok "nginx is installed"
else
    bad "nginx is not installed - this does not look like the depot server"
fi

command -v openssl >/dev/null 2>&1 && ok "openssl is installed" || bad "openssl is missing"

for f in cert_pull.py cert_check.py log.py system/depot-cert-install "${UNITS[@]/#/system/}"; do
    [ -f "$REPO/$f" ] || bad "missing $f in the repository"
done
[ "$problems" -eq 0 ] && ok "all source files present"

PY="$REPO/venv/bin/python"
if [ -x "$PY" ]; then
    if sudo -u "$RUN_USER" "$PY" -c 'import dotenv' 2>/dev/null; then
        ok "virtualenv has the required libraries"
    else
        bad "$PY cannot import python-dotenv (pip install -r requirements.txt)"
    fi
else
    bad "no virtualenv at $REPO/venv (python3 -m venv venv)"
fi

if [ -f "$REPO/.env" ]; then
    grep -q '^[[:space:]]*app_username' "$REPO/.env" \
        && grep -q '^[[:space:]]*app_password' "$REPO/.env" \
        && ok "mail credentials found in .env" \
        || bad ".env is missing app_username / app_password"
else
    bad "no .env in $REPO"
fi

[ -f "$CERT" ] && ok "current certificate $CERT" || warn "no certificate yet at $CERT"

if [ -f "$KEY" ]; then
    if openssl pkey -in "$KEY" -noout 2>/dev/null; then
        ok "private key $KEY is readable"
    else
        bad "$KEY is not a readable private key"
    fi
else
    warn "no private key at $KEY - installs will refuse until one is in place"
fi

# the certificate on disk should match the key, or renewals will not install
if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    if [ "$(openssl x509 -in "$CERT" -noout -pubkey 2>/dev/null)" \
       = "$(openssl pkey -in "$KEY" -pubout 2>/dev/null)" ]; then
        ok "certificate and key match"
    else
        warn "the installed certificate does not match $KEY"
    fi
fi

echo
if [ "$problems" -gt 0 ]; then
    if [ "$FORCE" -eq 1 ]; then
        echo "$problems check(s) failed, continuing anyway because of --force."
    else
        echo "$problems check(s) failed. Nothing has been changed."
        echo "Fix the above, or pass --force if you know better."
        exit 1
    fi
fi

# -------------------- Install --------------------

echo "Installing..."

install -o root -g root -m 755 "$REPO/system/depot-cert-install" "$HELPER"
ok "$HELPER"

# build the sudoers rule against this repository's actual path, then let visudo
# check it before it goes anywhere near /etc/sudoers.d
tmp_sudoers="$(mktemp)"
trap 'rm -f "$tmp_sudoers"' EXIT
{
    echo "# Installed by $REPO/cert_setup.sh - do not edit by hand."
    echo "# Lets $RUN_USER install a downloaded certificate and reload nginx."
    echo "$RUN_USER ALL=(root) NOPASSWD: $HELPER $REPO/certs/*"
} > "$tmp_sudoers"

if visudo -cqf "$tmp_sudoers"; then
    install -o root -g root -m 440 "$tmp_sudoers" "$SUDOERS"
    ok "$SUDOERS"
else
    die "generated sudoers rule did not validate, not installing it"
fi

# the units ship with the standard paths; rewrite them for this checkout
for unit in "${UNITS[@]}"; do
    sed -e "s#/home/depot/depot-server#$REPO#g" \
        -e "s#^User=depot\$#User=$RUN_USER#" \
        -e "s#^Group=www-data\$#Group=$RUN_GROUP#" \
        "$REPO/system/$unit" > "$UNIT_DIR/$unit"
    chmod 644 "$UNIT_DIR/$unit"
    ok "$UNIT_DIR/$unit"
done

mkdir -p "$REPO/certs"
chown "$RUN_USER:$RUN_GROUP" "$REPO/certs"
chmod 755 "$REPO/certs"
ok "$REPO/certs"

mkdir -p /var/backups/depot-cert
chmod 700 /var/backups/depot-cert
ok "/var/backups/depot-cert"

systemctl daemon-reload
for timer in "${TIMERS[@]}"; do
    systemctl enable --now "$timer" >/dev/null
    ok "enabled $timer"
done

# -------------------- Check it works --------------------

echo
echo "Verifying..."

# the sudoers rule only allows the helper with a path under certs/, so probe it
# with a file that is not there: getting "no such file" back means sudo let us in
probe="$REPO/certs/.setup-probe"
probe_out="$(sudo -u "$RUN_USER" sudo -n "$HELPER" "$probe" 2>&1 || true)"
if echo "$probe_out" | grep -q "no such file"; then
    ok "$RUN_USER can call the install helper without a password"
elif echo "$probe_out" | grep -qiE "not allowed|password is required|sudo:"; then
    warn "sudo refused the helper for $RUN_USER - check $SUDOERS"
else
    warn "unexpected reply from the helper: $probe_out"
fi

# reads the mailbox and reports the expiry; installs nothing, emails nobody
if sudo -u "$RUN_USER" "$PY" "$REPO/cert_check.py" --no-pull --dry-run >/dev/null 2>&1; then
    ok "cert_check.py runs"
else
    warn "cert_check.py exited non-zero - see $REPO/logs/cert_check/latest.log"
fi

if [ -f "$CERT" ]; then
    echo "  current certificate: $(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)"
fi

echo
systemctl list-timers --no-pager 'depot-cert*' || true

echo
echo "Done."
[ "$warnings" -gt 0 ] && echo "$warnings warning(s) above are worth a look."
cat <<EOF

Still to do by hand:
  1. In the depot Gmail account, add a filter putting the InCommon enrollment
     mails under the "Depot-Cert" label (they come from cert-manager.com).
  2. Watch the first renewal land, or test the plumbing now with:
       sudo -u $RUN_USER $PY $REPO/cert_pull.py --dry-run
       sudo -u $RUN_USER $PY $REPO/cert_check.py --dry-run --force
EOF
