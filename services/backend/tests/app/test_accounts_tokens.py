"""Access-token issue/verify, and refresh-token generation/hashing — pure functions, no database."""

from __future__ import annotations

from datetime import timedelta

import pytest

from herhealth_backend.app.accounts.errors import InvalidAccessToken
from herhealth_backend.app.accounts.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
    read_access_token,
)

_SECRET = "unit-test-secret"


def test_read_access_token_returns_the_issued_user_id() -> None:
    token = issue_access_token(_SECRET, user_id="a-user-id")

    assert read_access_token(_SECRET, token) == "a-user-id"


def test_read_access_token_rejects_a_token_signed_with_a_different_secret() -> None:
    token = issue_access_token(_SECRET, user_id="a-user-id")

    with pytest.raises(InvalidAccessToken):
        read_access_token("a-different-secret", token)


def test_read_access_token_rejects_a_tampered_token() -> None:
    token = issue_access_token(_SECRET, user_id="a-user-id")
    # A middle character, not the last: trailing base64 characters can carry
    # fewer effective bits, and flipping one there can round-trip unchanged.
    middle = len(token) // 2
    flipped = "a" if token[middle] != "a" else "b"
    tampered = token[:middle] + flipped + token[middle + 1 :]

    with pytest.raises(InvalidAccessToken):
        read_access_token(_SECRET, tampered)


def test_read_access_token_rejects_a_token_older_than_its_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = issue_access_token(_SECRET, user_id="a-user-id")

    # A negative TTL makes even a token issued an instant ago older than
    # allowed, without sleeping through the real 15-minute window.
    monkeypatch.setattr(
        "herhealth_backend.app.accounts.tokens.ACCESS_TOKEN_TTL", timedelta(seconds=-1)
    )

    with pytest.raises(InvalidAccessToken):
        read_access_token(_SECRET, token)


def test_generate_refresh_token_returns_distinct_high_entropy_values() -> None:
    first = generate_refresh_token()
    second = generate_refresh_token()

    assert first != second
    assert len(first) >= 32


def test_hash_refresh_token_is_deterministic_and_does_not_leak_the_raw_value() -> None:
    raw = generate_refresh_token()

    digest = hash_refresh_token(raw)

    assert hash_refresh_token(raw) == digest
    assert raw not in digest
