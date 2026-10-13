"""Scoring first-turn outcomes against the benchmark's silver labels."""

from __future__ import annotations

import pytest

from herhealth_backend.evaluation.benchmark_score import outcome, score


def row(
    gold: str,
    kind: str | None,
    action: str | None = None,
    *,
    clarify: str = "no",
    seed: str = "s1",
    style: str = "canonical",
) -> dict[str, object]:
    return {
        "seed_id": seed,
        "style": style,
        "gold_risk_level": gold,
        "requires_clarification": clarify,
        "ok": kind is not None,
        "type": kind,
        "action": action,
    }


@pytest.mark.parametrize(
    ("kind", "action", "expected"),
    [
        ("conclude", "SELF_CARE", "routine"),
        ("conclude", "ROUTINE_APPOINTMENT", "see-doctor"),
        ("conclude", "URGENT_SAME_DAY", "urgent"),
        ("conclude", "EMERGENCY", "urgent"),
        ("ask", None, "asked"),
        ("inform", None, "no-level"),
        ("decline", None, "declined"),
        (None, None, "invalid"),
    ],
)
def test_outcome_mapping(kind: str | None, action: str | None, expected: str) -> None:
    assert outcome(row("routine", kind, action)) == expected


def test_strict_under_triage_counts_an_explanation_and_a_lower_level() -> None:
    rows = [
        row("see-doctor", "conclude", "ROUTINE_APPOINTMENT"),  # met
        row("see-doctor", "inform"),  # no level: under
        row("see-doctor", "conclude", "SELF_CARE"),  # lower: under
        row("see-doctor", "ask"),  # asked: not under
        row("urgent", "conclude", "ROUTINE_APPOINTMENT"),  # lower: under
        row("urgent", "conclude", "EMERGENCY"),  # met
        row("urgent", None),  # invalid: separate
        row("routine", "inform"),  # not in the denominator
    ]
    result = score(rows)
    need = result["needing_a_doctor"]
    assert need["questions"] == 7
    assert need["under_triaged"] == 3
    assert need["under_triage_rate"] == pytest.approx(3 / 7)
    assert need["breakdown"] == {
        "met or exceeded": 2,
        "asked": 1,
        "no-level": 1,
        "lower level": 2,
        "declined": 0,
        "invalid": 1,
    }


def test_clarification_recall_and_over_triage() -> None:
    rows = [
        row("routine", "ask", clarify="yes"),
        row("routine", "inform", clarify="yes"),
        row("routine", "conclude", "ROUTINE_APPOINTMENT"),
        row("routine", "conclude", "SELF_CARE"),
    ]
    result = score(rows)
    assert result["clarification"] == {"questions": 2, "asked": 1, "recall": 0.5}
    assert result["routine"]["questions"] == 4
    assert result["routine"]["over_triaged"] == 1


def test_consistency_across_rewordings() -> None:
    rows = [
        row("routine", "inform", seed="a", style="canonical"),
        row("routine", "inform", seed="a", style="clinical"),
        row("routine", "ask", seed="b", style="canonical"),
        row("routine", "inform", seed="b", style="clinical"),
    ]
    assert score(rows)["consistency"] == {"seeds": 2, "all_rewordings_same_outcome": 1}
