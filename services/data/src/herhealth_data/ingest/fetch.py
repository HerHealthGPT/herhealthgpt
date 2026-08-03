"""Fetch source documents into an immutable, dated, hash-recorded store.

Design rules, all from the ingestion protocol and none of them optional:

**Raw content is immutable.** Documents land in ``raw/{source}/{YYYY-MM-DD}/``
and an existing file is never overwritten. Re-running on the same day is a
no-op; re-fetching on a later day creates a new dated directory so upstream
changes are diffable rather than silently applied.

**Licence guards run before the request, not after.** A URL matching an
excluded path fragment is refused without a network call being made. The
MedlinePlus ``/ency/`` exclusion is a licence term expressed as code, because a
rule that lives only in someone's memory is a rule that eventually gets broken.

**Nothing fetches by accident.** The default is a dry run that prints the plan.
Network access requires an explicit flag.

**Tests never hit the network.** Every function that touches HTTP takes the
transport as an argument, so tests inject a fake and the real one is unused.

``raw/`` is gitignored. ``ingest_targets.yaml`` and ``ingest.lock.jsonl`` are
tracked, and together they are what makes a fetch reproducible: the targets say
what to get, the lock records what was got and its hash.
"""

from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Final

import certifi
import yaml

__all__ = [
    "ExcludedByLicence",
    "FetchOutcome",
    "FetchPlan",
    "FetchRecord",
    "Target",
    "Transport",
    "fetch_all",
    "http_get",
    "load_plan",
    "write_lock",
]

#: Identifies us honestly. An academic project should not pretend to be a browser.
#: Sources whose edge blocks this can override it per source in the targets file.
USER_AGENT: Final[str] = (
    "HerHealthGPT-research/0.1 (academic capstone; contact via repository)"
)

REQUEST_TIMEOUT_SECONDS: Final[float] = 40.0

MANIFEST_NAME: Final[str] = "manifest.jsonl"


class ExcludedByLicence(Exception):
    """Raised when a URL is barred by a licence guard. Never caught silently."""


@dataclass(frozen=True, slots=True)
class Target:
    """One document we intend to fetch."""

    source_id: str
    slug: str
    url: str
    licence: str

    def destination(self, raw_dir: Path, on_date: str) -> Path:
        return raw_dir / self.source_id / on_date / f"{self.slug}.html"


@dataclass(frozen=True, slots=True)
class FetchPlan:
    targets: tuple[Target, ...]
    #: source_id -> path fragments that must never be fetched from it.
    excluded_path_fragments: Mapping[str, tuple[str, ...]]
    #: source_id -> user agent, for sources whose edge rejects the default.
    user_agents: Mapping[str, str] = field(default_factory=dict)

    def excluded_reason(self, target: Target) -> str | None:
        for fragment in self.excluded_path_fragments.get(target.source_id, ()):
            if fragment in target.url:
                return fragment
        return None

    def user_agent_for(self, target: Target) -> str:
        return self.user_agents.get(target.source_id, USER_AGENT)


class FetchOutcome:
    """What happened to one target. Strings, because they end up in the lock."""

    FETCHED = "fetched"
    #: The file already existed. Raw content is immutable, so it was left alone.
    ALREADY_PRESENT = "already_present"
    #: Refused by a licence guard, before any request.
    EXCLUDED = "excluded"
    #: The server did not return 200. Nothing was written.
    FAILED = "failed"
    #: Dry run: nothing was requested.
    PLANNED = "planned"


@dataclass(frozen=True, slots=True)
class FetchRecord:
    """Provenance for one document. Written to the manifest and the lock."""

    source_id: str
    slug: str
    url: str
    licence: str
    outcome: str
    fetched_at: str | None = None
    http_status: int | None = None
    content_hash: str | None = None
    bytes: int | None = None
    detail: str | None = None

    def to_json(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)


#: (url, user_agent) -> (http_status, body). Injected so tests never reach the
#: network — the real implementation below is unused by the test suite.
Transport = Callable[[str, str], tuple[int, bytes]]


@cache
def _ssl_context() -> ssl.SSLContext:
    """Trust store for outbound HTTPS.

    uv installs a python-build-standalone interpreter, which ships without a CA
    bundle, so ``urllib`` fails certificate verification against every host.
    certifi supplies the bundle. Verification is never disabled.
    """
    return ssl.create_default_context(cafile=certifi.where())


