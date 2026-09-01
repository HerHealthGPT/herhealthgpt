"""The seam between Accounts and wherever a verification email actually goes.

One narrow method, not a generic "send an email" API — there is exactly one
kind of message Accounts sends today. When #12 (password reset) needs one
too, it gets its own method here, the way ``CredentialKind`` grows one member
at a time rather than up front.

Two implementations. ``ConsoleEmailSender`` never touches a network, so the
test suite and any environment without AWS credentials can still run the
whole registration-and-verification flow end to end — it is what every
environment gets by default. ``SesEmailSender`` sends for real, through the
identity #6 provisioned; ``app/main.py`` selects it when
``HERHEALTH_EMAIL_SENDER=ses``.

Both are ``async def`` even though only one of them does anything
asynchronous — ``EmailSender`` is a Protocol callers ``await``, and a sync
method could not be swapped for a real network call later without changing
every call site.
"""

from __future__ import annotations

import logging
from typing import Protocol

import boto3
from anyio import to_thread

from herhealth_backend.app.accounts.verification_code_policy import CODE_TTL

__all__ = ["EmailSender", "ConsoleEmailSender", "SesEmailSender"]

_logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification_code(self, *, to: str, code: str) -> None: ...


class ConsoleEmailSender:
    """Logs the code instead of emailing it. Every environment's default."""

    async def send_verification_code(self, *, to: str, code: str) -> None:
        _logger.info("verification code for %s: %s", to, code)


#: The identity #6 provisioned in SES — see
#: docs/runbooks/ses-production-access.md and the ses-email-infra project
#: memory. Not a secret (a sending address is meant to be public), and fixed
#: to this one AWS account and verified domain, so a constant here rather
#: than another environment variable to keep in sync with it.
SES_REGION = "us-east-1"
SES_FROM_ADDRESS = "HerHealthGPT <no-reply@herhealthgpt.org>"
SES_REPLY_TO_ADDRESS = "support@herhealthgpt.org"


class SesEmailSender:
    """Sends the code for real, through the SES identity #6 provisioned.

    boto3's SES client is synchronous; the send itself runs off the event
    loop through ``anyio.to_thread`` — the same reasoning ``passwords.py``
    offloads argon2id. A blocking network call in the request path would
    otherwise stall every other in-flight request on this process, including
    ``/health``.

    **Bounce and complaint handling is not built.** The production-access
    request in ``docs/runbooks/ses-production-access.md`` describes
    consuming SES's bounce/complaint notifications via SNS and suppressing
    further sends to an address that hard-bounced or complained, as though
    it exists — it does not yet. Said here rather than left only in a
    runbook nobody re-reads once access is granted: an address that bounces
    today is simply retried at the next resend, with no suppression.
    """

    def __init__(self, *, region: str = SES_REGION) -> None:
        self._client = boto3.client("ses", region_name=region)

    def _send(self, *, to: str, code: str) -> None:
        minutes = int(CODE_TTL.total_seconds() // 60)
        self._client.send_email(
            Source=SES_FROM_ADDRESS,
            Destination={"ToAddresses": [to]},
            ReplyToAddresses=[SES_REPLY_TO_ADDRESS],
            Message={
                "Subject": {"Data": "Your HerHealthGPT verification code", "Charset": "UTF-8"},
                "Body": {
                    "Text": {
                        "Charset": "UTF-8",
                        "Data": (
                            f"Your verification code is: {code}\n\n"
                            f"This code expires in {minutes} minutes. If you did not "
                            "request this, you can ignore this email."
                        ),
                    }
                },
            },
        )

    async def send_verification_code(self, *, to: str, code: str) -> None:
        await to_thread.run_sync(lambda: self._send(to=to, code=code))
