#!/bin/bash
# Publish a retrieval index to the private artifacts bucket, once per version.
#
#   scripts/publish-index.sh --index-dir build/index-deploy \
#       --bge-m3-revision <40-hex Hugging Face commit> [--bucket NAME] [--dry-run]
#
# Run by a PERSON with write access (the admin IAM user), never by CI: CI only
# reads index/ (infra/terraform/prod/iam_oidc.tf).
#
# It REFUSES to upload when:
#   - manifest.json model_name is not exactly BAAI/bge-m3 (the hashing stand-in,
#     or any other embedder, must never ship);
#   - any passage has may_be_ingested false or missing, or comes from the
#     `nhs` source -- quote-only text must never enter the bucket or an image;
#   - the three files disagree about how many passages there are (a corrupt
#     index returns the wrong text for a query);
#   - that version already exists in the bucket (versions are immutable).
#
# The version is a content hash, so the same index always gets the same name and
# a changed index can never overwrite an old one. --dry-run does every check and
# computes the version without touching AWS.
#
# Layout written: s3://<bucket>/index/<version>/{vectors.npy,passages.jsonl,
# manifest.json,build-info.json}, encrypted with SSE-S3.
set -euo pipefail

INDEX_DIR=""
REVISION=""
BUCKET="${ARTIFACTS_BUCKET:-}"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --index-dir) INDEX_DIR="${2:?}"; shift 2 ;;
    --bge-m3-revision) REVISION="${2:?}"; shift 2 ;;
    --bucket) BUCKET="${2:?}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$INDEX_DIR" ] || { echo "--index-dir is required" >&2; exit 2; }
[ -n "$REVISION" ] || { echo "--bge-m3-revision is required (the index and the retrieval image must be built from the same weights)" >&2; exit 2; }

# Validation lives in Python (stdlib only): JSON and .npy headers are miserable
# in bash. On success it writes build-info.json and prints the version.
VERSION="$(python3 - "$INDEX_DIR" "$REVISION" <<'PY'
import ast, hashlib, json, re, struct, sys
from datetime import datetime, timezone
from pathlib import Path

index_dir, revision = Path(sys.argv[1]), sys.argv[2]
EXPECTED_MODEL = "BAAI/bge-m3"
FILES = ("manifest.json", "passages.jsonl", "vectors.npy")


def refuse(message: str) -> None:
    print(f"REFUSING: {message}", file=sys.stderr)
    sys.exit(1)


if not re.fullmatch(r"[0-9a-f]{40}", revision):
    refuse(f"--bge-m3-revision must be a full 40-hex commit sha, got {revision!r}")

for name in FILES:
    if not (index_dir / name).is_file():
        refuse(f"{index_dir / name} is missing")

manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
if manifest.get("model_name") != EXPECTED_MODEL:
    refuse(
        f"manifest.json model_name is {manifest.get('model_name')!r}, "
        f"not {EXPECTED_MODEL!r}. The hashing stand-in and any other embedder must never ship."
    )

# .npy header: magic, version, header length, then a python-literal dict.
with (index_dir / "vectors.npy").open("rb") as handle:
    if handle.read(6) != b"\x93NUMPY":
        refuse("vectors.npy is not a .npy file")
    major, _minor = handle.read(2)
    (header_len,) = struct.unpack("<H", handle.read(2)) if major == 1 else struct.unpack("<I", handle.read(4))
    header = ast.literal_eval(handle.read(header_len).decode("latin1"))
rows, dims = header["shape"]
if header["descr"] != "<f4" or header["fortran_order"]:
    refuse(f"vectors.npy must be little-endian float32 C-order, got {header}")

passages = 0
with (index_dir / "passages.jsonl").open(encoding="utf-8") as handle:
    for number, line in enumerate(handle, 1):
        if not line.strip():
            continue
        passage = json.loads(line)
        passages += 1
        # Missing counts as False: an unclassified passage is quote-only.
        if passage.get("may_be_ingested") is not True:
            refuse(
                f"passages.jsonl line {number} ({passage.get('source_id')}/{passage.get('slug')}) "
                f"has may_be_ingested={passage.get('may_be_ingested')!r}. Quote-only text must never "
                "enter the bucket or an image. Rebuild with --exclude-quote-only."
            )
        if passage.get("source_id") == "nhs":
            refuse(f"passages.jsonl line {number} is from the nhs source (citable_only, never redistributable)")

counts = {"manifest": manifest.get("passages"), "passages.jsonl": passages, "vectors.npy": rows}
if len(set(counts.values())) != 1:
    refuse(f"passage counts disagree: {counts}")
if manifest.get("dimensions") != dims:
    refuse(f"manifest dimensions {manifest.get('dimensions')} != vectors.npy {dims}")

digest = hashlib.sha256()
for name in FILES:  # fixed order
    digest.update(name.encode())
    digest.update((index_dir / name).read_bytes())
version = digest.hexdigest()[:16]

(index_dir / "build-info.json").write_text(
    json.dumps(
        {
            "version": version,
            "model_name": EXPECTED_MODEL,
            "bge_m3_revision": revision,
            "passages": passages,
            "dimensions": dims,
            "quote_only_passages": 0,
            "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(version)
PY
)"

echo "checks passed: index version $VERSION ($INDEX_DIR)"

if [ "$DRY_RUN" = 1 ]; then
  echo "dry run: nothing uploaded"
  exit 0
fi

[ -n "$BUCKET" ] || { echo "--bucket (or ARTIFACTS_BUCKET) is required to upload" >&2; exit 2; }
DEST="s3://${BUCKET}/index/${VERSION}/"

if [ -n "$(aws s3 ls "$DEST" 2>/dev/null)" ]; then
  echo "REFUSING: $DEST already exists. Index versions are immutable." >&2
  exit 1
fi

for f in vectors.npy passages.jsonl manifest.json build-info.json; do
  aws s3 cp "$INDEX_DIR/$f" "${DEST}${f}" --sse AES256 --only-show-errors
done

echo
echo "published $DEST"
echo "next: set the GitHub repository variable RETRIEVAL_INDEX_VERSION=${VERSION}"
echo "      and BGE_M3_REVISION=${REVISION} (they must match build-info.json)"
