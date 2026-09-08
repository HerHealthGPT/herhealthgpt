"""``age_bands`` against the real ``features.yaml``.

The point of the first test is the boundaries duplicated in
``age_bands._BANDS``: they cannot be derived from ``features.yaml``, because
``allowed_values`` there holds opaque ids rather than ranges. So this asserts
the duplication has not drifted — a renamed band fails here rather than
producing an id the closed vocabulary rejects at ``ClosedVocabularyViolation``
time.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.age_bands import (
    AGE_BAND_FEATURE_ID,
    age_band_for,
    age_in_years,
)

REPO = Path(__file__).resolve().parents[3]
KNOWLEDGE = REPO / "knowledge"

#: One date of birth per band, as of TODAY below.
TODAY = date(2026, 9, 6)


def _allowed_age_bands() -> set[str]:
    base = load_knowledge_base(KNOWLEDGE)
    return set(base.features_by_id[AGE_BAND_FEATURE_ID].allowed_values)


@pytest.mark.parametrize(
    ("date_of_birth", "expected"),
    [
        (date(2010, 1, 1), "under_20"),
        (date(2006, 9, 6), "20_to_29"),
        (date(1997, 1, 1), "20_to_29"),
        (date(1996, 9, 6), "30_to_39"),
        (date(1987, 1, 1), "30_to_39"),
        (date(1986, 9, 6), "40_to_44"),
        (date(1982, 1, 1), "40_to_44"),
        (date(1981, 9, 6), "45_to_54"),
        (date(1972, 1, 1), "45_to_54"),
        (date(1971, 9, 6), "55_plus"),
        (date(1940, 1, 1), "55_plus"),
    ],
)
def test_each_band_is_reachable(date_of_birth: date, expected: str) -> None:
    assert age_band_for(date_of_birth, today=TODAY) == expected


def test_every_band_this_module_returns_is_a_real_allowed_value() -> None:
    allowed = _allowed_age_bands()
    reachable = {
        age_band_for(date(year, 1, 1), today=TODAY)
        # Spans every band from the 55_plus floor to under_20.
        for year in range(TODAY.year - 100, TODAY.year)
    }
    assert reachable, "no bands produced — the loop bounds are wrong"
    assert reachable <= allowed, f"not in features.yaml: {sorted(reachable - allowed)}"


def test_every_allowed_value_is_reachable() -> None:
    """The other direction: no band in features.yaml is unreachable, which
    would mean a value the model may pick that this mapping never produces."""
    allowed = _allowed_age_bands()
    reachable = {
        age_band_for(date(year, 1, 1), today=TODAY) for year in range(TODAY.year - 100, TODAY.year)
    }
    assert allowed <= reachable, f"unreachable bands: {sorted(allowed - reachable)}"


def test_age_is_not_incremented_until_the_birthday() -> None:
    """The reason a date is stored rather than a band — 45 is the boundary
    features.yaml says separates perimenopause from PCOS, so being a day out
    changes what the system suspects."""
    born = date(1981, 9, 7)
    assert age_in_years(born, today=date(2026, 9, 6)) == 44
    assert age_band_for(born, today=date(2026, 9, 6)) == "40_to_44"
    assert age_in_years(born, today=date(2026, 9, 7)) == 45
    assert age_band_for(born, today=date(2026, 9, 7)) == "45_to_54"


def test_a_birthday_on_29_february_does_not_crash_in_a_non_leap_year() -> None:
    born = date(2000, 2, 29)
    # 2026 is not a leap year: by 1 March she has had her birthday.
    assert age_in_years(born, today=date(2026, 2, 28)) == 25
    assert age_in_years(born, today=date(2026, 3, 1)) == 26
