"""Date of birth -> the ``age_band`` value ``knowledge/features.yaml`` allows.

Lives on the Triage side of the boundary and imports nothing from Accounts,
because what it knows about is the ``age_band`` feature's closed vocabulary,
not users. The API layer passes a stored date in; that layer is the one place
``CONTEXT-MAP.md`` permits the two contexts to meet.

**The boundaries below are duplicated from ``features.yaml`` and cannot be
derived from it.** That file records ``allowed_values`` as opaque ids —
``40_to_44`` is a string, not a machine-readable range — so the numbers have
to be written somewhere. ``tests/test_age_bands.py`` asserts every value this
module can return really is in ``features.yaml``'s ``allowed_values``, so a
renamed band breaks a test rather than silently producing an id the closed
vocabulary rejects.
"""

from __future__ import annotations

from datetime import date

__all__ = ["AGE_BAND_FEATURE_ID", "age_band_for", "age_in_years"]

#: The feature these values belong to, in features.yaml.
AGE_BAND_FEATURE_ID = "age_band"

#: Upper bound (inclusive) of each band, and the id for ages at or below it.
#: Ordered, and the last entry's ``None`` is the open-ended top band.
_BANDS: tuple[tuple[int | None, str], ...] = (
    (19, "under_20"),
    (29, "20_to_29"),
    (39, "30_to_39"),
    (44, "40_to_44"),
    (54, "45_to_54"),
    (None, "55_plus"),
)


def age_in_years(date_of_birth: date, *, today: date) -> int:
    """Completed years, the way a person counts her own age.

    ``today`` is required rather than defaulted to ``date.today()`` so this
    is a pure function: a birthday-boundary test must be able to name the
    day it is asking about, and a band that changes with the wall clock is
    untestable.
    """
    had_birthday_this_year = (today.month, today.day) >= (
        date_of_birth.month,
        date_of_birth.day,
    )
    return today.year - date_of_birth.year - (0 if had_birthday_this_year else 1)


def age_band_for(date_of_birth: date, *, today: date) -> str:
    """The ``age_band`` id for this date of birth, as of ``today``.

    Returns an id from ``features.yaml``'s ``allowed_values`` and nothing
    else. A date in the future yields ``under_20`` rather than raising —
    validation of the date itself belongs to whoever accepted it from a user
    (``app/accounts/profile.py``), not here.
    """
    age = age_in_years(date_of_birth, today=today)
    for upper_bound, band in _BANDS:
        if upper_bound is None or age <= upper_bound:
            return band
    raise AssertionError("_BANDS must end with an open-ended band")  # pragma: no cover
