"""Download BAAI/bge-m3 at one exact commit and make it the cache's `main`.

    python scripts/pin-bge-m3.py [<40-hex revision>]

The index CLI cannot take a revision, so the Hugging Face cache is pinned
instead and the index is then built with HF_HUB_OFFLINE=1 -- the same steps
services/model/Dockerfile takes for the image, so the index and the image embed
with the same weights. With no argument, pins the repository's current head.

The last line printed is the revision, for BGE_M3_REVISION.
"""

import pathlib
import re
import sys

from huggingface_hub import HfApi, snapshot_download

MODEL = "BAAI/bge-m3"

rev = (
    sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else HfApi().model_info(MODEL).sha
)
if not rev or not re.fullmatch(r"[0-9a-f]{40}", rev):
    sys.exit(f"revision must be a full 40-hex commit sha, got {rev!r}")

print(f"pinning {MODEL} at {rev}", file=sys.stderr)
snap = pathlib.Path(
    snapshot_download(
        MODEL, revision=rev, ignore_patterns=["onnx/*", "imgs/*", "*.jpg", "*.png"]
    )
)
refs = snap.parents[1] / "refs"
refs.mkdir(exist_ok=True)
(refs / "main").write_text(rev)
print(rev)
