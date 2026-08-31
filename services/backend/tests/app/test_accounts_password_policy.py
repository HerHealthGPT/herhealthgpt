"""The password strength floor, and that a rejection says what is wrong."""

from __future__ import annotations

import pytest

from herhealth_backend.app.accounts.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    PasswordTooWeak,
    check_password_strength,
)


def test_acceptable_password_is_not_rejected() -> None:
    check_password_strength("correct-horse-battery-staple")


def test_too_short_password_is_rejected_with_a_reason() -> None:
    with pytest.raises(PasswordTooWeak) as excinfo:
        check_password_strength("a" * (MIN_LENGTH - 1))
    assert any("characters" in reason for reason in excinfo.value.reasons)


def test_password_at_the_minimum_length_is_accepted() -> None:
    check_password_strength("a1b2c3d" + "z")  # MIN_LENGTH characters, not a common password


def test_common_password_is_rejected_with_a_reason() -> None:
    with pytest.raises(PasswordTooWeak) as excinfo:
        check_password_strength("password123")
    assert any("common" in reason for reason in excinfo.value.reasons)


def test_common_password_check_is_case_insensitive() -> None:
    with pytest.raises(PasswordTooWeak):
        check_password_strength("PASSWORD123")


def test_too_long_password_is_rejected_with_a_reason() -> None:
    with pytest.raises(PasswordTooWeak) as excinfo:
        check_password_strength("a1" * (MAX_LENGTH // 2 + 1))
    assert any("characters" in reason for reason in excinfo.value.reasons)


@pytest.mark.parametrize(
    "password", ["12345678", "00000000", "11111111", "qwerty123", "iloveyou1"]
)
def test_other_top_breach_corpus_passwords_are_rejected(password: str) -> None:
    with pytest.raises(PasswordTooWeak):
        check_password_strength(password)
