"""The cross-service shape of a retrieved passage.

``herhealth_data.retrieval.passages.Passage`` is the authoring-side
implementation: a plain dataclass, built and embedded inside ``services/data``,
where numpy and (optionally) ``sentence_transformers`` are available. Nothing
outside ``packages/contracts`` may cross a service boundary, so now that
retrieval is promoted from "propose evidence rows for a human to review" to
"ground a live answer for the reasoning model", the backend needs a passage
shape it can hold without importing ``services/data``. This is that shape.

A :class:`RetrievedPassage` is what a search returns; nothing constructs one
directly from scratch. Whatever runs the search — today ``services/data``,
later ``services/model`` or the backend's own retrieval client — is
responsible for turning a ``Passage`` plus a similarity score into one of
these before it crosses the service boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from herhealth_contracts.knowledge import Identifier

__all__ = [
    "INDEX_FILE",
    "MANIFEST_FILE",
    "PASSAGES_FILE",
    "QUERY_INSTRUCTION",
    "IndexManifest",
    "IndexedPassage",
    "PassageId",
    "PassageType",
    "RetrievedPassage",
    "format_query",
]

#: The three files that make up a retrieval index on disk. The builder
#: (services/data) writes them and the backend reads them; neither imports the
#: other, so these names and the two models below ARE the interface. There is
#: deliberately no pickle among them: unpickling executes code, and an index is
#: copied between machines.
INDEX_FILE = "index.faiss"
PASSAGES_FILE = "passages.jsonl"
MANIFEST_FILE = "manifest.json"

#: Qwen3-Embedding is instruction-aware on the QUERY side only: documents are
#: embedded as plain text, queries as "Instruct: <task>\nQuery:<text>". The
#: builder and every searcher must agree on this, which is why it lives here.
QUERY_INSTRUCTION = (
    "Given a question about women's reproductive health, "
    "retrieve passages that answer it"
)


def format_query(query: str) -> str:
    """A query in the form the embedding model was trained to read."""
    return f"Instruct: {QUERY_INSTRUCTION}\nQuery:{query}"

#: Passage.id is hashlib.sha256(f"{source_id}\\x00{slug}\\x00{text}").hexdigest()[:16]
#: — lowercase hex, fixed length, and deliberately not an Identifier: it names
#: a piece of retrievable text, not a concept in the knowledge base, and must
#: never be confused with a feature or condition id in the same citation list.
PassageId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9a-f]{16}$")
]


class PassageType(StrEnum):
    """What a passage came from, so a citation can be interpreted correctly.

    A ``SOURCE_PASSAGE`` is a sentence from a cleaned source document — general
    prose. An ``EVIDENCE_STATEMENT`` is one ``evidence.csv`` row rendered as a
    retrievable sentence (see
    ``herhealth_data.retrieval.passages.evidence_statement_passages``) and
    carries the row's structured fields alongside its text, so a citation can
    be checked against the knowledge base rather than only read.

    A ``LIVE_FALLBACK`` passage was fetched live, on demand, from an approved
    domain, because the reviewed index returned nothing usable for the query —
    see docs/adr/0012-openrouter-reasoning-and-guarded-web-fallback.md. It is
    never persisted into the served index and never backs a ``strong``/``weak``
    evidence claim; it exists only so a decision has something real to cite
    instead of nothing. Callers must treat a decision grounded only in
    ``LIVE_FALLBACK`` passages as lower-provenance than one grounded in a
    reviewed passage — see that ADR's §3, rule 4 (it may not resolve to
    ``SELF_CARE``).
    """

    SOURCE_PASSAGE = "source_passage"
    EVIDENCE_STATEMENT = "evidence_statement"
    LIVE_FALLBACK = "live_fallback"


class RetrievedPassage(BaseModel):
    """One hit from the knowledge base, as the reasoning model is shown it."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: PassageId
    passage_type: PassageType
    source_id: Identifier
    text: str
    citation: str

    #: How well the text matched the query: the reranker's relevance score
    #: when it ran, otherwise cosine similarity. Not a probability of anything
    #: clinical and not evidence strength.
    score: float = Field(ge=-1.0, le=1.0)

    #: The page this text was actually fetched from, so a citation shown to a
    #: user is a link she can open and read rather than an internal
    #: ``source/slug`` label. Resolved from ``services/data/ingest.lock.jsonl``
    #: — the tracked record of what was fetched (``raw/`` itself is
    #: gitignored) — keyed on ``(source_id, slug)``. Optional because
    #: resolution can miss: a LIVE_FALLBACK passage carries its own live url,
    #: and a passage whose document predates the lock file has none. A
    #: missing url is rendered as plain text, never as a broken link.
    url: str | None = None

    #: Populated only when passage_type is EVIDENCE_STATEMENT. A source
    #: passage carries none of these — it is prose, not a graded claim.
    condition_id: Identifier | None = None
    feature_id: Identifier | None = None
    value: str | None = None
    strength: str | None = None


class IndexedPassage(BaseModel):
    """One line of ``passages.jsonl``: a passage and everything needed to cite
    it. Line N describes vector N of ``index.faiss``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: PassageId
    passage_type: PassageType
    source_id: Identifier
    slug: str
    heading: str = ""
    text: str
    citation: str
    url: str | None = None
    #: False for a quote-only source (NHS). Such a passage may sit in the
    #: authoring index and must never be in a served one.
    may_be_ingested: bool
    condition_id: Identifier | None = None
    feature_id: Identifier | None = None
    value: str | None = None
    strength: str | None = None


class IndexManifest(BaseModel):
    """``manifest.json``: what built this index, so a reader can refuse one it
    cannot use before answering a single query from it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal[1] = 1
    #: The embedding model's real id, not the name it is served under.
    embedding_model: str = Field(min_length=1)
    embedding_revision: str | None = None
    dimensions: int = Field(gt=0)
    passages: int = Field(ge=0)
    evidence_statements: int = Field(ge=0)
    contains_quote_only: bool
    built_at: str
