"""argon2id hashing: the hash proves the password without storing it."""

from __future__ import annotations

from herhealth_backend.app.accounts.passwords import hash_password, verify_password


def test_hash_is_argon2id() -> None:
    assert hash_password("correct-horse-battery-staple").startswith("$argon2id$")


def test_hash_never_contains_the_plaintext() -> None:
    password = "correct-horse-battery-staple"
    assert password not in hash_password(password)


def test_hashing_the_same_password_twice_gives_different_hashes() -> None:
    password = "correct-horse-battery-staple"
    assert hash_password(password) != hash_password(password)


def test_verify_password_accepts_the_matching_password() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password(password_hash, "correct-horse-battery-staple") is True


def test_verify_password_rejects_a_wrong_password() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password(password_hash, "wrong-password-entirely") is False
