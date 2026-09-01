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
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from herhealth_contracts.knowledge import Identifier

__all__ = ["PassageId", "PassageType", "RetrievedPassage"]

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

    #: Cosine similarity against the query. Not a probability and not evidence
    #: strength — it says how well the text matched the question asked, not
    #: how strongly it supports a condition.
    score: float = Field(ge=-1.0, le=1.0)

    #: Populated only when passage_type is EVIDENCE_STATEMENT. A source
    #: passage carries none of these — it is prose, not a graded claim.
    condition_id: Identifier | None = None
    feature_id: Identifier | None = None
    value: str | None = None
    strength: str | None = None
