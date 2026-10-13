"""Resolve a passage back to the page it was actually fetched from.

``Passage`` carries ``source_id`` and ``slug`` but no url — the clean stage
never wrote one through (see ``herhealth_data.ingest.clean``). The url does
survive, though, in ``services/data/ingest.lock.jsonl``: the tracked record
of what ``make fetch`` retrieved, kept in version control precisely because
``raw/`` is gitignored. That file is keyed on exactly ``(source_id, slug)``,
which is what a passage has, so a lookup built from it closes the gap
without touching the ingestion pipeline or re-fetching anything.

Read once per index build. The url is written into each passage's record in
``passages.jsonl``, so nothing downstream needs the lock file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

__all__ = ["SourceUrlIndex", "load_source_urls", "resolve_url"]

logger = logging.getLogger(__name__)

#: Comment lines in the lock file, which is JSONL with a header block.
_COMMENT_PREFIX = "#"

#: (source_id, slug) -> url
SourceUrlIndex = dict[tuple[str, str], str]


def load_source_urls(lock_path: Path) -> SourceUrlIndex:
    """Build the lookup, or return an empty one.

    A missing or malformed lock file is logged and treated as "no urls
    known", never raised: a citation without a link is degraded, but a
    retrieval service that refuses to start because a provenance file moved
    is worse. Every caller already treats ``url`` as optional.
    """
    if not lock_path.is_file():
        logger.warning("no ingest lock at %s — citations will have no links", lock_path)
        return {}

    index: SourceUrlIndex = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(_COMMENT_PREFIX):
            continue
        try:
            record = json.loads(stripped)
            index[(record["source_id"], record["slug"])] = record["url"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # One unreadable row should not cost every other row its link.
            logger.warning("skipping unreadable ingest.lock row: %.80s", stripped)

    logger.info("resolved %d source url(s) from %s", len(index), lock_path)
    return index


# ---------------------------------------------------------------------------
# Evidence-statement fallback
# ---------------------------------------------------------------------------
#
# An evidence-statement passage is synthesised from an ``evidence.csv`` row,
# not fetched, so its slug is ``evidence/<condition>/<feature>/<value>`` and
# can never appear in the lock. Its row records ``source_id`` but not which
# page of that source the quote was read from — that identity is recorded
# nowhere in the authoring chain, which is the real defect.
#
# Until it is recorded (index ``provenance.load_corpus`` per document, emit
# the document slug from ``verify-quotes``, carry a ``source_slug`` column
# through ``make evidence``), this resolves the citation to *the source's own
# page for that condition*.
#
# **That is a weaker claim than the exact-slug path makes**, and callers
# should read it that way: the link lands on the page this source publishes
# about this condition, not on the page the sentence was verified against.
# The two are the same page in the ordinary case and this is how the rows
# were authored, but it is an inference, not provenance.

#: Condition ids the sources file under a different slug. Hand-checked
#: against every slug in ingest.lock.jsonl on 2026-09-17; a wrong entry here
#: puts a worried user on the wrong health page, so nothing is added without
#: reading the lock first.
_CONDITION_PAGE_ALIASES: dict[str, str] = {
    "uterine_fibroids": "fibroids",
    "perimenopause": "menopause",
    "normal_variation": "menstruation",
}

#: Where one source files a condition differently from the others.
#: Checked the same way, and consulted before :data:`_CONDITION_PAGE_ALIASES`.
_PER_SOURCE_PAGE_ALIASES: dict[tuple[str, str], str] = {
    # MedlinePlus has no general STI topic page; its STI rows were authored
    # from the chlamydia page, which is the one it publishes.
    ("medlineplus", "sexually_transmitted_infection"): "chlamydia",
    # NHS files cycle-length content under irregular periods; it publishes no
    # general "menstruation" page the way MedlinePlus and womenshealth do.
    ("nhs", "normal_variation"): "irregular_periods",
}


def resolve_url(
    index: SourceUrlIndex,
    source_id: str,
    slug: str,
    condition_id: str | None = None,
) -> str | None:
    """The page a citation should open, or ``None``.

    Tried in order, strongest first:

    1. ``(source_id, slug)`` — the page this passage was actually fetched
       from. Provenance.
    2. ``(source_id, condition_id)`` — the source's page for this condition.
       An inference; see the module note above.
    3. The same, through the alias tables, for conditions filed under another
       slug.

    ``None`` when nothing matches, which the UI renders as an unlinked
    source name rather than inventing a destination.
    """
    exact = index.get((source_id, slug))
    if exact is not None:
        return exact
    if not condition_id:
        return None
    direct = index.get((source_id, condition_id))
    if direct is not None:
        return direct
    per_source = _PER_SOURCE_PAGE_ALIASES.get((source_id, condition_id))
    if per_source is not None and (url := index.get((source_id, per_source))):
        return url
    alias = _CONDITION_PAGE_ALIASES.get(condition_id)
    if alias is not None:
        return index.get((source_id, alias))
    return None
