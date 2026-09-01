"""The seam between Accounts and Google's identity assertion.

``GoogleIdentity`` is deliberately the *only* thing a verifier can hand
back — a subject, an email, and whether Google itself asserts that email is
verified. Nothing else about a Google account is Accounts' business.

``GoogleOAuthTokenVerifier`` is the real implementation: it verifies an ID
token's signature and audience against Google, using the standard
``google-auth`` library. It needs ``HERHEALTH_GOOGLE_CLIENT_ID`` configured
(the OAuth client this backend was registered as) — no Google Cloud project
has been provisioned for this yet, the way #6 provisioned one for SES, so
this class is code-complete but has not been exercised against a real
Google token. Tests use their own double instead (see #11's own acceptance
criterion: "tests supply identities directly with no network call").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from anyio import to_thread
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from herhealth_backend.app.accounts.errors import GoogleSignInNotConfigured, GoogleTokenInvalid

__all__ = [
    "GoogleIdentity",
    "GoogleTokenVerifier",
    "GoogleOAuthTokenVerifier",
    "UnconfiguredGoogleTokenVerifier",
]


@dataclass(frozen=True)
class GoogleIdentity:
    #: Google's stable, opaque subject identifier. The join key #11 uses —
    #: never the email, which can change on the Google side.
    sub: str
    email: str
    #: Google's own claim that ``email`` is verified. Must be checked
    #: explicitly — Google does not always set it, and code that assumes it
    #: is true has protection that only looks real (#11's own framing).
    email_verified: bool


class GoogleTokenVerifier(Protocol):
    async def verify(self, id_token: str) -> GoogleIdentity: ...


class GoogleOAuthTokenVerifier:
    """Verifies a real Google ID token. See the module docstring."""

    def __init__(self, *, client_id: str) -> None:
        self._client_id = client_id

    def _verify(self, id_token: str) -> GoogleIdentity:
        try:
            claims = google_id_token.verify_oauth2_token(
                id_token, google_requests.Request(), self._client_id
            )
            sub = claims["sub"]
            email = claims["email"]
        except (GoogleAuthError, ValueError, KeyError) as exc:
            raise GoogleTokenInvalid() from exc
        return GoogleIdentity(
            sub=sub, email=email, email_verified=bool(claims.get("email_verified", False))
        )

    async def verify(self, id_token: str) -> GoogleIdentity:
        return await to_thread.run_sync(self._verify, id_token)


class UnconfiguredGoogleTokenVerifier:
    """What ``app.state.google_verifier`` is when ``HERHEALTH_GOOGLE_CLIENT_ID``
    is unset — every call raises :class:`GoogleSignInNotConfigured` rather
    than the app failing to boot over an optional feature no Google Cloud
    project exists for yet.
    """

    async def verify(self, id_token: str) -> GoogleIdentity:
        raise GoogleSignInNotConfigured()
