"""The one Windows event-loop workaround psycopg forces on us.

psycopg's async mode refuses Windows' default ``ProactorEventLoop`` and needs a
selector loop. Both the run entry point and the test harness have to apply this
before any async database work, so the reason lives here rather than as two
identical one-liners that could drift apart. A no-op everywhere but Windows,
which is why the Linux deploy target and CI never notice it.
"""

from __future__ import annotations

import asyncio
import sys

__all__ = ["use_selector_loop_on_windows"]


def use_selector_loop_on_windows() -> None:
    """Select a psycopg-compatible event loop policy on Windows; a no-op elsewhere."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
