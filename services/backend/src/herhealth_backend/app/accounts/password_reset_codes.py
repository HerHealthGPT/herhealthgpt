"""Generating a password-reset code, and comparing one without leaking timing.

Mirrors ``verification_codes.py`` exactly, including the reasoning: a reset
code is short by necessity (CODE_LENGTH digits), which makes a fast hash of
it invertible by brute force if a stored row ever leaks — ``hash_code`` is
keyed with the app secret so a stolen database row is useless without it too.
A separate HMAC context from ``verification_codes.py``'s, so the two kinds of
code can never be confused for each other even though both are hashed under
the same app secret.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from herhealth_backend.app.accounts.password_reset_policy import CODE_LENGTH

__all__ = ["generate_code", "hash_code", "codes_match"]

#: Namespaces this HMAC's use of the app secret away from verification_codes.py's
#: own context, and any other keyed use in the process.
_CONTEXT = b"herhealth-password-reset-code"


def generate_code() -> str:
    """A fresh CODE_LENGTH-digit code, zero-padded, drawn from a CSPRNG."""
    upper_bound = 10**CODE_LENGTH
    return str(secrets.randbelow(upper_bound)).zfill(CODE_LENGTH)


def hash_code(secret: str, code: str) -> str:
    """The value stored in place of ``code``. See the module docstring for
    why this is a keyed HMAC rather than a plain hash."""
    return hmac.new(secret.encode(), _CONTEXT + code.encode(), hashlib.sha256).hexdigest()


def codes_match(secret: str, code: str, expected_hash: str) -> bool:
    """Whether ``code`` hashes to ``expected_hash``, compared in constant
    time so neither a matching prefix nor the overall length of the
    computation can leak how close a guess was."""
    return hmac.compare_digest(hash_code(secret, code), expected_hash)
