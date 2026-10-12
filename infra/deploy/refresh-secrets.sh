#!/bin/bash
# Build /run/herhealth/backend.env from Secrets Manager.
#
#   refresh-secrets.sh                     write the file (deploy.sh calls this)
#   refresh-secrets.sh --restart-on-change also recreate the backend if the
#                                          database URL differs from the one the
#                                          running container was started with
#                                          (the 15-minute systemd timer)
#
# /run is tmpfs: the file never touches disk, never goes into an image, and is
# gone after a reboot. That is fine: containers keep the environment they were
# CREATED with, so `restart: unless-stopped` after a reboot needs no file. The
# file is only read when a container is created (deploy, or the recreate below).
#
# RDS rotates its managed master password (every 7 days by default) and the old
# one stops working at once. Open connections survive; new ones fail until the
# backend is recreated with the new URL. This script is that fix: simplest safe
# option, no extra moving parts.
set -euo pipefail

# HERHEALTH_HOME / HERHEALTH_RUN_DIR exist so this can be exercised in a scratch
# directory with a stubbed aws; on the host they are never set.
HOME_DIR="${HERHEALTH_HOME:-/opt/herhealth}"

# shellcheck disable=SC1091
source "$HOME_DIR/instance.env"

RESTART_ON_CHANGE=0
[ "${1:-}" = "--restart-on-change" ] && RESTART_ON_CHANGE=1

RUN_DIR="${HERHEALTH_RUN_DIR:-/run/herhealth}"
ENV_FILE="$RUN_DIR/backend.env"
COMPOSE=(docker compose -p herhealth --env-file "$HOME_DIR/release.env" -f "$HOME_DIR/compose.prod.yml")

# Before the first deploy there is nothing to refresh and the secrets may still
# be empty. Not an error: the timer must not page anyone for a fresh server.
if [ "$RESTART_ON_CHANGE" = 1 ] && [ ! -f "$HOME_DIR/release.env" ]; then
  echo "no release deployed yet; nothing to refresh"
  exit 0
fi

# The whole point of /run/herhealth is that secrets never touch disk. Refuse to
# write them anywhere else: if /run were ever not a tmpfs this fails loudly
# instead of quietly putting the env file on the root volume.
if [ "$RUN_DIR" = /run/herhealth ]; then
  fstype="$(findmnt -no FSTYPE -T /run 2>/dev/null || true)"
  if [ "$fstype" != "tmpfs" ]; then
    echo "ERROR: /run is '${fstype:-unknown}', not tmpfs; refusing to write secrets to disk." >&2
    exit 1
  fi
fi

# A secret Terraform created but nobody has filled yet has no value at all, and
# the CLI then fails with ResourceNotFoundException. Turn that into one clear
# message and a non-zero exit BEFORE anything is written, so the existing env
# file is never touched and nothing retries on its own (the timer only runs on
# its schedule and, before the first deploy, exits above).
get_secret() {
  local value
  if ! value="$(aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text 2>/dev/null)"     || [ -z "$value" ] || [ "$value" = "None" ]; then
    echo "ERROR: secret '$1' has no value yet. Fill it first (docs/runbooks/aws-deploy.md, \"Filling secrets\"):" >&2
    echo "         aws secretsmanager put-secret-value --secret-id '$1' --secret-string '...'" >&2
    exit 1
  fi
  printf '%s' "$value"
}

# Google sign-in is optional: the backend treats an empty client id as "not
# configured" and the frontend hides the button. So an unfilled secret yields an
# empty value here instead of stopping the deploy.
get_optional_secret() {
  local value
  if ! value="$(aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text 2>/dev/null)" \
    || [ "$value" = "None" ]; then
    value=""
  fi
  printf '%s' "$value"
}

# URL-encode with the stdlib: RDS passwords contain characters (/ @ : ? #) that
# would otherwise end the userinfo part of the URL early.
urlencode() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().rstrip("\n"), safe=""))'
}

db_json="$(get_secret "$DB_SECRET_ARN")"
db_user="$(jq -r .username <<<"$db_json" | urlencode)"
db_pass="$(jq -r .password <<<"$db_json" | urlencode)"
# sslmode=require: RDS serves TLS; refuse to fall back to plaintext.
database_url="postgresql+psycopg://${db_user}:${db_pass}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"

session_secret="$(get_secret "$SECRET_SESSION")"
google_client_id="$(get_optional_secret "$SECRET_GOOGLE")"

install -d -m 700 "$RUN_DIR"
old_hash=""
[ -f "$RUN_DIR/database-url.sha256" ] && old_hash="$(cat "$RUN_DIR/database-url.sha256")"
new_hash="$(printf '%s' "$database_url" | sha256sum | cut -d' ' -f1)"

tmp="$(mktemp -p "$RUN_DIR")"
chmod 600 "$tmp"
{
  echo "HERHEALTH_DATABASE_URL=$database_url"
  echo "HERHEALTH_SESSION_SECRET=$session_secret"
  echo "HERHEALTH_GOOGLE_CLIENT_ID=$google_client_id"
} >"$tmp"
mv "$tmp" "$ENV_FILE"
echo "$new_hash" >"$RUN_DIR/database-url.sha256"
chmod 600 "$RUN_DIR/database-url.sha256"

if [ "$RESTART_ON_CHANGE" = 1 ] && [ -n "$old_hash" ] && [ "$old_hash" != "$new_hash" ]; then
  echo "database credentials changed (RDS rotation): recreating backend"
  "${COMPOSE[@]}" up -d --force-recreate --no-deps backend
fi
