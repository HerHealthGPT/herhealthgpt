"""Resolve a passage back to the page it was actually fetched from.

``Passage`` carries ``source_id`` and ``slug`` but no url — the clean stage
never wrote one through (see ``herhealth_data.ingest.clean``). The url does
survive, though, in ``services/data/ingest.lock.jsonl``: the tracked record
of what ``make fetch`` retrieved, kept in version control precisely because
``raw/`` is gitignored. That file is keyed on exactly ``(source_id, slug)``,
which is what a passage has, so a lookup built from it closes the gap
without touching the ingestion pipeline or re-fetching anything.

Read once at start-up. The file is small (tens of records) and only changes
when ``make fetch`` runs, which is not while this service is up.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

__all__ = ["SourceUrlIndex", "load_source_urls"]

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