def http_get(url: str, user_agent: str = USER_AGENT) -> tuple[int, bytes]:
    """The only function in this package that opens a socket."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS, context=_ssl_context()
        ) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as error:
        return int(error.code), b""
    except urllib.error.URLError as error:
        raise RuntimeError(f"could not reach {url}: {error.reason}") from error


def load_plan(path: Path) -> FetchPlan:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = tuple(
        Target(
            source_id=str(d["source_id"]),
            slug=str(d["slug"]),
            url=str(d["url"]),
            licence=str(d["licence"]).strip(),
        )
        for d in raw.get("documents", [])
    )
    exclusions = {
        str(source): tuple(str(f) for f in fragments)
        for source, fragments in (raw.get("excluded_path_fragments") or {}).items()
    }
    user_agents = {
        str(source): str(agent).strip()
        for source, agent in (raw.get("user_agents") or {}).items()
    }
    _reject_duplicate_targets(targets)
    return FetchPlan(
        targets=targets,
        excluded_path_fragments=exclusions,
        user_agents=user_agents,
    )


def _reject_duplicate_targets(targets: Sequence[Target]) -> None:
    seen = [(t.source_id, t.slug) for t in targets]
    duplicates = sorted({s for s in seen if seen.count(s) > 1})
    if duplicates:
        shown = ", ".join(f"{source}/{slug}" for source, slug in duplicates)
        raise ValueError(f"duplicate targets would overwrite each other: {shown}")


def fetch_all(
    plan: FetchPlan,
    raw_dir: Path,
    on_date: str,
    transport: Transport,
    *,
    dry_run: bool = True,
) -> list[FetchRecord]:
    """Fetch every target that is permitted and not already present.

    Returns one record per target, in plan order, whatever happened to it.
    """
    records: list[FetchRecord] = []
    for target in plan.targets:
        records.append(_fetch_one(plan, target, raw_dir, on_date, transport, dry_run=dry_run))

    if not dry_run:
        _write_manifests(records, raw_dir, on_date)
    return records


def _fetch_one(
    plan: FetchPlan,
    target: Target,
    raw_dir: Path,
    on_date: str,
    transport: Transport,
    *,
    dry_run: bool,
) -> FetchRecord:
    base = FetchRecord(
        source_id=target.source_id,
        slug=target.slug,
        url=target.url,
        licence=target.licence,
        outcome=FetchOutcome.PLANNED,
    )

    fragment = plan.excluded_reason(target)
    if fragment is not None:
        return _replace(
            base,
            outcome=FetchOutcome.EXCLUDED,
            detail=f"licence guard: url contains {fragment!r}",
        )

    destination = target.destination(raw_dir, on_date)
    if destination.exists():
        body = destination.read_bytes()
        return _replace(
            base,
            outcome=FetchOutcome.ALREADY_PRESENT,
            content_hash=_sha256(body),
            bytes=len(body),
            detail="raw content is immutable; existing file left untouched",
        )

    if dry_run:
        return base

    status, body = transport(target.url, plan.user_agent_for(target))
    if status != 200 or not body:
        return _replace(
            base,
            outcome=FetchOutcome.FAILED,
            http_status=status,
            fetched_at=_now(),
            detail="nothing written",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    return _replace(
        base,
        outcome=FetchOutcome.FETCHED,
        http_status=status,
        fetched_at=_now(),
        content_hash=_sha256(body),
        bytes=len(body),
    )


def _write_manifests(records: Sequence[FetchRecord], raw_dir: Path, on_date: str) -> None:
    """One manifest per source directory, rewritten from the current records."""
    by_source: dict[str, list[FetchRecord]] = {}
    for record in records:
        if record.outcome in {FetchOutcome.FETCHED, FetchOutcome.ALREADY_PRESENT}:
            by_source.setdefault(record.source_id, []).append(record)

    for source_id, source_records in by_source.items():
        directory = raw_dir / source_id / on_date
        directory.mkdir(parents=True, exist_ok=True)
        lines = "\n".join(r.to_json() for r in source_records)
        (directory / MANIFEST_NAME).write_text(lines + "\n", encoding="utf-8")


def write_lock(records: Sequence[FetchRecord], lock_path: Path, on_date: str) -> None:
    """Write the tracked lockfile.

    ``raw/`` is gitignored, so this is the only record of what was fetched that
    survives in version control. A changed hash on a later fetch means upstream
    guidance moved, which is a thing worth seeing in a diff.
    """
    usable = [
        r
        for r in records
        if r.outcome in {FetchOutcome.FETCHED, FetchOutcome.ALREADY_PRESENT}
    ]
    header = (
        "# Generated by `make fetch`. Do not edit.\n"
        "# raw/ is gitignored; this is the tracked record of what was fetched.\n"
        f"# fetched_on: {on_date}\n"
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
        for r in sorted(usable, key=lambda r: (r.source_id, r.slug))
    )
    lock_path.write_text(header + body + "\n", encoding="utf-8")


def _replace(record: FetchRecord, **changes: object) -> FetchRecord:
    return replace(record, **changes)  # type: ignore[arg-type]


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
