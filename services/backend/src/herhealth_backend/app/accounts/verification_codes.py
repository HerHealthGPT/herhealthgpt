"""Generating a verification code, and comparing one without leaking timing.

A verification code is short by necessity (CODE_LENGTH digits — a woman
types it from her inbox), which makes it a fundamentally different secret
from a password or a refresh token: its keyspace is small enough that a fast
hash of it can simply be inverted by recomputing every possible code, if an
attacker ever gets the stored value. ``hash_code`` is keyed with the app
secret (HMAC, not a plain digest) specifically so that a stolen database row
is useless without also knowing that secret — MAX_ATTEMPTS is what stops
online guessing; this is what stops offline guessing from a leaked row.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from herhealth_backend.app.accounts.verification_code_policy import CODE_LENGTH

__all__ = ["generate_code", "hash_code", "codes_match"]

#: Namespaces this HMAC's use of the app secret away from any other keyed use
#: (access tokens use itsdangerous under their own salt; see tokens.py).
_CONTEXT = b"herhealth-email-verification-code"


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
