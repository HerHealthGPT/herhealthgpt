#!/bin/bash
# First-boot stub, installed as /opt/herhealth/deploy.sh by user_data.
#
# Why it exists: SSM Run Command needs *something* at /opt/herhealth/deploy.sh
# before any release has ever been deployed. Embedding the whole real deploy.sh
# (and refresh-secrets.sh) in user_data used to push it close to EC2's 16 KB
# limit, and both are replaced from S3 on the first deploy anyway. So this stub
# only fetches the real deploy.sh for the release being installed and hands over
# to it. It is never edited by hand and never needs to change when deploy.sh does.
set -euo pipefail

SHA="${1:?usage: deploy.sh <git-sha>}"
[[ "$SHA" =~ ^[0-9a-f]{7,64}$ ]] || { echo "refusing: '$SHA' is not a git sha" >&2; exit 2; }

# If the file we fetch is itself this stub, handing over would loop forever. The
# flag below is set on the hand-over; seeing it set on entry means we ARE the
# fetched file.
if [ -n "${HERHEALTH_DEPLOY_REEXEC:-}" ]; then
  echo "ERROR: deploy/$SHA/deploy.sh in S3 is the bootstrap stub, not the real deploy script." >&2
  exit 1
fi

HOME_DIR="${HERHEALTH_HOME:-/opt/herhealth}"
# shellcheck disable=SC1091
source "$HOME_DIR/instance.env"

aws s3 cp "s3://${ARTIFACTS_BUCKET}/deploy/${SHA}/deploy.sh" "$HOME_DIR/deploy.sh.new" --only-show-errors
chmod 755 "$HOME_DIR/deploy.sh.new"
mv "$HOME_DIR/deploy.sh.new" "$HOME_DIR/deploy.sh"
HERHEALTH_DEPLOY_REEXEC=1 exec "$HOME_DIR/deploy.sh" "$SHA"
