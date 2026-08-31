"""``session_secret`` reading and validating ``HERHEALTH_SESSION_SECRET``."""

from __future__ import annotations

import pytest

from herhealth_backend.app.config import SESSION_SECRET_ENV, session_secret


def test_session_secret_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SESSION_SECRET_ENV, raising=False)

    with pytest.raises(RuntimeError):
        session_secret()


def test_session_secret_raises_when_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SESSION_SECRET_ENV, "too-short")

    with pytest.raises(RuntimeError):
        session_secret()


def test_session_secret_returns_a_long_enough_value(monkeypatch: pytest.MonkeyPatch) -> None:
    value = "a" * 32
    monkeypatch.setenv(SESSION_SECRET_ENV, value)

    assert session_secret() == value
