"""The password strength floor a new credential must clear.

Kept as a pure function returning *why* a password was refused, because #8's
acceptance criteria require the rejection message to say what is wrong, not
merely that the password was rejected.

The list below is deliberately small and boring: a minimum length plus a
denylist of the handful of passwords that show up at the top of every public
breach-corpus frequency table (`123456`, `password`, `qwerty`, ...). A
capstone with no clinician reviewer and no security team should not be
carrying a bespoke entropy estimator; a length floor and a denylist are easy
to verify by reading them, which is the same bar the knowledge base itself is
held to.
"""

from __future__ import annotations

__all__ = ["PasswordTooWeak", "MIN_LENGTH", "MAX_LENGTH", "check_password_strength"]

#: Below this many characters, a password is refused regardless of content.
MIN_LENGTH = 8

#: Above this many characters, a password is refused too. Generous enough for
#: any real passphrase; the actual point is to stop an arbitrarily large
#: request body from reaching argon2id, which hashes whatever it is given.
#: Enforced here and only here — not as a schema-level Field(max_length=...)
#: in routes.py, because FastAPI's default validation-error response echoes
#: the raw offending value, which would leak an oversized password into the
#: 422 body. This function runs before hash_password and reports only static
#: reason strings, never the password itself.
MAX_LENGTH = 256

#: Case-folded. The most common passwords in public breach corpora, plus the
#: obvious runs a length floor alone would still let through.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "12345678910",
        "00000000",
        "11111111",
        "qwertyui",
        "qwerty123",
        "qwertyuiop",
        "letmein123",
        "iloveyou1",
        "iloveyou123",
        "admin123456",
        "welcome123",
        "sunshine123",
        "princess123",
        "abcdefghij",
        "1q2w3e4r5t",
    }
)


class PasswordTooWeak(Exception):
    """Raised with every reason the password did not clear the floor."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = tuple(reasons)
        super().__init__("; ".join(reasons))


def check_password_strength(password: str) -> None:
    """Raise :class:`PasswordTooWeak` naming every way ``password`` falls short."""
    reasons: list[str] = []
    if len(password) < MIN_LENGTH:
        reasons.append(f"must be at least {MIN_LENGTH} characters long")
    if len(password) > MAX_LENGTH:
        reasons.append(f"must be at most {MAX_LENGTH} characters long")
    if password.casefold() in _COMMON_PASSWORDS:
        reasons.append("is too common to be used as a password")
    if reasons:
        raise PasswordTooWeak(reasons)
