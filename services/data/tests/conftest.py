"""Fixtures for the ingest tests.

Helper functions live in ingest_factories.py, not here: see the note there.
Only fixtures belong in conftest, because pytest resolves those per directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ingest_factories import DATE

from herhealth_data.ingest import RawStore


@pytest.fixture
def store(tmp_path: Path) -> RawStore:
    return RawStore(tmp_path, DATE)
