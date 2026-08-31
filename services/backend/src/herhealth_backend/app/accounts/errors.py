"""Domain errors raised by the Accounts use cases, translated to HTTP in routes.py."""

from __future__ import annotations

__all__ = ["EmailAlreadyRegistered"]


class EmailAlreadyRegistered(Exception):
    """Raised when registering an address that already has a user.

    Carries no detail about the existing user — not whether she is verified,
    not when she registered — because the route this feeds must not reveal
    anything about her beyond the fact that this registration attempt failed.
    """
