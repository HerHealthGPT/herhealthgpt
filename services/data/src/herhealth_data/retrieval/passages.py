"""Turn cleaned documents into sentence-level passages.

**Sentence-aware chunking, and the sentence is the unit for two reasons.**

The first is empirical. Alsubhi et al. compared four chunking strategies across
six Arabic datasets and found sentence-aware chunking best overall (74.78 mean),
ahead of fixed-size (69.41) and recursive (69.13) — and, notably, well ahead of
embedding-based *semantic* chunking (66.92), which underperformed everywhere.
See docs/adr/0010.

The second is structural, and it is the one that decides it for us regardless of
benchmarks: every clinical row carries a ``source_quote`` that must appear
**verbatim** in its source, and ``make verify-quotes`` checks exactly that. If a
passage spanned a chunk boundary, the sentence a reviewer wants to quote might
not exist as a retrievable unit. Retrieving sentences means anything retrieved
can be quoted directly.

Text is never altered here. The cleaner already normalised whitespace and
refused undecodable input; this module only *splits*. A passage that does not
appear character-for-character in the cleaned document is a bug.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from herhealth_contracts.knowledge import Condition, EvidenceRow, Feature
from herhealth_contracts.retrieval import PassageType

__all__ = [
    "Passage",
    "evidence_statement_passages",
    "load_passages",
    "split_sentences",
]

#: Below this many characters a "sentence" is a heading fragment, a list marker
#: or navigation debris. Clinical statements are longer.
MIN_SENTENCE_CHARS = 40

#: Abbreviations that end in a full stop without ending a sentence. Kept small
#: and explicit: a long list would silently join real sentences.
_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "approx.",
    "Dr.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "St.",
    "no.",
    "No.",
    "cm.",
    "mm.",
    "ml.",
)

#: Split after . ! ? when followed by whitespace and something that starts a new
#: sentence. Requiring the next character to be upper-case or a digit avoids
#: splitting "2.5cm" and "1. Take one tablet".
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Zء-ي0-9])")

_PLACEHOLDER = "\x00"


@dataclass(frozen=True, slots=True)
class Passage:
    """One sentence, with everything needed to cite it."""

    source_id: str
    slug: str
    heading: str
    section_type: str
    text: str

    #: From ``sources.yaml``. False for NHS, whose licence permits quoting but
    #: not redistribution — such a passage may back a ``source_quote`` and must
    #: never enter the served corpus. Carried per passage so the distinction
    #: survives into the index rather than being re-derived later.
    may_be_ingested: bool = True

    #: ``source_passage`` (a sentence from a cleaned document, the default) or
    #: ``evidence_statement`` (one evidence.csv row, see
    #: :func:`evidence_statement_passages`). Mirrors
    #: ``herhealth_contracts.retrieval.PassageType`` by value rather than by
    #: import, so a passage built here can be compared against one received
    #: over the service boundary without services/data depending on that being
    #: the same object.
    passage_type: str = PassageType.SOURCE_PASSAGE.value

    #: Populated only when passage_type is "evidence_statement". A source
    #: passage carries none of these — it is prose, not a graded claim.
    condition_id: str | None = None
    feature_id: str | None = None
    value: str | None = None
    strength: str | None = None

    @property
    def id(self) -> str:
        """Stable across runs, so an index can be diffed against an older one."""
        digest = hashlib.sha256(
            f"{self.source_id}\x00{self.slug}\x00{self.text}".encode()
        ).hexdigest()
        return digest[:16]

    @property
    def citation(self) -> str:
        return f"{self.source_id}/{self.slug}" + (f" § {self.heading}" if self.heading else "")


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences without altering any character.

    Joining the result with single spaces reproduces the input, which is what
    keeps every passage quotable.
    """
    protected = paragraph
    for abbreviation in _ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", _PLACEHOLDER))

    parts = _BOUNDARY.split(protected)
    return [part.replace(_PLACEHOLDER, ".").strip() for part in parts if part.strip()]


