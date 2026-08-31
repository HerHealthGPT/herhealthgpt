"""How long a session lives before it needs re-proving.

Three independent limits, each a policy call rather than something derived
from a source, the way the clinical thresholds in ``weights.yaml`` are:

- ``ACCESS_TOKEN_TTL`` is how long a stolen access token stays dangerous —
  it cannot be revoked (see ``tokens.py`` and ``services/backend/CONTEXT.md``),
  so this is the only thing bounding it.
- ``REFRESH_TOKEN_TTL`` is the longest a woman can go without signing in
  again, regardless of activity.
- ``IDLE_TIMEOUT`` is the "agreed idle period" #9 asks for: leave the service
  untouched for this long and the next refresh fails even though the
  absolute lifetime has not run out.
"""

from __future__ import annotations

from datetime import timedelta

__all__ = ["ACCESS_TOKEN_TTL", "REFRESH_TOKEN_TTL", "IDLE_TIMEOUT"]

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
IDLE_TIMEOUT = timedelta(days=7)
