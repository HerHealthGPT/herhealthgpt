"""How a verification code is shaped, how long it lives, and how many
guesses it tolerates before it is dead (#10).

Three independent policy calls, the same kind CLAUDE.md's clinical
thresholds are: ``CODE_LENGTH`` trades guessability against what a woman can
type from an email; ``CODE_TTL`` is the "agreed window" #10 asks for;
``MAX_ATTEMPTS`` is what makes a 6-digit code's small keyspace safe to use at
all — without a cap, 10**CODE_LENGTH guesses is nothing to script.
"""

from __future__ import annotations

from datetime import timedelta

__all__ = ["CODE_LENGTH", "CODE_TTL", "MAX_ATTEMPTS"]

#: Digits in a code. Six is the common floor for a one-time code sent by
#: email — short enough to type from an inbox, still 10**6 combinations.
CODE_LENGTH = 6

#: How long a code stays usable after it is sent.
CODE_TTL = timedelta(minutes=15)

#: Wrong guesses tolerated before the code is invalidated entirely and a new
#: one must be requested. 10**6 combinations at 5 guesses is not brute-forceable.
MAX_ATTEMPTS = 5
