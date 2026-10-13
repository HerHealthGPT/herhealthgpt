#!/bin/bash
# Deploy one release to this host. Run by GitHub Actions through SSM Run Command:
#
#   /opt/herhealth/deploy.sh <git-sha>
#
# Order, and why:
#   1. self-update          this file is replaced from S3 so deploy logic ships
#                           with the release instead of being frozen at first boot
#                           (on a brand-new host the file is bootstrap-deploy.sh,
#                           which fetches this one and hands over)
#   2. stage release files  compose.prod.yml and the Caddyfile go to next/, NOT
#                           over the live ones: nothing that can still fail may
#                           touch what is running
#   3. preflight            database reachable, disk, ECR login, pull, Caddyfile
#                           validation, migrations -- all against the staged files
#   4. switch               snapshot the live files to previous/, install the
#                           staged ones, `compose up --wait`, reload Caddy
#   5. health check THROUGH CADDY (real TLS, real routing), and if it fails,
#   6. ROLL BACK to the previous tag AND the previous compose/Caddy files
#      automatically -- this replaces the ECS deployment circuit breaker
#   7. prune                keep only the current and previous images
#
# ROLLBACK LIMIT: step 6 restores the previous IMAGES and FILES, not the previous
# database schema. A migration that is not backward compatible with the previous
# release will leave the old code running against the new schema. Migrations
# must be written expand/contract (docs/runbooks/aws-deploy.md, "Rollback").
#
# Re-running after a failed FIRST deploy is safe: every step is idempotent. Do
# not LOOP on it, though -- Let's Encrypt limits repeated failed validations
# (see the runbook, "First deploy").
set -euo pipefail

SHA="${1:?usage: deploy.sh <git-sha>}"
[[ "$SHA" =~ ^[0-9a-f]{7,64}$ ]] || { echo "refusing: '$SHA' is not a git sha" >&2; exit 2; }

# HERHEALTH_HOME and HERHEALTH_LOCK_FILE exist so the logic can be exercised in a
# scratch directory with stubbed aws/docker/curl; on the host they are never set.
HOME_DIR="${HERHEALTH_HOME:-/opt/herhealth}"

# shellcheck disable=SC1091
source "$HOME_DIR/instance.env"
cd "$HOME_DIR"

# One deploy at a time.
exec 9>"${HERHEALTH_LOCK_FILE:-/var/lock/herhealth-deploy.lock}"
flock -n 9 || { echo "another deploy is already running" >&2; exit 1; }

S3="s3://${ARTIFACTS_BUCKET}/deploy/${SHA}"
STAGE="$HOME_DIR/next"
MIN_FREE_GB=15 # room for two image pulls and the previous release

say() { echo "[deploy $(date -u +%H:%M:%S)] $*"; }

# --- 1. self-update ------------------------------------------------------------
if [ -z "${HERHEALTH_DEPLOY_REEXEC:-}" ]; then
  aws s3 cp "$S3/deploy.sh" deploy.sh.new --only-show-errors
  if ! cmp -s deploy.sh.new deploy.sh; then
    say "deploy.sh changed in this release; re-executing the new copy"
    chmod 755 deploy.sh.new
    mv deploy.sh.new deploy.sh
    HERHEALTH_DEPLOY_REEXEC=1 exec "$HOME_DIR/deploy.sh" "$SHA"
  fi
  rm -f deploy.sh.new
fi

# --- 2. stage release files -------------------------------------------------------
say "staging release files for $SHA"
rm -rf "$STAGE"
install -d "$STAGE/caddy"
aws s3 cp "$S3/compose.prod.yml" "$STAGE/compose.prod.yml" --only-show-errors
aws s3 cp "$S3/Caddyfile" "$STAGE/caddy/Caddyfile" --only-show-errors
for f in refresh-secrets.sh caddy-data.sh; do
  aws s3 cp "$S3/$f" "$f.new" --only-show-errors
  chmod 755 "$f.new"
  mv "$f.new" "$f"
