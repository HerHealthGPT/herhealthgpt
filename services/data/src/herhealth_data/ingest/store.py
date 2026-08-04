"""Where fetched documents go, and what we record about them.

Three things, all storage concerns:

* ``FetchRecord`` / ``FetchOutcome`` — provenance for one document.
* ``RawStore`` — the immutable ``raw/{source}/{date}/{slug}.html`` layout. The
  only writer, and the only place that knows the directory structure.
* ``write_lock`` / ``read_lock`` — the tracked lockfile.

**Immutability is enforced, not assumed:** :meth:`RawStore.save` refuses to
overwrite. A re-fetch on a later date is a different store at a different date,
so both snapshots survive and upstream changes stay diffable.

``raw/`` is gitignored, so ``ingest.lock.jsonl`` is the only record in version
control of what the knowledge base was built from — to source content what
``uv.lock`` is to dependencies. A changed ``content_hash`` means upstream
guidance moved, which should appear in a diff rather than silently altering the
evidence under a set of clinical rows.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final

from herhealth_data.ingest.config import Target

__all__ = [
    "MANIFEST_NAME",
    "FetchOutcome",
    "FetchRecord",
    "RawStore",
    "StoredDocument",
    "content_hash",
    "read_lock",
    "write_lock",
]

MANIFEST_NAME: Final[str] = "manifest.jsonl"
DOCUMENT_SUFFIX: Final[str] = ".html"
LOCK_COMMENT: Final[str] = "#"


def content_hash(body: bytes) -> str:
    """Full sha256 hex digest. Truncating it would defeat drift detection."""
    return hashlib.sha256(body).hexdigest()


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


class FetchOutcome(StrEnum):
    """What happened to one target. Ends up verbatim in the manifest."""

    FETCHED = "fetched"
    #: File existed. Raw content is immutable, so it was left alone.
    ALREADY_PRESENT = "already_present"
    #: Refused by a licence guard, before any request was made.
    EXCLUDED = "excluded"
    #: Not a usable 200. Nothing was written.
    FAILED = "failed"
    #: Dry run — nothing was requested.
    PLANNED = "planned"


USABLE_OUTCOMES: Final[frozenset[FetchOutcome]] = frozenset(
    {FetchOutcome.FETCHED, FetchOutcome.ALREADY_PRESENT}
)


@dataclass(frozen=True, slots=True)
class FetchRecord:
    """Provenance for one document.

    Carries the four fields the ingestion protocol requires on every record:
    ``url``, ``fetched_at``, ``content_hash``, ``licence``.
    """

    source_id: str
    slug: str
    url: str
    licence: str
    outcome: FetchOutcome
    fetched_at: str | None = None
    http_status: int | None = None
    content_hash: str | None = None
    bytes: int | None = None
    detail: str | None = None

    @property
    def is_usable(self) -> bool:
        """Whether a document for this record exists on disk."""
        return self.outcome in USABLE_OUTCOMES

    def with_(self, **changes: object) -> FetchRecord:
        return replace(self, **changes)  # type: ignore[arg-type]

    def to_json(self) -> str:
        """Optional fields are absent rather than null."""
        payload = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)


# --------------------------------------------------------------------------
# The raw store
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """A document already on disk. What the clean stage consumes."""

    source_id: str
    slug: str
    path: Path

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()


class RawStore:
    """One dated snapshot of fetched documents.

    Bound to a single date at construction, so "write today" and "read
    yesterday" are two objects rather than two arguments — and there is no way
    to write into a past snapshot by accident.
    """

    def __init__(self, root: Path, on_date: str) -> None:
        self.root = root
        self.on_date = on_date

    def __repr__(self) -> str:
        return f"RawStore({self.root}, {self.on_date!r})"

    def directory_for(self, source_id: str) -> Path:
        return self.root / source_id / self.on_date

    def path_for(self, target: Target) -> Path:
        return self.directory_for(target.source_id) / f"{target.slug}{DOCUMENT_SUFFIX}"

    def has(self, target: Target) -> bool:
        return self.path_for(target).is_file()

    def read(self, target: Target) -> bytes:
        return self.path_for(target).read_bytes()

    def documents(self) -> Iterator[StoredDocument]:
        """Every document in this snapshot, sorted for reproducible output.

        The clean stage iterates this instead of globbing, so the layout stays
        this class's business.
        """
        if not self.root.is_dir():
            return
        for source_directory in sorted(self.root.iterdir()):
            dated = source_directory / self.on_date
            if not dated.is_dir():
                continue
            for document in sorted(dated.glob(f"*{DOCUMENT_SUFFIX}")):
                yield StoredDocument(source_directory.name, document.stem, document)

    def save(self, target: Target, body: bytes) -> Path:
        """Write a document. Refuses to overwrite an existing one."""
        destination = self.path_for(target)
        if destination.exists():
            raise FileExistsError(
                f"raw content is immutable and {destination} already exists; "
                "fetch into a new dated store instead of overwriting"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        return destination

    def write_manifests(self, records: Sequence[FetchRecord]) -> list[Path]:
        """One manifest per source directory, so a snapshot is self-explaining."""
        by_source: dict[str, list[FetchRecord]] = {}
        for record in records:
            if record.is_usable:
                by_source.setdefault(record.source_id, []).append(record)

        written: list[Path] = []
        for source_id, source_records in sorted(by_source.items()):
            directory = self.directory_for(source_id)
            directory.mkdir(parents=True, exist_ok=True)
            manifest = directory / MANIFEST_NAME
            ordered = sorted(source_records, key=lambda r: r.slug)
            manifest.write_text("\n".join(r.to_json() for r in ordered) + "\n", encoding="utf-8")
            written.append(manifest)
        return written


# --------------------------------------------------------------------------
# The tracked lockfile
# --------------------------------------------------------------------------


def write_lock(records: Sequence[FetchRecord], path: Path, on_date: str) -> Path:
    """Write the lockfile. Sorted, so diffs stay readable.

    Only usable records are included: an excluded or failed document has no
    bytes, so listing it would imply content that does not exist.
    """
    usable = sorted((r for r in records if r.is_usable), key=lambda r: (r.source_id, r.slug))
    header = (
        f"{LOCK_COMMENT} Generated by `make fetch`. Do not edit.\n"
        f"{LOCK_COMMENT} raw/ is gitignored; this is the tracked record of what was fetched.\n"
        f"{LOCK_COMMENT} A changed content_hash means upstream guidance moved.\n"
        f"{LOCK_COMMENT} fetched_on: {on_date}\n"
    )
    body = "\n".join(
        json.dumps(
            {
                "source_id": r.source_id,
                "slug": r.slug,
                "url": r.url,
                "fetched_on": on_date,
                "content_hash": r.content_hash,
                "bytes": r.bytes,
                "licence": r.licence,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        for r in usable
    )
    path.write_text(header + body + "\n", encoding="utf-8")
    return path


def read_lock(path: Path) -> list[dict[str, object]]:
    """Parse the lockfile, ignoring comment lines."""
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith(LOCK_COMMENT)
    ]
