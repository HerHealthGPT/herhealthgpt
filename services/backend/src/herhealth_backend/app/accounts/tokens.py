"""The two token kinds a session hands out, and nothing else touches either.

**Access tokens** are short-lived and deliberately not looked up anywhere —
CONTEXT.md's resolved decision is that they are short-lived precisely
*because* they cannot be revoked. They are signed with ``itsdangerous``
rather than built as a JWT: a JWT's header and algorithm negotiation exist to
solve interoperability problems this single-process service does not have,
and that negotiable header is also exactly what algorithm-confusion attacks
against JWT libraries have historically targeted. ``itsdangerous`` gives the
same property — a value that cannot be forged or altered without the secret —
with one fixed algorithm and no header to attack.

**Refresh tokens** are 256 bits of random entropy, opaque to the holder. Only
their hash is ever stored (see ``models.Session.refresh_token_hash``), the
same reasoning ``passwords.py`` applies to a password — except the hash here
is a fast one. A refresh token has no low-entropy secret for a slow hash to
protect against guessing; argon2id would only add cost with nothing to show
for it.
"""

from __future__ import annotations

import hashlib
import secrets

from itsdangerous import BadSignature, URLSafeTimedSerializer

from herhealth_backend.app.accounts.errors import InvalidAccessToken
from herhealth_backend.app.accounts.session_policy import ACCESS_TOKEN_TTL

__all__ = [
    "issue_access_token",
    "read_access_token",
    "generate_refresh_token",
    "hash_refresh_token",
]

#: Namespaces this signer's tokens away from any other itsdangerous use in the
#: process, so the same secret could not be replayed across purposes.
_ACCESS_TOKEN_SALT = "herhealth-access-token"


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_ACCESS_TOKEN_SALT)


def issue_access_token(secret: str, *, user_id: str) -> str:
    """A signed token proving ``user_id`` was signed in within ACCESS_TOKEN_TTL."""
    return _serializer(secret).dumps(user_id)


def read_access_token(secret: str, token: str) -> str:
    """The ``user_id`` a valid, unexpired access token was issued for.

    Raises :class:`~herhealth_backend.app.accounts.errors.InvalidAccessToken`
    if ``token`` is missing, tampered with, signed under a different secret,
    or older than ACCESS_TOKEN_TTL.
    """
    try:
        user_id = _serializer(secret).loads(token, max_age=int(ACCESS_TOKEN_TTL.total_seconds()))
    except BadSignature as exc:
        raise InvalidAccessToken() from exc
    return str(user_id)


def generate_refresh_token() -> str:
    """A fresh, high-entropy opaque secret, safe to put in a cookie value."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    """The value stored in place of ``raw_token``. See the module docstring
    for why a fast hash is the right choice here and not a slow one.

    UTF-8, not ASCII: a real token (``secrets.token_urlsafe``) is always
    ASCII, but ``raw_token`` can also be an arbitrary cookie value a caller
    sent, and encoding must not raise on that input — it should simply hash
    to something no stored row matches, the same as any other wrong token.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()
