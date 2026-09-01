"""How a password-reset code is shaped, how long it lives, and how many
guesses it tolerates before it is dead (#12).

Mirrors ``verification_code_policy.py`` exactly — a reset code is the same
shape of secret as a verification code (short, emailed, typed from an
inbox), so the same three trade-offs apply for the same reasons.
"""

from __future__ import annotations

from datetime import timedelta

__all__ = ["CODE_LENGTH", "CODE_TTL", "MAX_ATTEMPTS"]

#: Digits in a code. Matches verification_code_policy.CODE_LENGTH.
CODE_LENGTH = 6

#: How long a code stays usable after it is sent.
CODE_TTL = timedelta(minutes=15)

#: Wrong guesses tolerated before the code is invalidated entirely and a new
#: one must be requested. 10**6 combinations at 5 guesses is not brute-forceable.
MAX_ATTEMPTS = 5
