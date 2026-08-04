"""Turn fetched HTML into sectioned, quotable text.

Reads through :class:`RawStore`, strips boilerplate, splits on headings, and
classifies each section. Output goes to ``build/clean/{source}/{slug}.json``.

**Text is preserved verbatim.** Whitespace is normalised and nothing else — no
reflowing, no summarising, no paraphrasing. Every ``source_quote`` in
``evidence.csv`` and ``red_flags.yaml`` must be a sentence that genuinely
appears in the source, so a cleaner that rewrites text would quietly destroy the
one guarantee the verification protocol rests on. This is also why we parse the
markup ourselves rather than using a heuristic main-content extractor.

**Locale-specific references are recorded, not replaced.** The ingestion
protocol says service references ("call 999", "see your GP") become action
codes — but that substitution belongs to the *build* stage that writes
``passages.parquet``, not here, because rewriting them here would corrupt the
quotable text. Each section instead carries ``locale_references`` listing what
was found, so the build stage knows what to substitute and a reviewer can see
which sections need it.

``when_to_get_help`` is the highest-value output. Red-flag rules may only be
derived from explicit escalation language, and this is where that language is.

This module imports BeautifulSoup, which lives in the optional ``ingest`` extra.
It is deliberately NOT re-exported from ``herhealth_data.ingest`` so that
``make validate`` works without the extra installed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from bs4 import BeautifulSoup, Tag

from herhealth_data.ingest.store import RawStore

__all__ = [
    "ESCALATION_PATTERNS",
    "INVISIBLE_SPACES",
    "ZERO_WIDTH",
    "DecodingError",
    "STRUCTURAL_NOISE",
    "CleanDocument",
    "Section",
    "SectionType",
    "classify_heading",
    "clean_html",
    "clean_store",
    "find_escalation_sentences",
    "find_locale_references",
    "is_link_list",
    "summarise",
    "write_content_lock",
]


class SectionType(StrEnum):
    """What a section is about, inferred from its heading."""

    SYMPTOMS = "symptoms"
    CAUSES = "causes"
    WHEN_TO_GET_HELP = "when_to_get_help"
    TREATMENT = "treatment"
    DIAGNOSIS = "diagnosis"
    OTHER = "other"


#: Whole elements that never contain body text.
STRUCTURAL_NOISE: Final[tuple[str, ...]] = (
    "script", "style", "nav", "header", "footer", "aside", "form",
    "noscript", "svg", "button", "iframe", "figure",
)

#: Substrings in class or id that mark a wrapper as chrome rather than content.
CHROME_MARKERS: Final[tuple[str, ...]] = (
    "cookie", "banner", "breadcrumb", "related", "feedback", "social", "share",
    "skip-link", "skiplink", "menu", "search", "sidebar", "site-nav", "subnav",
    "back-to-top", "newsletter", "subscribe", "alert-bar", "promo", "advert",
    "language-select", "print-only", "screen-reader", "visually-hidden",
)

#: Heading keywords, checked in order — the first match wins. Escalation is
#: checked first because "when to get urgent help" also contains "help".
HEADING_RULES: Final[tuple[tuple[SectionType, tuple[str, ...]], ...]] = (
    (SectionType.WHEN_TO_GET_HELP, (
        "when to get", "when to see", "when to call", "when to contact",
        "when to seek", "get medical help", "seek medical", "seek help",
        "urgent", "emergency", "call 999", "call 911", "immediate help",
        "see a doctor", "talk to a doctor", "see your doctor", "when should",
    )),
    (SectionType.SYMPTOMS, ("symptom", "sign of", "signs of", "signs and", "what are the signs")),
    (SectionType.CAUSES, ("cause", "risk factor", "who is at risk", "why does")),
    (SectionType.DIAGNOSIS, ("diagnos", "how is it found", "test for", "testing", "screening")),
    (SectionType.TREATMENT, ("treatment", "treated", "manage", "managing", "therapy", "medicine")),
)

#: Locale-specific service references. Recorded here, substituted at build time.
LOCALE_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    (r"\b999\b", "999"),
    (r"\b911\b", "911"),
    (r"\b111\b", "111"),
    (r"\bA&E\b", "A&E"),
    (r"\bemergency room\b", "emergency room"),
    (r"\bER\b", "ER"),
    (r"\bGP\b", "GP"),
    (r"\bNHS\b", "NHS"),
    (r"\burgent care\b", "urgent care"),
    (r"\bwalk-in cent(?:re|er)\b", "walk-in centre"),
)

#: Explicit escalation language, matched per SENTENCE rather than per heading.
#:
#: UK sources put this under a "When to get help" heading; US federal sources
#: bury it mid-paragraph ("see your doctor if the bleeding is heavy"). Heading
#: classification alone finds none of it, and red_flags.yaml may only be derived
#: from language like this — never inferred — so it has to be found where it
#: actually lives.
#:
#: Deliberately narrow. A phrase that merely mentions a doctor is not an
#: escalation instruction; these all express "act, and act now".
ESCALATION_PATTERNS: Final[tuple[str, ...]] = (
    r"\b(?:see|call|contact|tell|talk to|visit)\s+(?:your|a|the)\s+"
    r"(?:doctor|provider|healthcare provider|health care provider|nurse|clinician)\b",
    r"\bseek\s+(?:immediate|urgent|emergency|prompt|medical)\b",
    r"\bget\s+(?:immediate|urgent|emergency|medical)\s+(?:help|care|attention|treatment)\b",
    r"\bgo\s+to\s+(?:the\s+)?(?:emergency|hospital|er\b|a&e)\b",
    r"\bcall\s+9-?1-?1\b|\bcall\s+999\b|\bcall\s+111\b",
    r"\b(?:right away|immediately|as soon as possible|straight away|without delay)\b",
    r"\bemergency\b",
    r"\bmedical emergency\b",
)

#: Compiled once. Sentence splitting is deliberately crude — we only need
#: candidate sentences for a human to read, not perfect segmentation.
_ESCALATION_RE: Final[re.Pattern[str]] = re.compile("|".join(ESCALATION_PATTERNS), re.IGNORECASE)
_SENTENCE_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+")

HEADING_TAGS: Final[tuple[str, ...]] = ("h1", "h2", "h3", "h4")
TEXT_TAGS: Final[tuple[str, ...]] = ("p", "li", "dd", "td")

MIN_PARAGRAPH_CHARS: Final[int] = 25

#: Headings whose sections are link lists rather than guidance. MedlinePlus
#: rotates the PubMed articles it lists on every fetch, so including them in the
#: text hash reintroduces exactly the churn the text hash exists to remove.
#: They stay in the cleaned output — they are harmless there — but nothing is
#: ever quoted from them, so they do not count as content changing.
LINK_LIST_HEADINGS: Final[tuple[str, ...]] = (
    "journal articles",
    "clinical trials",
    "reference",
    "find an expert",
    "start here",
    "related issues",
    "statistics and research",
    "videos and tutorials",
    "patient handouts",
)


@dataclass(frozen=True, slots=True)
class Section:
    """One heading and the text beneath it."""

    heading: str
    section_type: SectionType
    paragraphs: tuple[str, ...]
    locale_references: tuple[str, ...]

    #: Sentences containing explicit escalation language, verbatim — so each is
    #: usable directly as a source_quote in red_flags.yaml.
    escalation_sentences: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


@dataclass(frozen=True, slots=True)
class CleanDocument:
    source_id: str
    slug: str
    sections: tuple[Section, ...]

    @property
    def text_hash(self) -> str:
        """sha256 of the extracted text — the drift signal that actually works.

        The raw-byte hash in ingest.lock.jsonl records exactly what arrived, but
        it is useless for detecting changed guidance: MedlinePlus rotates a
        cache-busting query string on a stylesheet link and NICHD regenerates
        Drupal render ids on every request, so a re-fetch changes almost every
        raw hash while no word of clinical content moves. A signal that fires
        every time is a signal nobody reads.

        This hashes headings and paragraphs of quotable sections only — link
        lists are skipped, since MedlinePlus rotates its PubMed article listings
        on every fetch. It changes when the words change, and not otherwise.
        """
        payload = "\n".join(
            f"{section.heading}\n" + "\n".join(section.paragraphs)
            for section in self.sections
            if not is_link_list(section.heading)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def of_type(self, section_type: SectionType) -> tuple[Section, ...]:
        return tuple(s for s in self.sections if s.section_type is section_type)

    @property
    def escalation_sentences(self) -> tuple[str, ...]:
        """Every escalation candidate in the document, deduplicated, in order."""
        found: list[str] = []
        for section in self.sections:
            for sentence in section.escalation_sentences:
                if sentence not in found:
                    found.append(sentence)
        return tuple(found)

    def to_json(self) -> str:
        return json.dumps(
            {
                "source_id": self.source_id,
                "slug": self.slug,
                "sections": [asdict(s) for s in self.sections],
            },
            indent=2,
            ensure_ascii=False,
        )


def is_link_list(heading: str) -> bool:
    """Whether a section is navigational rather than guidance."""
    lowered = heading.casefold()
    return any(marker in lowered for marker in LINK_LIST_HEADINGS)


def classify_heading(heading: str) -> SectionType:
    """Map a heading to a section type. First matching rule wins."""
    lowered = heading.casefold()
    for section_type, keywords in HEADING_RULES:
        if any(keyword in lowered for keyword in keywords):
            return section_type
    return SectionType.OTHER


def find_locale_references(text: str) -> tuple[str, ...]:
    """Locale-specific service references present in the text."""
    found = [label for pattern, label in LOCALE_PATTERNS if re.search(pattern, text)]
    return tuple(dict.fromkeys(found))


def find_escalation_sentences(paragraphs: Iterable[str]) -> tuple[str, ...]:
    """Sentences carrying explicit escalation language, verbatim.

    These are CANDIDATES for red_flags.yaml, not rules. A human still reads each
    one and decides whether it states a condition specific enough to key on.
    """
    found: list[str] = []
    for paragraph in paragraphs:
        for sentence in _SENTENCE_RE.split(paragraph):
            cleaned = sentence.strip()
            if cleaned and _ESCALATION_RE.search(cleaned) and cleaned not in found:
                found.append(cleaned)
    return tuple(found)


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    for element in soup.find_all(STRUCTURAL_NOISE):
        element.decompose()

    # Decomposing a wrapper invalidates its descendants, which are still in the
    # list we are walking. Skip anything already removed rather than touching a
    # detached node.
    for element in list(soup.find_all(True)):
        if not isinstance(element, Tag) or element.decomposed:
            continue
        classes = element.get("class") or []
        identifiers = " ".join([*classes, str(element.get("id") or "")]).casefold()
        if identifiers and any(marker in identifiers for marker in CHROME_MARKERS):
            element.decompose()


#: Space wrongly introduced *by us* before punctuation, or after an opening
#: bracket. Extracting with a separator puts a space between inline elements, so
#: markup like ``Obesity<a href="...">, weight gain`` comes out as
#: "Obesity , weight gain" — which is not what the page says.
_SPACE_BEFORE_PUNCTUATION: Final[re.Pattern[str]] = re.compile(r"\s+([,.;:!?%)\]])")
_SPACE_AFTER_OPENING: Final[re.Pattern[str]] = re.compile(r"([(\[])\s+")

#: Characters that look like a space but are not one. Web pages are full of
#: these, and they break verbatim matching invisibly: a quote containing a
#: non-breaking space will not be found by anyone searching the page for it.
#: Mapped to an ordinary space.
INVISIBLE_SPACES: Final[str] = (
    " "  # no-break space
    " "  # figure space
    " "  # thin space
    " "  # narrow no-break space
    "　"  # ideographic space
    "﻿"  # zero-width no-break space / stray BOM
)

#: Characters carrying no meaning in prose that survive extraction and would
#: make an otherwise identical quote fail to match. Removed entirely.
ZERO_WIDTH: Final[str] = (
    "​"  # zero-width space
    "‌"  # zero-width non-joiner
    "‍"  # zero-width joiner
    "­"  # soft hyphen
)

_INVISIBLE_TO_SPACE: Final[dict[int, str]] = {ord(c): " " for c in INVISIBLE_SPACES}
_ZERO_WIDTH_REMOVED: Final[dict[int, None]] = {ord(c): None for c in ZERO_WIDTH}

#: U+FFFD. Its presence means a decode already failed upstream, so the text is
#: lossy and cannot be trusted as a quote.
REPLACEMENT_CHARACTER: Final[str] = "�"


class DecodingError(ValueError):
    """Extracted text contains replacement characters, so it is already lossy."""


def _normalise(text: str) -> str:
    """Make text safely quotable without changing what it says.

    Every transformation here is either lossless or undoes something *we*
    introduced. None of them rewrites the source.

    1. **Unicode NFC.** The same visual character can be encoded as one
       codepoint or as a base plus a combining mark. Two quotes that look
       identical would then compare unequal, and a reviewer searching the page
       for one would not find the other. NFC picks one form consistently.
    2. **Invisible spaces to real spaces.** A non-breaking space looks exactly
       like a space and breaks verbatim matching silently — the worst kind of
       corruption, because nothing looks wrong.
    3. **Zero-width characters removed.** Soft hyphens and zero-width joiners
       carry no meaning in prose and only break matching.
    4. **Whitespace collapsed**, which is lossless for prose.
    5. **Our own extraction artifacts undone** — the space that appears before
       a comma when inline markup is separated. Restores what the page reads.

    Deliberately NOT done: converting em-dashes, curly quotes or accented
    characters to ASCII. Those are real source characters. "Rewriting symbols to
    look tidier" would make quotes that do not appear in the source, which is
    the exact failure the verbatim rule exists to prevent.

    Raises :class:`DecodingError` if the text already contains replacement
    characters, since that means a decode failed upstream and the text is lossy.
    """
    if REPLACEMENT_CHARACTER in text:
        raise DecodingError(
            "text contains U+FFFD replacement characters, so it was decoded with "
            "the wrong encoding upstream and cannot be trusted as a quote"
        )

    composed = unicodedata.normalize("NFC", text)
    spaced = composed.translate(_INVISIBLE_TO_SPACE).translate(_ZERO_WIDTH_REMOVED)
    collapsed = re.sub(r"\s+", " ", spaced).strip()
    tightened = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", collapsed)
    return _SPACE_AFTER_OPENING.sub(r"\1", tightened)


def clean_html(html: bytes | str) -> tuple[Section, ...]:
    """Strip boilerplate, split on headings, classify each section."""
    soup = BeautifulSoup(html, "lxml")
    _strip_boilerplate(soup)

    sections: list[Section] = []
    heading = "(untitled)"
    paragraphs: list[str] = []

    def flush() -> None:
        if not paragraphs:
            return
        joined = "\n".join(paragraphs)
        sections.append(
            Section(
                heading=heading,
                section_type=classify_heading(heading),
                paragraphs=tuple(paragraphs),
                locale_references=find_locale_references(joined),
                escalation_sentences=find_escalation_sentences(paragraphs),
            )
        )

    for element in soup.find_all([*HEADING_TAGS, *TEXT_TAGS]):
        text = _normalise(element.get_text(" "))
        if not text:
            continue
        if element.name in HEADING_TAGS:
            flush()
            heading, paragraphs = text, []
        elif len(text) >= MIN_PARAGRAPH_CHARS and text not in paragraphs:
            paragraphs.append(text)

    flush()
    return tuple(sections)


def clean_store(store: RawStore, out_dir: Path) -> list[CleanDocument]:
    """Clean every document in a snapshot and write the results."""
    documents: list[CleanDocument] = []
    for stored in store.documents():
        document = CleanDocument(
            source_id=stored.source_id,
            slug=stored.slug,
            sections=clean_html(stored.read_bytes()),
        )
        destination = out_dir / stored.source_id / f"{stored.slug}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document.to_json(), encoding="utf-8")
        documents.append(document)
    return documents


def write_content_lock(documents: Sequence[CleanDocument], path: Path, on_date: str) -> Path:
    """The tracked record of what the sources *say*.

    Companion to ``ingest.lock.jsonl``, which records what bytes arrived. Two
    locks because they answer different questions:

    * ``ingest.lock.jsonl`` — provenance. Exactly these bytes were retrieved
      from this URL on this date under this licence.
    * ``content.lock.jsonl`` — drift. The words changed, so a human should look
      at whether any evidence row still says what its source says.

    Only the second is worth alerting on. A changed row here means guidance
    moved and the rows citing that document need re-reading.
    """
    ordered = sorted(documents, key=lambda d: (d.source_id, d.slug))
    header = (
        "# Generated by `make clean`. Do not edit.\n"
        "# text_hash covers headings and paragraphs only, so it ignores markup\n"
        "# churn (cache-busting query strings, per-request render ids) and\n"
        "# changes only when the words change.\n"
        f"# cleaned_on: {on_date}\n"
    )
    body = "\n".join(
        json.dumps(
            {
                "source_id": d.source_id,
                "slug": d.slug,
                "text_hash": d.text_hash,
                "sections": len(d.sections),
                "escalation_sentences": len(d.escalation_sentences),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        for d in ordered
    )
    path.write_text(header + body + "\n", encoding="utf-8")
    return path


def summarise(documents: Iterable[CleanDocument]) -> str:
    lines = []
    for document in documents:
        counts: dict[str, int] = {}
        for section in document.sections:
            counts[section.section_type.value] = counts.get(section.section_type.value, 0) + 1
        shown = ", ".join(f"{n} {name}" for name, n in sorted(counts.items()))
        lines.append(f"  {document.source_id:<12} {document.slug:<28} {shown}")
    return "\n".join(lines)
