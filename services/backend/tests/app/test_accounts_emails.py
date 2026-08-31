"""Two spellings of one address must normalise to the same stored form."""

from __future__ import annotations

from herhealth_backend.app.accounts.emails import normalize_email


def test_normalize_email_lowercases() -> None:
    assert normalize_email("Woman@Example.com") == "woman@example.com"


def test_normalize_email_strips_surrounding_whitespace() -> None:
    assert normalize_email("  woman@example.com  ") == "woman@example.com"


def test_normalize_email_two_spellings_match() -> None:
    assert normalize_email(" Woman@Example.com") == normalize_email("woman@example.com ")
