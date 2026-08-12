"""The backend's runtime layer: the FastAPI application and its database.

Everything the process needs to boot, connect to PostgreSQL and answer a
request lives here. The triage core deliberately imports none of it — a triage
run has no server, no database and no user — and a test enforces that boundary
(``tests/test_boundary.py``). The dependency points one way: this layer may use
Triage; Triage may never reach back into here.
"""

from __future__ import annotations

from herhealth_backend.app.db import Database
from herhealth_backend.app.main import create_app

__all__ = ["Database", "create_app"]
