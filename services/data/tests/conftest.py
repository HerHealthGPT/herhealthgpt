"""Shared factories for the ingest tests.

Every transport here is fake. The real one is never imported by a test, which is
how "tests never hit the network" stays true without anyone policing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from herhealth_data.ingest import FetchPlan, RawStore, Target

DATE = "2026-08-03"

DEFAULT_BODY = b"<html>content</html>"


def make_target(**overrides: str) -> Target:
    values: dict[str, str] = {
        "source_id": "nichd",
        "slug": "pcos",
        "url": "https://www.nichd.nih.gov/health/topics/pcos",
        "licence": "US federal government work, public domain",
    }
    values.update(overrides)
    return Target(**values)  # type: ignore[arg-type]


def make_plan(
    *targets: Target,
    exclusions: dict[str, tuple[str, ...]] | None = None,
    user_agents: dict[str, str] | None = None,
) -> FetchPlan:
    return FetchPlan(
        targets=targets or (make_target(),),
        excluded_path_fragments=exclusions or {},
        user_agents=user_agents or {},
    )


def responds(body: bytes = DEFAULT_BODY, status: int = 200):  # noqa: ANN201
    """A transport that always returns the same response."""

    def transport(url: str, user_agent: str) -> tuple[int, bytes]:
        return status, body

    return transport


def recording(sink: list[tuple[str, str]], body: bytes = DEFAULT_BODY):  # noqa: ANN201
    """A transport that records every (url, user_agent) it is called with."""

    def transport(url: str, user_agent: str) -> tuple[int, bytes]:
        sink.append((url, user_agent))
        return 200, body

    return transport


def forbidden(url: str, user_agent: str = "") -> tuple[int, bytes]:
    """A transport that fails the test if it is called at all."""
    raise AssertionError(f"the network must not be touched, but {url} was requested")


@pytest.fixture
def store(tmp_path: Path) -> RawStore:
    return RawStore(tmp_path, DATE)
