"""``verification_codes``: generation, hashing, constant-time comparison.

Pure functions, no database.
"""

from __future__ import annotations

import pytest

from herhealth_backend.app.accounts.verification_code_policy import CODE_LENGTH
from herhealth_backend.app.accounts.verification_codes import (
    codes_match,
    generate_code,
    hash_code,
)

_SECRET = "unit-test-secret"


def test_generate_code_has_the_configured_length_and_is_numeric() -> None:
    code = generate_code()

    assert len(code) == CODE_LENGTH
    assert code.isdigit()


def test_generate_code_returns_distinct_values() -> None:
    codes = {generate_code() for _ in range(20)}

    assert len(codes) > 1


def test_generate_code_zero_pads_small_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "herhealth_backend.app.accounts.verification_codes.secrets.randbelow", lambda _: 7
    )

    code = generate_code()

    assert code == "0" * (CODE_LENGTH - 1) + "7"


def test_codes_match_is_true_for_the_code_that_produced_the_hash() -> None:
    code = generate_code()

    assert codes_match(_SECRET, code, hash_code(_SECRET, code)) is True


def test_codes_match_is_false_for_a_different_code() -> None:
    code = generate_code()
    stored_hash = hash_code(_SECRET, code)

    wrong_code = "0" * CODE_LENGTH if code != "0" * CODE_LENGTH else "1" * CODE_LENGTH
    assert codes_match(_SECRET, wrong_code, stored_hash) is False


def test_codes_match_is_false_under_a_different_secret() -> None:
    code = generate_code()
    stored_hash = hash_code(_SECRET, code)

    assert codes_match("a-different-secret", code, stored_hash) is False


def test_hash_code_does_not_leak_the_raw_code() -> None:
    code = generate_code()

    assert code not in hash_code(_SECRET, code)