done

PREV_TAG=""
if [ -f release.env ]; then
  PREV_TAG="$(sed -n 's/^TAG=//p' release.env)"
fi

write_release_env() { # <tag> <file>
  {
    echo "ECR_REGISTRY=${ECR_REGISTRY}"
    echo "TAG=$1"
    echo "DOMAIN=${DOMAIN}"
    echo "AWS_REGION=${AWS_REGION}"
    echo "ACME_EMAIL=${ACME_EMAIL}"
    # local.env is for hand-set overrides, e.g. ACME_CA=<Let's Encrypt staging>
    # while rehearsing a recreate (docs/runbooks/aws-deploy.md).
    if [ -f "$HOME_DIR/local.env" ]; then cat "$HOME_DIR/local.env"; fi
  } >"$2"
}

# dc <compose-file> <env-file> <compose args...>
dc() {
  local file="$1" envf="$2"; shift 2
  docker compose -p herhealth --env-file "$envf" -f "$file" "$@"
}
LIVE="$HOME_DIR/compose.prod.yml"

prune_images() { # <keep-tag> [<keep-tag>]
  docker image prune -f >/dev/null || true
  docker images --format '{{.Repository}} {{.Tag}}' | while read -r repo tag; do
    case "$repo" in "${ECR_REGISTRY}"/herhealth-*) ;; *) continue ;; esac
    if [ "$tag" != "${1:-}" ] && [ "$tag" != "${2:-}" ]; then
      docker image rm "$repo:$tag" >/dev/null 2>&1 || true
    fi
  done
}

free_gb() { df --output=avail -BG / | tail -1 | tr -dc '0-9'; }

# --- 3. preflight (nothing here touches the running release) ------------------------

# A stopped RDS makes /health fail, which would be read as a bad release and
# trigger a pointless rollback. Fail early and say why instead.
say "checking the database is reachable at ${DB_HOST}:${DB_PORT}"
if ! timeout 5 bash -c "exec 3<>/dev/tcp/${DB_HOST}/${DB_PORT}" 2>/dev/null; then
  echo "ERROR: cannot reach the database at ${DB_HOST}:${DB_PORT}. Is RDS stopped? (docs/runbooks/aws-deploy.md, \"Stop between sessions\")" >&2
  echo "       Start it, wait for 'available', and re-run. Nothing was changed." >&2
  exit 1
fi

# Always drop images older than the running release first, so at most the
# running release and the new one are on disk during the pull.
prune_images "$PREV_TAG" "$SHA"
if [ "$(free_gb)" -lt "$MIN_FREE_GB" ]; then
  echo "ERROR: only $(free_gb) GB free after pruning, need $MIN_FREE_GB. See docs/runbooks/aws-deploy.md, \"Disk space\"." >&2
  df -h / >&2
  exit 1
fi

say "ECR login"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null

write_release_env "$SHA" release.env.new

say "refreshing secrets"
HERHEALTH_RELEASE_SHA="$SHA" ./refresh-secrets.sh

say "pulling images (a failure here leaves the running release untouched)"
dc "$STAGE/compose.prod.yml" release.env.new pull

# A bad Caddyfile would otherwise only be noticed when `caddy reload` refuses it
# after the switch. Validate it with the image that will run it.
say "validating the Caddyfile"
dc "$STAGE/compose.prod.yml" release.env.new run --rm --no-deps --entrypoint caddy caddy \
  validate --config /etc/caddy/Caddyfile

# Run from services/backend: alembic.ini's script_location is relative to the
# working directory. A failure here leaves the old services running.
say "alembic upgrade head"
dc "$STAGE/compose.prod.yml" release.env.new run --rm --no-deps -w /app/services/backend backend \
  alembic upgrade head