def _sections(document: dict[str, object]) -> Iterator[tuple[str, str, list[str]]]:
    for section in document.get("sections", []) or []:
        if not isinstance(section, dict):
            continue
        paragraphs = [p for p in (section.get("paragraphs") or []) if isinstance(p, str)]
        yield (
            str(section.get("heading") or ""),
            str(section.get("section_type") or "other"),
            paragraphs,
        )


def load_passages(
    clean_dir: Path, ingestable: dict[str, bool] | None = None
) -> list[Passage]:
    """Read every cleaned document and split it into sentence passages.

    ``ingestable`` maps source id to whether its licence permits redistribution;
    anything missing defaults to **False**, so a source nobody has classified is
    treated as quote-only rather than assumed safe to serve.
    """
    permitted = ingestable or {}
    passages: list[Passage] = []
    seen: set[str] = set()

    for path in sorted(clean_dir.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        source_id = str(document.get("source_id") or path.parent.name)
        slug = str(document.get("slug") or path.stem)

        for heading, section_type, paragraphs in _sections(document):
            for paragraph in paragraphs:
                for sentence in split_sentences(paragraph):
                    if len(sentence) < MIN_SENTENCE_CHARS:
                        continue
                    passage = Passage(
                        source_id=source_id,
                        slug=slug,
                        heading=heading,
                        section_type=section_type,
                        text=sentence,
                        may_be_ingested=permitted.get(source_id, False),
                    )
                    # The same boilerplate sentence recurs across pages of one
                    # source. Keeping duplicates would let a retrieval hit be
                    # decided by how often a footer repeats.
                    key = f"{source_id}\x00{sentence}"
                    if key in seen:
                        continue
                    seen.add(key)
                    passages.append(passage)

    return passages


def evidence_statement_passages(
    evidence: Sequence[EvidenceRow],
    features: Mapping[str, Feature],
    conditions: Mapping[str, Condition],
    ingestable: Mapping[str, bool] | None = None,
) -> list[Passage]:
    """Render every evidence.csv row as one retrievable statement.

    Each row already carries a verbatim ``source_quote`` — the retrievable part
    of the row, per docs/research/0001 §2a — but a bare quote does not say
    which condition or feature it was authored against, so a similarity search
    over quotes alone could return the right sentence attached to the wrong
    claim. This wraps the quote in that context. ``source_quote`` itself is
    appended unedited, character for character, so ``make verify-quotes`` can
    still check it: only the surrounding sentence is generated.

    Same licence rule as every other passage, checked against the same
    ``ingestable`` mapping ``load_passages`` uses: a row backed by a
    ``citable_only`` source (NHS backs 37 of 89 rows today) is still built and
    still searchable during authoring, but comes back ``may_be_ingested=False``
    so it can never enter the served corpus. See ``Source.may_be_ingested``.

    A row whose ``condition_id`` or ``feature_id`` is not in ``features`` /
    ``conditions`` is skipped rather than raised on — that mismatch is a
    referential-integrity fault ``make validate`` already catches elsewhere,
    and this function is not the place to raise it a second time.
    """
    permitted = ingestable or {}
    passages: list[Passage] = []

    for row in evidence:
        feature = features.get(row.feature_id)
        condition = conditions.get(row.condition_id)
        if feature is None or condition is None:
            continue

        strength = row.strength.value.replace("_", " ")
        text = (
            f"{feature.label} = {row.value} ({strength}) for {condition.label}. "
            f'Source: "{row.source_quote}"'
        )
        passages.append(
            Passage(
                source_id=row.source_id,
                slug=f"evidence/{row.condition_id}/{row.feature_id}/{row.value}",
                heading=condition.label,
                section_type="evidence_statement",
                text=text,
                may_be_ingested=permitted.get(row.source_id, False),
                passage_type=PassageType.EVIDENCE_STATEMENT.value,
                condition_id=row.condition_id,
                feature_id=row.feature_id,
                value=row.value,
                strength=row.strength.value,
            )
        )

    return passages
