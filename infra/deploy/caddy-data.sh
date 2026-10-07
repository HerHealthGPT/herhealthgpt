#!/bin/bash
# Save / restore Caddy's certificate store (the compose volume herhealth_caddy_data).
#
#   caddy-data.sh backup     before destroying or replacing the server
#   caddy-data.sh restore    on the new server, BEFORE the first deploy
#
# Why: Let's Encrypt allows 5 duplicate certificates per week for the same set
# of names. Each fresh server asks for a new certificate for herhealthgpt.org,
# api.herhealthgpt.org and www.herhealthgpt.org, so repeated destroy/recreate
# cycles hit that limit and the site serves no valid certificate until it
# resets. Restoring the old store means no new issuance at all.
set -euo pipefail

# shellcheck disable=SC1091
source /opt/herhealth/instance.env

VOLUME=herhealth_caddy_data
KEY="s3://${ARTIFACTS_BUCKET}/caddy-backup/caddy_data.tar.gz"

case "${1:-}" in
  backup)
    docker volume inspect "$VOLUME" >/dev/null
    docker run --rm -v "$VOLUME":/data:ro alpine:3.20 tar -C /data -czf - . \
      | aws s3 cp - "$KEY" --sse AES256
    echo "backed up to $KEY"
    ;;
  restore)
    docker volume create "$VOLUME" >/dev/null
    aws s3 cp "$KEY" - \
      | docker run --rm -i -v "$VOLUME":/data alpine:3.20 tar -C /data -xzf -
    echo "restored from $KEY"
    ;;
  *)
    echo "usage: $0 backup|restore" >&2
    exit 2
    ;;
esac
