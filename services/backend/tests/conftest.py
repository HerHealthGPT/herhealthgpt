"""Fixtures for the triage tests. Helpers live in triage_factories.py."""

from __future__ import annotations

import pytest
from triage_factories import build

from herhealth_backend.triage.engine import TriageEngine


@pytest.fixture
def engine() -> TriageEngine:
    return TriageEngine(build())
