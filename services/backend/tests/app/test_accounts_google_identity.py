"""``GoogleOAuthTokenVerifier`` and ``UnconfiguredGoogleTokenVerifier`` — no network here.

``verify_oauth2_token`` is mocked throughout: it is Google's own library
function that would otherwise fetch Google's public certs over the network,
exactly what #11's own acceptance criterion asks the test suite to avoid.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from google.auth.exceptions import GoogleAuthError

from herhealth_backend.app.accounts.errors import GoogleSignInNotConfigured, GoogleTokenInvalid
from herhealth_backend.app.accounts.google_identity import (
    GoogleOAuthTokenVerifier,
    UnconfiguredGoogleTokenVerifier,
)

_PATCH_TARGET = "herhealth_backend.app.accounts.google_identity.google_id_token.verify_oauth2_token"


async def test_google_oauth_verifier_returns_the_identity_from_the_token() -> None:
    with patch(_PATCH_TARGET) as mock_verify:
        mock_verify.return_value = {
            "sub": "12345",
            "email": "woman@example.com",
            "email_verified": True,
        }
        verifier = GoogleOAuthTokenVerifier(client_id="a-client-id")

        identity = await verifier.verify("a-real-token-would-go-here")

    assert identity.sub == "12345"
    assert identity.email == "woman@example.com"
    assert identity.email_verified is True
    mock_verify.assert_called_once()
    assert mock_verify.call_args.args[0] == "a-real-token-would-go-here"
    assert mock_verify.call_args.args[2] == "a-client-id"


async def test_google_oauth_verifier_defaults_email_verified_to_false_when_absent() -> None:
    """Google does not always set this claim — #11's own framing for why it
    must be checked explicitly rather than assumed true."""
    with patch(_PATCH_TARGET) as mock_verify:
        mock_verify.return_value = {"sub": "12345", "email": "woman@example.com"}
        verifier = GoogleOAuthTokenVerifier(client_id="a-client-id")

        identity = await verifier.verify("a-token")

    assert identity.email_verified is False


async def test_google_oauth_verifier_rejects_an_invalid_token() -> None:
    with patch(_PATCH_TARGET) as mock_verify:
        mock_verify.side_effect = GoogleAuthError("token expired")
        verifier = GoogleOAuthTokenVerifier(client_id="a-client-id")

        with pytest.raises(GoogleTokenInvalid):
            await verifier.verify("an-expired-token")


async def test_google_oauth_verifier_rejects_a_malformed_token() -> None:
    with patch(_PATCH_TARGET) as mock_verify:
        mock_verify.side_effect = ValueError("not a valid JWT")
        verifier = GoogleOAuthTokenVerifier(client_id="a-client-id")

        with pytest.raises(GoogleTokenInvalid):
            await verifier.verify("not-a-token")


async def test_google_oauth_verifier_rejects_a_token_missing_required_claims() -> None:
    with patch(_PATCH_TARGET) as mock_verify:
        mock_verify.return_value = {"sub": "12345"}  # no email claim at all
        verifier = GoogleOAuthTokenVerifier(client_id="a-client-id")

        with pytest.raises(GoogleTokenInvalid):
            await verifier.verify("a-token")


async def test_unconfigured_verifier_always_raises() -> None:
    verifier = UnconfiguredGoogleTokenVerifier()

    with pytest.raises(GoogleSignInNotConfigured):
        await verifier.verify("anything")
