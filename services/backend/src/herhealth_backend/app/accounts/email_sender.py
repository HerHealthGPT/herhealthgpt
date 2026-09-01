"""The seam between Accounts and wherever a verification email actually goes.

One method per kind of message, not a generic "send an email" API — #12
(password reset) is the second one, added here rather than generalised into
a single parametrised method, the way ``CredentialKind`` grows one member at
a time rather than up front.

Two implementations. ``ConsoleEmailSender`` never touches a network, so the
test suite and any environment without AWS credentials can still run the
whole registration-and-verification flow end to end — it is what every
environment gets by default. It still renders the branded HTML templates and
writes them under ``services/backend/var/email-previews/`` so local dev can
open what would have been sent. ``SesEmailSender`` sends for real, through
the identity #6 provisioned; ``app/main.py`` selects it when
``HERHEALTH_EMAIL_SENDER=ses``.

Both are ``async def`` even though only one of them does anything
asynchronous — ``EmailSender`` is a Protocol callers ``await``, and a sync
method could not be swapped for a real network call later without changing
every call site.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import boto3
from anyio import to_thread

from herhealth_backend.app.accounts.email_preview import write_email_preview
from herhealth_backend.app.accounts.email_templates import (
    password_reset_email,
    verification_email,
)
from herhealth_backend.app.accounts.password_reset_policy import CODE_TTL as PASSWORD_RESET_CODE_TTL
from herhealth_backend.app.accounts.verification_code_policy import CODE_TTL

__all__ = ["EmailSender", "ConsoleEmailSender", "SesEmailSender"]

_logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_verification_code(self, *, to: str, code: str) -> None: ...
    async def send_password_reset_code(self, *, to: str, code: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _RenderedEmail:
    subject: str
    body_text: str
    body_html: str
    preview_kind: str


def _render_verification(code: str) -> _RenderedEmail:
    minutes = int(CODE_TTL.total_seconds() // 60)
    body_text, body_html = verification_email(code=code, minutes=minutes)
    return _RenderedEmail(
        subject="Your HerHealthGPT verification code",
        body_text=body_text,
        body_html=body_html,
        preview_kind="verification",
    )


def _render_password_reset(code: str) -> _RenderedEmail:
    minutes = int(PASSWORD_RESET_CODE_TTL.total_seconds() // 60)
    body_text, body_html = password_reset_email(code=code, minutes=minutes)
    return _RenderedEmail(
        subject="Reset your HerHealthGPT password",
        body_text=body_text,
        body_html=body_html,
        preview_kind="password-reset",
    )


class ConsoleEmailSender:
    """Logs the code and writes a styled HTML preview. Every environment's default."""

    async def _deliver(self, *, to: str, code: str, rendered: _RenderedEmail, log_label: str) -> None:
        preview_path = write_email_preview(kind=rendered.preview_kind, html=rendered.body_html)
        _logger.info("%s for %s: %s", log_label, to, code)
        _logger.info("styled email preview written to %s", preview_path)

    async def send_verification_code(self, *, to: str, code: str) -> None:
        await self._deliver(
            to=to,
            code=code,
            rendered=_render_verification(code),
            log_label="verification code",
        )

    async def send_password_reset_code(self, *, to: str, code: str) -> None:
        await self._deliver(
            to=to,
            code=code,
            rendered=_render_password_reset(code),
            log_label="password reset code",
        )


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

    def _send(self, *, to: str, subject: str, body_text: str, body_html: str) -> None:
        self._client.send_email(
            Source=SES_FROM_ADDRESS,
            Destination={"ToAddresses": [to]},
            ReplyToAddresses=[SES_REPLY_TO_ADDRESS],
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Charset": "UTF-8", "Data": body_text},
                    "Html": {"Charset": "UTF-8", "Data": body_html},
                },
            },
        )

    async def send_verification_code(self, *, to: str, code: str) -> None:
        rendered = _render_verification(code)
        await to_thread.run_sync(
            lambda: self._send(
                to=to,
                subject=rendered.subject,
                body_text=rendered.body_text,
                body_html=rendered.body_html,
            )
        )

    async def send_password_reset_code(self, *, to: str, code: str) -> None:
        rendered = _render_password_reset(code)
        await to_thread.run_sync(
            lambda: self._send(
                to=to,
                subject=rendered.subject,
                body_text=rendered.body_text,
                body_html=rendered.body_html,
            )
        )
