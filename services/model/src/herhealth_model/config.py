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
    "INGEST_LOCK_ENV",
    "MEDLINEPLUS_EXCLUDED_PATH_FRAGMENT",
    "MIN_SCORE_ENV",
    "embedding_model_name",
    "index_dir",
    "evidence_slots",
    "ingest_lock_path",
    "min_score",
]

INDEX_DIR_ENV = "HERHEALTH_INDEX_DIR"
EMBEDDING_MODEL_ENV = "HERHEALTH_EMBEDDING_MODEL"
MIN_SCORE_ENV = "HERHEALTH_MIN_SCORE"
INGEST_LOCK_ENV = "HERHEALTH_INGEST_LOCK"
EVIDENCE_SLOTS_ENV = "HERHEALTH_EVIDENCE_SLOTS"

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


def ingest_lock_path() -> Path:
    """The tracked record of what ``make fetch`` retrieved, used to turn a
    passage's ``(source_id, slug)`` into the page it came from — see
    ``source_urls.py``. Defaults next to the data service's own copy, which
    is where ``make fetch`` writes it.
    """
    value = os.environ.get(INGEST_LOCK_ENV)
    if value:
        return Path(value)
    from herhealth_data.paths import REPO_ROOT

    return REPO_ROOT / "services" / "data" / "ingest.lock.jsonl"


def embedding_model_name() -> str:
    """The embedder to load. Defaults to the index's own choice — bge-m3 —
    but overridable for a fast, non-semantic dev loop via ``hashing``, the
    same escape hatch ``herhealth_data.cli index --model hashing`` already
    offers.
    """
    return os.environ.get(EMBEDDING_MODEL_ENV) or "BAAI/bge-m3"


def evidence_slots() -> int:
    """How many of a search's ``k`` slots are reserved for evidence
    statements — ``evidence.csv`` rows rendered as retrievable sentences.

    Exists because the two passage types are wildly unbalanced in the index
    and pure cosine ranking therefore buries the structured one. Measured on
    the 2026-09-02 index (4454 passages): 4314 source passages, 140 evidence
    statements — 3.1%. Across eight representative in-domain openers, five
    returned **no** evidence statement at all in the top 8, the first one
    landing at rank 27, 28, 33 or beyond 60.

    That matters far more than a ranking nicety, because an evidence
    statement is the only passage type that carries a ``feature_id``, and
    ``herhealth_backend.triage.clients``' prompt tells the model it may not
    invent one: with none retrieved, the model either concludes on turn one
    (against the system prompt's instruction to ask two or three clarifying
    questions first) or invents an id and trips
    ``vocabulary.ClosedVocabularyViolation``, which the API surfaces as a
    502. Reserving slots is the cheap fix; ADR 0010 defers a reranker until
    "the right passage is retrieved but ranked outside top k", which is
    exactly the measurement above, so revisit that ADR if this proves
    insufficient rather than raising this number indefinitely.
    """
    raw = os.environ.get(EVIDENCE_SLOTS_ENV)
    return int(raw) if raw else 3


def min_score() -> float:
    """Below this cosine score, a primary-index hit does not count as
    'found' and the guarded web fallback (docs/adr/0012, §3) is eligible to
    run instead. Conservative by default: a low bar here would let a
    barely-related passage stand in for real evidence, which is the opposite
    of what ADR 0012 exists to prevent.
    """
    raw = os.environ.get(MIN_SCORE_ENV)
    return float(raw) if raw else 0.3
