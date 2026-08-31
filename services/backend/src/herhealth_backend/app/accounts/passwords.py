"""Turning a password into the argon2id hash that is actually stored.

One module, so there is exactly one place that touches a plaintext password.
``Type.ID`` is passed explicitly rather than relied on as the library default —
CLAUDE.md's rule about never inventing a clinical fact has a security analogue
here: which variant is used should be a line you can read, not an assumption
about what a dependency currently defaults to.
"""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

__all__ = ["hash_password", "verify_password"]

_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """The argon2id hash to store. Never log or persist ``password`` itself."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Whether ``password`` matches the stored ``password_hash``."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