# --- 4. switch -----------------------------------------------------------------------
# Keep what is live so a rollback restores the files as well as the images.
rm -rf previous
install -d previous/caddy
if [ -f compose.prod.yml ]; then cp -p compose.prod.yml previous/compose.prod.yml; fi
if [ -f caddy/Caddyfile ]; then cp -p caddy/Caddyfile previous/caddy/Caddyfile; fi

install_files() { # <source-dir>
  install -d caddy
  cp "$1/compose.prod.yml" compose.prod.yml.new && mv compose.prod.yml.new compose.prod.yml
  # Caddy mounts the DIRECTORY ./caddy, not the file: mv replaces the file's
  # inode, and a single-file bind mount keeps pointing at the old one, so
  # `caddy reload` would silently re-read the old Caddyfile.
  cp "$1/caddy/Caddyfile" caddy/Caddyfile.new && mv caddy/Caddyfile.new caddy/Caddyfile
}

install_files "$STAGE"
mv release.env.new release.env
say "starting release $SHA (previous: ${PREV_TAG:-none})"

reload_caddy() {
  dc "$LIVE" release.env exec -T caddy caddy reload --config /etc/caddy/Caddyfile --force >/dev/null 2>&1 \
    || dc "$LIVE" release.env up -d --force-recreate --no-deps caddy >/dev/null 2>&1 || true
}

# With the ACME staging CA selected in local.env, Caddy serves a certificate no
# trust store knows, so verification is skipped -- and only then. Production
# certificates are always verified.
CURL_TLS=()
if [ -f local.env ]; then
  acme_ca="$(sed -n 's/^ACME_CA=//p' local.env | tail -1)"
  if [ -n "$acme_ca" ] && [ "$acme_ca" != "https://acme-v02.api.letsencrypt.org/directory" ]; then
    CURL_TLS=(-k)
    say "ACME_CA is overridden ($acme_ca): health checks will NOT verify the certificate. Remove it from local.env before real use."
  fi
fi

healthy_through_caddy() {
  for _ in $(seq 1 36); do # ~3 minutes: first-ever certificate issuance is slow
    if curl -fsS "${CURL_TLS[@]}" --max-time 5 --resolve "api.${DOMAIN}:443:127.0.0.1" "https://api.${DOMAIN}/health" >/dev/null 2>&1 \
      && curl -fsS "${CURL_TLS[@]}" --max-time 10 -o /dev/null --resolve "${DOMAIN}:443:127.0.0.1" "https://${DOMAIN}/" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

rollback() {
  echo "ERROR: release $SHA failed its health check." >&2
  dc "$LIVE" release.env logs --tail 40 >&2 || true
  if [ -z "$PREV_TAG" ]; then
    echo "No previous release recorded (first deploy): nothing to roll back to. Left as-is for inspection." >&2
    exit 1
  fi
  say "ROLLING BACK to $PREV_TAG (images and compose/Caddy files)"
  install_files previous
  write_release_env "$PREV_TAG" release.env
  dc "$LIVE" release.env up -d --remove-orphans --wait --wait-timeout 600 || true
  reload_caddy
  if healthy_through_caddy; then
    echo "Rolled back to $PREV_TAG and it is healthy. Database migrations were NOT reverted." >&2
  else
    echo "CRITICAL: rollback to $PREV_TAG is also unhealthy. Investigate on the host now." >&2
  fi
  exit 1
}

if ! dc "$LIVE" release.env up -d --remove-orphans --wait --wait-timeout 600; then
  rollback
fi

# The Caddyfile directory is mounted, so a reload sees the new file.
reload_caddy

# --- 5. health through Caddy ---------------------------------------------------------
say "health check through Caddy"
if ! healthy_through_caddy; then
  rollback
fi

# --- 7. prune ------------------------------------------------------------------------
rm -rf "$STAGE"
prune_images "$SHA" "$PREV_TAG"
say "release $SHA is live. Disk free: $(free_gb) GB"
