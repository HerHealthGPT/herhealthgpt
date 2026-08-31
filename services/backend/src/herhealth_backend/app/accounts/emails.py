"""Normalising an email address to a consistent stored form.

Two spellings of the same address must resolve to one user (#8's acceptance
criteria), so every address is normalised before it is compared or stored.
Case folding and trimming surrounding whitespace are the two things a user
routinely does by accident (a capitalised first letter, a pasted trailing
space); anything beyond that (stripping Gmail's dots or plus-addressing) is a
provider-specific guess this project does not make.
"""

from __future__ import annotations

__all__ = ["normalize_email"]


def normalize_email(email: str) -> str:
    """The form an address is stored and compared in: trimmed, case-folded."""
    return email.strip().casefold()
