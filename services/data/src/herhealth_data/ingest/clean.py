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

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from bs4 import BeautifulSoup, Tag

from herhealth_data.ingest.store import RawStore

__all__ = [
    "ESCALATION_PATTERNS",
    "STRUCTURAL_NOISE",
    "CleanDocument",
    "Section",
    "SectionType",
    "classify_heading",
    "clean_html",
    "clean_store",
    "find_escalation_sentences",
    "find_locale_references",
    "summarise",
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


def _normalise(text: str) -> str:
    """Collapse whitespace. The only transformation applied to source text."""
    return re.sub(r"\s+", " ", text).strip()


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


def summarise(documents: Iterable[CleanDocument]) -> str:
    lines = []
    for document in documents:
        counts: dict[str, int] = {}
        for section in document.sections:
            counts[section.section_type.value] = counts.get(section.section_type.value, 0) + 1
        shown = ", ".join(f"{n} {name}" for name, n in sorted(counts.items()))
        lines.append(f"  {document.source_id:<12} {document.slug:<28} {shown}")
    return "\n".join(lines)
