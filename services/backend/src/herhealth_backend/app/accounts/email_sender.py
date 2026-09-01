"""The seam between Accounts and wherever a verification email actually goes.

One narrow method, not a generic "send an email" API — there is exactly one
kind of message Accounts sends today. When #12 (password reset) needs one
too, it gets its own method here, the way ``CredentialKind`` grows one member
at a time rather than up front.

``ConsoleEmailSender`` is the implementation #10 asks for: it never touches a
network, so the test suite and any environment without AWS credentials can
still run the whole registration-and-verification flow end to end. A
network-backed sender (SES, using the identity provisioned in #6) is future
work — swapping it in is changing what ``app.state.email_sender`` is
constructed with in ``main.py``, nothing that calls it needs to change.
"""

from __future__ import annotations

import logging
from typing import Protocol

__all__ = ["EmailSender", "ConsoleEmailSender"]

_logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    def send_verification_code(self, *, to: str, code: str) -> None: ...


class ConsoleEmailSender:
    """Logs the code instead of emailing it. The only sender this project ships today."""

    def send_verification_code(self, *, to: str, code: str) -> None:
        _logger.info("verification code for %s: %s", to, code)
