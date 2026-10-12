"""Canonical filesystem locations, defined once.

Every other module imports from here rather than recomputing paths relative to
``__file__``. When the repository layout changes, this is the only file that
needs to know.

Nothing here touches the filesystem — these are locations, not guarantees that
anything exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# paths.py -> herhealth_data -> src -> data -> services -> <repo root>
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[4]

#: Hand-authored clinical knowledge. Tracked.
KNOWLEDGE_DIR: Final[Path] = REPO_ROOT / "knowledge"

#: Immutable fetched source documents. Gitignored.
RAW_DIR: Final[Path] = REPO_ROOT / "raw"

#: Generated artifacts — cleaned text, passages.parquet, conflicts. Gitignored.
BUILD_DIR: Final[Path] = REPO_ROOT / "build"

#: Flat table exports of the knowledge base. Generated, gitignored.
TABLES_DIR: Final[Path] = BUILD_DIR / "tables"

#: Readable per-condition and per-answer views of the evidence grid.
CARDS_DIR: Final[Path] = BUILD_DIR / "cards"

#: Sectioned, quotable text produced by the clean step. Gitignored.
CLEAN_DIR: Final[Path] = BUILD_DIR / "clean"

#: The passage index: a vector matrix plus one JSON line per passage.
#: Generated and gitignored — rebuildable from build/clean/ with `make index`.
INDEX_DIR: Final[Path] = BUILD_DIR / "index"
#: Includes quote-only (NHS) passages. For the evidence-proposal tool on the
#: authoring machine only; never served and never copied to a server.
AUTHORING_INDEX_DIR: Final[Path] = BUILD_DIR / "index-authoring"

DATA_SERVICE_DIR: Final[Path] = REPO_ROOT / "services" / "data"

#: What to fetch, and the per-source guards. Tracked.
INGEST_TARGETS_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest_targets.yaml"
INGEST_LOCK_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest.lock.jsonl"
#: Model ids, pinned revisions and ports for the vLLM processes (step 1).
SERVE_CONF: Final[Path] = REPO_ROOT / "infra" / "model" / "serve.conf"

#: Reviewed evidence rows, authored as YAML. Tracked. knowledge/evidence.csv
#: is generated from these by `make evidence`.
EVIDENCE_BATCH_DIR: Final[Path] = DATA_SERVICE_DIR / "evidence_batches"

#: What the sources SAY, hashed from extracted text. Tracked. This is the
#: drift signal; the ingest lock is provenance of exact bytes.
CONTENT_LOCK_FILE: Final[Path] = DATA_SERVICE_DIR / "content.lock.jsonl"

#: What was fetched, with hashes. Tracked — the only record of raw/ in git.
INGEST_LOCK_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest.lock.jsonl"

#: Benchmark cases. Tracked, version-controlled alongside the knowledge.
CASES_DIR: Final[Path] = DATA_SERVICE_DIR / "eval" / "cases"
