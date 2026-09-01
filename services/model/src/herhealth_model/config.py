"""Where this process reads its configuration from.

Mirrors ``herhealth_backend.app.config``'s shape (one module, typed readers,
required values raise rather than guess) even though this service's values
are mostly optional — there is no database URL here to get silently wrong,
but the same discipline costs nothing and keeps every service's config
module readable the same way.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

__all__ = [
    "ALLOWED_FALLBACK_DOMAINS",
    "EMBEDDING_MODEL_ENV",
    "INDEX_DIR_ENV",
    "MEDLINEPLUS_EXCLUDED_PATH_FRAGMENT",
    "MIN_SCORE_ENV",
    "embedding_model_name",
    "index_dir",
    "min_score",
]

INDEX_DIR_ENV = "HERHEALTH_INDEX_DIR"
EMBEDDING_MODEL_ENV = "HERHEALTH_EMBEDDING_MODEL"
MIN_SCORE_ENV = "HERHEALTH_MIN_SCORE"

#: Same five sources as knowledge/sources.yaml, and for the same reason: no
#: source beyond these is licensed for this project to use. Hardcoded rather
#: than loaded from sources.yaml because that file records precedence and
#: licence status, not a base domain — keep this list in sync by hand if
#: sources.yaml ever changes, and say so here so nobody assumes it is derived.
ALLOWED_FALLBACK_DOMAINS: Final[dict[str, str]] = {
    "medlineplus.gov": "medlineplus",
    "nichd.nih.gov": "nichd",
    "womenshealth.gov": "womenshealth",
    "cdc.gov": "cdc",
    "nhs.uk": "nhs",
}

#: MedlinePlus's A.D.A.M. Medical Encyclopedia is not public domain — see
#: CLAUDE.md, "MedlinePlus has a split licence and it matters." Applies live,
#: not only during batch ingestion.
MEDLINEPLUS_EXCLUDED_PATH_FRAGMENT: Final[str] = "/ency/"


def index_dir() -> Path:
    """Where the built ``PassageIndex`` lives. Defaults to ``herhealth_data``'s
    own default (``build/index``), so a dev box that has run
    ``python -m herhealth_data.cli index`` needs no configuration at all.
    """
    value = os.environ.get(INDEX_DIR_ENV)
    if value:
        return Path(value)
    from herhealth_data.paths import INDEX_DIR

    return INDEX_DIR


def embedding_model_name() -> str:
    """The embedder to load. Defaults to the index's own choice — bge-m3 —
    but overridable for a fast, non-semantic dev loop via ``hashing``, the
    same escape hatch ``herhealth_data.cli index --model hashing`` already
    offers.
    """
    return os.environ.get(EMBEDDING_MODEL_ENV) or "BAAI/bge-m3"


def min_score() -> float:
    """Below this cosine score, a primary-index hit does not count as
    'found' and the guarded web fallback (docs/adr/0012, §3) is eligible to
    run instead. Conservative by default: a low bar here would let a
    barely-related passage stand in for real evidence, which is the opposite
    of what ADR 0012 exists to prevent.
    """
    raw = os.environ.get(MIN_SCORE_ENV)
    return float(raw) if raw else 0.3
