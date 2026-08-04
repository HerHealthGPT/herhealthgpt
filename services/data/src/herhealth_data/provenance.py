"""Verify that every source_quote actually appears in the source it cites.

This is the check that makes the verification protocol real.

The protocol says every clinical row must restate something a cited source
says, and that a reviewer confirms the quote supports the row. But nothing so
far confirmed the more basic thing: that the quote *exists*, character for
character, in the document it is attributed to. Until this module, that rested
on whoever transcribed it not having made a mistake.

Three failures it catches, none of which is visible by reading the row:

**Drift.** A quote retyped or reflowed by a hair. It still reads correctly, and
a reviewer searching the page for it finds nothing.

**Misattribution.** A quote that is real but belongs to a different source. The
row looks perfect; the citation is wrong. This is why matching is scoped to the
cited source rather than to the corpus as a whole — a corpus-wide match would
pass exactly the rows that are wrong.

**Silent paraphrase.** Text that was summarised rather than quoted. The most
serious, because a paraphrase of a clinical claim is a new clinical claim, and
authoring those is the thing the protocol exists to prevent.

Runs against ``build/clean``, which is generated and gitignored, so this cannot
live in ``make validate`` — that must work from a fresh clone with no corpus and
no optional dependencies. It is its own command for that reason.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

__all__ = [
    "Corpus",
    "QuoteCheck",
    "Verdict",
    "load_corpus",
    "verify_quotes",
]


class Verdict(StrEnum):
    """What became of one quote."""

    #: Found verbatim in a document belonging to the cited source.
    VERIFIED = "verified"

    #: Found verbatim, but only in a document from a different source. The
    #: quote is real; the citation is wrong.
    WRONG_SOURCE = "wrong_source"

    #: Not found anywhere. Either drifted, paraphrased, or from a document that
    #: was never fetched.
    NOT_FOUND = "not_found"

    #: The cited source has no documents in the corpus, so nothing can be
    #: checked. Not a failure of the row.
    SOURCE_ABSENT = "source_absent"


@dataclass(frozen=True, slots=True)
class QuoteCheck:
    """The outcome for one quote, with enough context to fix it."""

    location: str
    source_id: str
    quote: str
    verdict: Verdict
    found_in: str | None = None
    closest: str | None = None

    @property
    def is_problem(self) -> bool:
        return self.verdict in (Verdict.WRONG_SOURCE, Verdict.NOT_FOUND)

    def describe(self) -> str:
        head = f"  {self.verdict.value.upper():<13} {self.location}"
        if self.verdict is Verdict.VERIFIED:
            return f"{head}  ({self.found_in})"
        if self.verdict is Verdict.SOURCE_ABSENT:
            return f"{head}  no {self.source_id!r} documents in the corpus; not checked"
        lines = [head, f'{"":<16}cites {self.source_id!r}: "{self.quote[:88]}"']
        if self.verdict is Verdict.WRONG_SOURCE:
            lines.append(f'{"":<16}but it appears in {self.found_in} instead')
        elif self.closest:
            lines.append(f'{"":<16}closest text found: "{self.closest[:88]}"')
        else:
            lines.append(f'{"":<16}no similar text found in any document')
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Corpus:
    """Cleaned text, indexed by source, for substring matching."""

    #: source_id -> the concatenated text of its documents
    by_source: dict[str, str] = field(default_factory=dict)

    #: source_id -> document slugs, for reporting where a quote was found
    slugs: dict[str, list[str]] = field(default_factory=dict)

    def sources(self) -> list[str]:
        return sorted(self.by_source)

    def contains(self, source_id: str, quote: str) -> bool:
        return quote in self.by_source.get(source_id, "")

    def find_elsewhere(self, quote: str, excluding: str) -> str | None:
        for source_id, text in sorted(self.by_source.items()):
            if source_id != excluding and quote in text:
                return source_id
        return None

    def closest_to(self, quote: str, source_id: str) -> str | None:
        """The most similar sentence in the cited source, to show the drift."""
        text = self.by_source.get(source_id, "")
        if not text:
            return None
        candidates = [line for line in text.splitlines() if len(line) > 20]
        matches = difflib.get_close_matches(quote, candidates, n=1, cutoff=0.6)
        return matches[0] if matches else None


def load_corpus(clean_dir: Path) -> Corpus:
    """Read every cleaned document, grouped by source."""
    corpus = Corpus()
    for path in sorted(clean_dir.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        source_id = str(document["source_id"])
        lines = [
            line
            for section in document["sections"]
            for line in (section["heading"], *section["paragraphs"])
        ]
        existing = corpus.by_source.get(source_id, "")
        corpus.by_source[source_id] = existing + "\n" + "\n".join(lines)
        corpus.slugs.setdefault(source_id, []).append(str(document["slug"]))
    return corpus


def verify_quotes(
    quotes: Iterable[tuple[str, str, str]],
    corpus: Corpus,
) -> list[QuoteCheck]:
    """Check each ``(location, source_id, quote)`` against the corpus.

    Matching is scoped to the cited source first. A quote found only elsewhere
    is reported as misattributed rather than passed, because a corpus-wide
    match would pass precisely the rows whose citation is wrong.
    """
    checks: list[QuoteCheck] = []
    for location, source_id, quote in quotes:
        cleaned = " ".join(quote.split())

        if source_id not in corpus.by_source:
            checks.append(QuoteCheck(location, source_id, cleaned, Verdict.SOURCE_ABSENT))
            continue

        if corpus.contains(source_id, cleaned):
            slugs = corpus.slugs.get(source_id, [])
            where = f"{source_id}, {len(slugs)} document(s)"
            checks.append(
                QuoteCheck(location, source_id, cleaned, Verdict.VERIFIED, found_in=where)
            )
            continue

        elsewhere = corpus.find_elsewhere(cleaned, excluding=source_id)
        if elsewhere:
            checks.append(
                QuoteCheck(location, source_id, cleaned, Verdict.WRONG_SOURCE, found_in=elsewhere)
            )
            continue

        checks.append(
            QuoteCheck(
                location,
                source_id,
                cleaned,
                Verdict.NOT_FOUND,
                closest=corpus.closest_to(cleaned, source_id),
            )
        )
    return checks


def summarise(checks: Sequence[QuoteCheck]) -> str:
    counts: dict[str, int] = {}
    for check in checks:
        counts[check.verdict.value] = counts.get(check.verdict.value, 0) + 1
    return ", ".join(f"{n} {verdict}" for verdict, n in sorted(counts.items()))
