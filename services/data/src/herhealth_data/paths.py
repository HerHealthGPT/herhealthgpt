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

#: Sectioned, quotable text produced by the clean step. Gitignored.
CLEAN_DIR: Final[Path] = BUILD_DIR / "clean"

DATA_SERVICE_DIR: Final[Path] = REPO_ROOT / "services" / "data"

#: What to fetch, and the per-source guards. Tracked.
INGEST_TARGETS_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest_targets.yaml"

#: What was fetched, with hashes. Tracked — the only record of raw/ in git.
INGEST_LOCK_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest.lock.jsonl"

#: Benchmark cases. Tracked, version-controlled alongside the knowledge.
CASES_DIR: Final[Path] = DATA_SERVICE_DIR / "eval" / "cases"
