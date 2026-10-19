"""Her cycle data in plain words, written by code (2026-10-19).

The numbers are the shape of a real Apple Health PDF import: twelve periods,
one 54-day cycle among 27 to 28-day ones.
"""

from __future__ import annotations

import datetime

import pytest
from herhealth_contracts.cycle import CycleExtraction

from herhealth_backend.triage.cycle_data import (
    asks_about_cycle_data,
    render_cycle_breakdown,
    summarize,
)

STARTS = ["2026-04-15", "2026-06-08", "2026-07-05", "2026-08-01", "2026-08-29", "2026-09-26"]


def _summary() -> object:
    days = []
    for start in STARTS:
        first = datetime.date.fromisoformat(start)
        for offset in range(3):
            days.append(
                {
                    "date": (first + datetime.timedelta(days=offset)).isoformat(),
                    "flow": "unspecified",
                    "symptoms": [],
                }
            )
    extraction = CycleExtraction.model_validate({"source_app": "apple_health", "days": days})
    return summarize(extraction, today=datetime.date(2026, 10, 19))


def test_the_breakdown_names_the_cycle_outside_the_usual_range() -> None:
    text = render_cycle_breakdown(_summary(), "en")  # type: ignore[arg-type]
    assert text is not None
    assert "6 periods, the most recent starting on 2026-09-26" in text
    assert "oldest first: 54, 27, 27, 28, 28 days" in text
    assert "Outside the 21 to 35 days our sources give as usual: 54 days" in text


@pytest.mark.parametrize("language", ["ar", "fr"])
def test_the_breakdown_is_written_in_her_language(language: str) -> None:
    text = render_cycle_breakdown(_summary(), language)  # type: ignore[arg-type]
    assert text is not None
    assert "54" in text
    assert "From the cycle data" not in text


def test_the_breakdown_never_judges_her_cycle() -> None:
    for language in ("en", "ar", "fr"):
        text = (render_cycle_breakdown(_summary(), language) or "").lower()  # type: ignore[arg-type]
        for word in ("healthy", "normal", "abnormal", "طبيعي", "normal"):
            assert word not in text


@pytest.mark.parametrize(
    ("message", "about"),
    [
        ("Can you see my cycle data file attached? Is it healthy?", True),
        ("Give me a breakdown", True),
        ("Looking at my tracker, is my cycle ok?", True),
        ("هل ترى بيانات دورتي؟", True),
        ("Pouvez-vous voir mes données de cycle ?", True),
        ("I have bad cramps today", False),
        ("What is PCOS?", False),
    ],
)
def test_a_question_about_her_data_is_recognised(message: str, about: bool) -> None:
    assert asks_about_cycle_data(message) is about


def test_her_data_is_shown_on_the_breakdown_turn() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    use = _her_data_use(
        _summary(),  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=True,
        concluded=False,
        first_turn=False,
    )
    assert use is not None
    assert use["source_app"] == "apple_health"
    assert use["breakdown"] is True
    assert use["answered"] == ["cycle_regularity"]


def test_her_data_is_not_repeated_on_every_question() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    use = _her_data_use(
        _summary(),  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=False,
        concluded=False,
        first_turn=False,
    )
    assert use is None


def test_her_data_is_shown_on_a_conclusion_it_answered_for() -> None:
    from herhealth_backend.app.triage.routes import _her_data_use

    summary = _summary()
    assert _her_data_use(summary, {}, breakdown=False, concluded=True, first_turn=True) is None  # type: ignore[arg-type]
    use = _her_data_use(
        summary,  # type: ignore[arg-type]
        {"cycle_regularity": "irregular"},
        breakdown=False,
        concluded=True,
        first_turn=False,
    )
    assert use is not None and use["breakdown"] is False
