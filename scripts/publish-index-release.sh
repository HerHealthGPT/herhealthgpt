#!/usr/bin/env bash
# Publish the retrieval index as a GitHub release file, and point the deploy
# workflow at it.
#
#   make index && scripts/publish-index-release.sh
#
# The index is built here because building it calls the embedding server. It
# is not committed. The deploy workflow downloads the release named by the
# repository variable INDEX_RELEASE and bakes it into the backend image.
#
# Refuses an index that holds quote-only (NHS) text: that text may be quoted
# with attribution but must never be distributed in an index.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INDEX_DIR="${1:-$REPO_ROOT/build/index}"

for f in index.faiss passages.jsonl manifest.json; do
  [ -f "$INDEX_DIR/$f" ] || { echo "missing $INDEX_DIR/$f; run make index" >&2; exit 1; }
done

python3 - "$INDEX_DIR/manifest.json" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1]))
if manifest["contains_quote_only"]:
    sys.exit("refusing: this index holds quote-only text (build it with `make index`, not index-authoring)")
print(f"index: {manifest['passages']} passages, {manifest['embedding_model']}, built {manifest['built_at']}")
PY

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -czf "$work/index.tar.gz" -C "$INDEX_DIR" index.faiss passages.jsonl manifest.json
digest="$(sha256sum "$work/index.tar.gz" | cut -c1-12)"
tag="index-$(date -u +%Y%m%d)-$digest"

if gh release view "$tag" >/dev/null 2>&1; then
  echo "release $tag already exists; reusing it"
else
  gh release create "$tag" "$work/index.tar.gz" \
    --title "Retrieval index $tag" \
    --notes "Retrieval index for the backend image. Built by make index; holds no quote-only text. Not a code release."
fi
gh variable set INDEX_RELEASE --body "$tag"
echo "INDEX_RELEASE=$tag"
