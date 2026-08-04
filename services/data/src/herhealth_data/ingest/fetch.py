"""Fetching: the network, and the policy that decides what to request.

``http_get`` is the only function in the whole package that opens a socket.
Everything else takes a ``Transport`` argument, so the test suite injects a fake
and the real one is never exercised by a test. "Tests never hit the network" is
therefore structural rather than a rule people must remember.

The order of checks in :func:`_fetch_one` is the policy, and it matters:

1. **Licence guard** — before anything else, and before any network call. A
   barred URL is never requested, so a licence rule cannot be violated by a
   retry, a redirect, or a bug further down.
2. **Already present** — raw content is immutable, so leave it and say so.
3. **Dry run** — the default. Nothing is requested unless the caller opts in.
4. **Fetch** — and only a real 200 with a body is written, so a 404 error page
   can never sit in ``raw/`` masquerading as content.
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from functools import cache
from typing import Final

import certifi

from herhealth_data.ingest.config import USER_AGENT, FetchPlan, Target, Transport
from herhealth_data.ingest.robots import RobotsPolicy
from herhealth_data.ingest.store import FetchOutcome, FetchRecord, RawStore, content_hash

__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "RobotsPolicy",
    "Transport",
    "fetch_all",
    "http_get",
    "utc_today",
]

REQUEST_TIMEOUT_SECONDS: Final[float] = 40.0

def utc_today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@cache
def _ssl_context() -> ssl.SSLContext:
    """Trust store for outbound HTTPS.

    uv installs a python-build-standalone interpreter, which ships without a CA
    bundle, so ``urllib`` fails certificate verification against every host.
    certifi supplies it. Verification is never disabled — if this raises, fix
    the trust store.
    """
    return ssl.create_default_context(cafile=certifi.where())


def http_get(url: str, user_agent: str = USER_AGENT) -> tuple[int, bytes]:
    """GET a URL. The only socket in this package.

    An HTTP error status is returned rather than raised, because a 404 is data
    the caller records. Only transport-level failure — DNS, TLS, refused —
    raises.
    """
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


def fetch_all(
    plan: FetchPlan,
    store: RawStore,
    transport: Transport,
    *,
    dry_run: bool = True,
    robots: RobotsPolicy | None = None,
) -> list[FetchRecord]:
    """Process every target in the plan.

    Returns one record per target, in plan order, whatever happened to it —
    including refused and failed ones, because a report that omits them is a
    report that hides them.
    """
    records = [
        _fetch_one(plan, target, store, transport, dry_run=dry_run, robots=robots)
        for target in plan.targets
    ]
    if not dry_run:
        store.write_manifests(records)
    return records


def _fetch_one(
    plan: FetchPlan,
    target: Target,
    store: RawStore,
    transport: Transport,
    *,
    dry_run: bool,
    robots: RobotsPolicy | None = None,
) -> FetchRecord:
    record = FetchRecord(
        source_id=target.source_id,
        slug=target.slug,
        url=target.url,
        licence=target.licence,
        outcome=FetchOutcome.PLANNED,
    )

    # 1. Licence guard, before any request.
    fragment = plan.excluded_reason(target)
    if fragment is not None:
        return record.with_(
            outcome=FetchOutcome.EXCLUDED,
            detail=f"licence guard: url contains {fragment!r}",
        )

    # 2. robots.txt, also before any request for the document itself.
    if robots is not None:
        refusal = robots.reason_if_disallowed(target.url, plan.user_agent_for(target))
        if refusal is not None:
            return record.with_(outcome=FetchOutcome.EXCLUDED, detail=refusal)

    # 3. Immutability: never overwrite what is already there.
    if store.has(target):
        body = store.read(target)
        return record.with_(
            outcome=FetchOutcome.ALREADY_PRESENT,
            content_hash=content_hash(body),
            bytes=len(body),
            detail="raw content is immutable; existing file left untouched",
        )

    # 4. Nothing fetches by accident.
    if dry_run:
        return record

    # 5. Fetch, and write only a usable response.
    status, body = transport(target.url, plan.user_agent_for(target))
    if status != 200 or not body:
        return record.with_(
            outcome=FetchOutcome.FAILED,
            http_status=status,
            fetched_at=_utc_now(),
            detail="nothing written",
        )

    store.save(target, body)
    return record.with_(
        outcome=FetchOutcome.FETCHED,
        http_status=status,
        fetched_at=_utc_now(),
        content_hash=content_hash(body),
        bytes=len(body),
    )
