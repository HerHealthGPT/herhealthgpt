"""``triage.cycle_data`` — what imported cycle data may answer (ADR 0019).

Run against the real knowledge base on purpose: the property that matters
most is that no rule in the real ``red_flags.yaml`` can fire from tracker
data alone, and a fixture could not show that.
"""

from __future__ import annotations

import datetime
import itertools
from pathlib import Path
from typing import Any

import pytest
from herhealth_contracts.cycle import CycleExtraction
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.context import clause_matches
from herhealth_backend.triage.cycle_data import (
    FRESHNESS_DAYS,
    POSSIBLE_PREFILLS,
    prefill,
    render_cycle_background,
    summarize,
)

REPO = Path(__file__).resolve().parents[3]
BASE = load_knowledge_base(REPO / "knowledge")
TODAY = datetime.date(2026, 10, 18)


def _cycles(
    lengths: list[int],
    *,
    period_days: int = 5,
    flow: str = "medium",
    last_start: datetime.date = TODAY - datetime.timedelta(days=5),
    extra: dict[str, dict[str, Any]] | None = None,
) -> CycleExtraction:
    """Periods whose starts are ``lengths`` apart, the last starting on
    ``last_start``. ``extra`` adds or overrides fields on given ISO dates."""
    starts = [last_start]
    for length in reversed(lengths):
        starts.insert(0, starts[0] - datetime.timedelta(days=length))
    days: dict[str, dict[str, Any]] = {}
    for start in starts:
        for offset in range(period_days):
            date = (start + datetime.timedelta(days=offset)).isoformat()
            days[date] = {"date": date, "flow": flow}
    for date, fields in (extra or {}).items():
        days[date] = {**days.get(date, {"date": date}), **fields}
    return CycleExtraction.model_validate({"source_app": "clue", "days": list(days.values())})


def _prefilled(extraction: CycleExtraction, **kwargs: Any) -> dict[str, str]:
    return prefill(summarize(extraction, today=TODAY, **kwargs), BASE)


def test_no_red_flag_can_fire_from_tracker_data_alone() -> None:
    """Every combination of values prefill can ever produce, tried against
    every rule in red_flags.yaml. A rule satisfiable here would escalate on
    old logs with nothing said today — the line ADR 0019 holds."""
    for rule in BASE.red_flags:
        features = [clause.feature_id for clause in rule.all_of]
        choices = [sorted(POSSIBLE_PREFILLS.get(f, ())) for f in features]
        for combination in itertools.product(*choices):
            given = dict(zip(features, combination, strict=True))
            assert not all(clause_matches(c, given) for c in rule.all_of), rule.id


def test_every_possible_prefill_is_in_the_vocabulary() -> None:
    allowed = {f.id: {str(v) for v in f.allowed_values} for f in BASE.features}
    for feature, values in POSSIBLE_PREFILLS.items():
        assert values <= allowed[feature], feature


def test_long_cycles_are_answered_as_long_and_irregular() -> None:
    """Scenario 1: 38-45 day cycles, the NHS definition of irregular."""
    values = _prefilled(_cycles([38, 41, 45, 40]))
    assert values["cycle_length"] == "over_35_days"
    assert values["cycle_regularity"] == "irregular"
    assert values["period_duration"] == "3_to_7_days"


def test_cycles_within_21_to_35_days_are_regular() -> None:
    values = _prefilled(_cycles([28, 29, 27]))
    assert values["cycle_length"] == "21_to_35_days"
    assert values["cycle_regularity"] == "regular"


def test_cycles_across_buckets_answer_regularity_but_not_length() -> None:
    values = _prefilled(_cycles([26, 33, 41]))
    assert "cycle_length" not in values
    assert values["cycle_regularity"] == "irregular"


def test_fewer_than_three_cycles_answer_nothing_about_the_pattern() -> None:
    values = _prefilled(_cycles([31, 33]))
    assert not {"cycle_length", "cycle_regularity", "period_duration"} & values.keys()


def test_stale_data_answers_nothing() -> None:
    old = TODAY - datetime.timedelta(days=FRESHNESS_DAYS + 25)
    extraction = _cycles([28, 28, 28], flow="heavy", last_start=old)
    assert _prefilled(extraction) == {}
    rendered = render_cycle_background(summarize(extraction, today=TODAY), {})
    assert "out of date" in rendered
    assert "stopped logging" in rendered


def test_red_flag_features_are_answered_only_in_the_alarming_direction() -> None:
    """Scenario 2: heavy flow and a positive test pre-fill; scenario 4: light
    flow and a negative test pre-fill nothing."""
    recent = (TODAY - datetime.timedelta(days=10)).isoformat()
    alarming = _prefilled(
        _cycles([28, 28, 28], flow="heavy", extra={recent: {"pregnancy_test": "positive"}})
    )
    assert alarming["bleeding_heaviness"] == "heavy"
    assert alarming["pregnancy_status"] == "possibly_pregnant"

    benign = _prefilled(
        _cycles([28, 28, 28], flow="light", extra={recent: {"pregnancy_test": "negative"}})
    )
    assert "bleeding_heaviness" not in benign
    assert "pregnancy_status" not in benign


def test_pain_severity_is_never_answered_even_when_logged_severe() -> None:
    first_day = (TODAY - datetime.timedelta(days=5)).isoformat()
    values = _prefilled(
        _cycles(
            [28, 28, 28],
            extra={first_day: {"symptoms": ["cramps"], "pain_intensity": "severe"}},
        )
    )
    assert "pelvic_pain_severity" not in values
    assert values["pelvic_pain_timing"] == "with_periods"


def test_spotting_between_periods_is_answered_yes() -> None:
    mid_cycle = (TODAY - datetime.timedelta(days=19)).isoformat()
    values = _prefilled(_cycles([28, 28, 28], extra={mid_cycle: {"flow": "spotting"}}))
    assert values["bleeding_between_periods"] == "yes"


def test_absence_is_never_read_as_no() -> None:
    """Scenario 5: no pain logged answers nothing unless she confirmed it."""
    extraction = _cycles([28, 28, 28])
    assert "pelvic_pain_timing" not in _prefilled(extraction)
    confirmed = _prefilled(extraction, confirmed_no_period_pain=True)
    assert confirmed["pelvic_pain_timing"] == "none"


@pytest.mark.parametrize("symptom", ["acne", "bloating", "low_mood", "lower_back_pain"])
def test_a_logged_symptom_answers_yes(symptom: str) -> None:
    recent = (TODAY - datetime.timedelta(days=3)).isoformat()
    values = _prefilled(_cycles([28, 28, 28], extra={recent: {"symptoms": [symptom]}}))
    assert "yes" in values.values()


def test_the_background_lists_what_was_answered_and_frames_the_rest() -> None:
    extraction = _cycles([38, 41, 45])
    summary = summarize(extraction, today=TODAY)
    rendered = render_cycle_background(summary, prefill(summary, BASE))

    assert "not from this conversation" in rendered
    assert "38, 41, 45" in rendered
    assert "cycle_length=over_35_days" in rendered
    assert "do not ask them again" in rendered
    assert "what she says wins" in rendered
    assert "never let it fire a warning sign on its own" in rendered
    assert "Pain severity is always asked about today" in rendered
