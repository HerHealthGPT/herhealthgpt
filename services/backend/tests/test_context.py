"""Tests for the deterministic grounding layer.

Built on ``triage_factories.build()`` for the same reason ``test_engine.py``
is: these are tests of the join and the clause arithmetic, and pinning them to
real clinical rows would let an approved evidence batch break them for reasons
that have nothing to do with this code.
"""

from __future__ import annotations

import pytest
from triage_factories import build, condition, evidence, feature

from herhealth_backend.triage.context import (
    TurnContext,
    assess_rules,
    build_turn_context,
    fired_rule,
    join_evidence,
    live_conditions,
    rank_askable,
    render_turn_context,
    separation,
)

# -- the join ---------------------------------------------------------------


def test_join_returns_every_row_keyed_by_an_answer_and_nothing_else() -> None:
    base = build()
    groups = {g.condition.id: g for g in join_evidence(base, {"pain": "severe"})}

    # All three conditions have a row on pain=severe; nothing keyed on fever
    # or bleeding may appear, because she has not answered those.
    assert set(groups) == {"infection", "growth", "normal"}
    for group in groups.values():
        assert all(row.feature_id == "pain" and row.value == "severe" for row in group.rows)


def test_join_is_empty_when_nothing_is_answered() -> None:
    assert join_evidence(build(), {}) == ()


def test_join_ignores_a_value_that_matches_no_row() -> None:
    assert join_evidence(build(), {"pain": "mild"}) == ()


def test_join_separates_supporting_from_arguing_against() -> None:
    groups = {g.condition.id: g for g in join_evidence(build(), {"pain": "severe"})}

    assert [r.strength.value for r in groups["infection"].supporting] == ["weak_support"]
    assert groups["infection"].against == ()
    # `normal` is reached by the join, but only by a row that argues against
    # it — the distinction a caller needs in order not to name it.
    assert groups["normal"].supporting == ()
    assert [r.strength.value for r in groups["normal"].against] == ["argues_against"]


def test_join_orders_strong_support_first() -> None:
    base = build()
    ordered = [g.condition.id for g in join_evidence(base, {"fever": "yes", "pain": "severe"})]
    # infection is the only condition with a strong_support row in this set.
    assert ordered[0] == "infection"


# -- red-flag clause arithmetic ---------------------------------------------


def test_a_rule_fires_only_when_every_clause_matches() -> None:
    base = build()
    assert fired_rule(assess_rules(base, {"pain": "severe"})) is None
    fired = fired_rule(assess_rules(base, {"pain": "severe", "fever": "yes"}))
    assert fired is not None
    assert fired.rule.id == "severe_pain_with_fever"


def test_an_unanswered_feature_never_satisfies_a_clause() -> None:
    (status,) = [s for s in assess_rules(build(), {}) if s.rule.id == "severe_pain_with_fever"]
    assert status.distance == 2
    assert not status.engaged


def test_distance_and_engagement_track_partial_matches() -> None:
    statuses = assess_rules(build(), {"pain": "severe"})
    (status,) = [s for s in statuses if s.rule.id == "severe_pain_with_fever"]
    assert status.distance == 1
    assert status.engaged
    assert status.outstanding[0].feature_id == "fever"


def test_the_most_severe_fired_rule_wins_not_the_first_in_file_order() -> None:
    """Two rules matching the same answers must resolve by severity."""
    red_flags = [
        {
            "id": "less_severe_first_in_file",
            "label": "Pain alone",
            "all_of": [{"feature_id": "pain", "op": "equals", "value": "severe"}],
            "action": "URGENT_SAME_DAY",
            "source_id": "src_a",
            "source_quote": "Severe pain should be seen today.",
        },
        {
            "id": "more_severe_second_in_file",
            "label": "Pain with fever",
            "all_of": [
                {"feature_id": "pain", "op": "equals", "value": "severe"},
                {"feature_id": "fever", "op": "equals", "value": "yes"},
            ],
            "action": "EMERGENCY",
            "source_id": "src_a",
            "source_quote": "Seek emergency care for severe pain with a fever.",
        },
    ]
    base = build(red_flags=red_flags)
    fired = fired_rule(assess_rules(base, {"pain": "severe", "fever": "yes"}))
    assert fired is not None
    assert fired.rule.id == "more_severe_second_in_file"


@pytest.mark.parametrize(
    ("op", "value", "answer", "expected"),
    [
        ("equals", "severe", "severe", True),
        ("equals", "severe", "mild", False),
        ("not_equals", "none", "mild", True),
        ("not_equals", "none", "none", False),
        ("in", ["mild", "severe"], "severe", True),
        ("in", ["mild", "severe"], "none", False),
    ],
)
def test_every_comparison_operator(op: str, value: object, answer: str, expected: bool) -> None:
    base = build(
        red_flags=[
            {
                "id": "rule",
                "label": "Rule",
                "all_of": [{"feature_id": "pain", "op": op, "value": value}],
                "action": "EMERGENCY",
                "source_id": "src_a",
                "source_quote": "Seek emergency care.",
            }
        ]
    )
    assert (fired_rule(assess_rules(base, {"pain": answer})) is not None) is expected


# -- near misses, and the property that makes the screen terminate ----------


def test_a_rule_one_answer_away_is_reported_as_a_near_miss() -> None:
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain"])
    assert [s.rule.id for s in turn.near_misses] == ["severe_pain_with_fever"]


def test_an_answered_feature_kills_the_rule_rather_than_leaving_it_near() -> None:
    """The bug this exists to prevent.

    Once ``fever=no`` is in, ``severe_pain_with_fever`` still has exactly one
    outstanding clause — but a dead one. Reporting it as "one answer away"
    would show a live emergency rule that no answer can ever complete, for the
    rest of the consultation, and the screen would never finish.
    """
    turn = build_turn_context(
        build(), given={"pain": "severe", "fever": "no"}, asked=["pain", "fever"]
    )
    assert turn.near_misses == ()
    assert [s.rule.id for s in turn.refuted] == ["severe_pain_with_fever"]


def test_an_unknown_answer_still_counts_as_asked() -> None:
    """"Asked and she could not say" must not be re-offered forever."""
    turn = build_turn_context(
        build(), given={"pain": "severe", "fever": "unknown"}, asked=["pain", "fever"]
    )
    assert turn.near_misses == ()
    assert "fever" not in {a.feature.id for a in turn.askable}


def test_a_rule_with_no_matching_clause_is_not_near() -> None:
    """Engagement scopes the screen to the presentation in front of us."""
    turn = build_turn_context(build(), given={"bleeding": "heavy"}, asked=["bleeding"])
    assert turn.near_misses == ()


# -- ranking ----------------------------------------------------------------


def test_a_feature_completing_a_severe_rule_outranks_a_merely_separating_one() -> None:
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain"])
    assert turn.askable[0].feature.id == "fever"
    assert "EMERGENCY" in turn.askable[0].reasons[0]


def test_burden_breaks_a_tie_before_separation() -> None:
    """Screening value is severity and cost, not differential separation.

    ``cheap`` and ``dear`` both complete the same EMERGENCY rule; ``dear``
    additionally separates the grid. The cheaper question must still win — a
    feature's separation says how well it splits the differential, which is
    not what is being decided while screening for an emergency.
    """
    features = [
        feature("trigger", ["yes", "no"], burden=1),
        feature("cheap", ["yes", "no"], burden=1),
        feature("dear", ["yes", "no"], burden=4),
    ]
    rows = [
        evidence("infection", "dear", "yes", "strong_support"),
        evidence("growth", "dear", "no", "weak_support"),
    ]
    red_flags = [
        {
            "id": f"trigger_with_{name}",
            "label": f"Trigger with {name}",
            "all_of": [
                {"feature_id": "trigger", "op": "equals", "value": "yes"},
                {"feature_id": name, "op": "equals", "value": "yes"},
            ],
            "action": "EMERGENCY",
            "source_id": "src_a",
            "source_quote": "Seek emergency care.",
        }
        for name in ("cheap", "dear")
    ]
    base = build(
        features=features,
        conditions=[condition("infection", "URGENT_SAME_DAY"), condition("growth", "SELF_CARE")],
        rows=rows,
        red_flags=red_flags,
    )
    turn = build_turn_context(base, given={"trigger": "yes"}, asked=["trigger"])

    assert separation(base, "dear") == 2
    assert separation(base, "cheap") == 0
    assert turn.askable[0].feature.id == "cheap"


def test_a_question_that_singles_one_condition_out_beats_one_that_lifts_all() -> None:
    """Spread, not mass — the fix for a defect seen in a live consultation.

    Scoring by summed weight rewarded a feature for *touching many*
    conditions rather than for *telling them apart*. Observed 2026-09-11:
    after "my periods are all over the place" the top-ranked follow-up was
    "have you been trying to become pregnant without success?" — burden 3,
    the most sensitive tier — because ``difficulty_conceiving`` carries rows
    for nine conditions, eight of them ``weak_support`` pointing the same
    way. Answering it lifts the whole differential and separates nothing.

    Both features here cost the same, so burden cannot decide it: the only
    difference is that one concentrates its weight and the other spreads it.
    """
    features = [
        feature("lead", ["yes", "no"], burden=1),
        feature("lifts_everything", ["yes", "no"], burden=1),
        feature("singles_one_out", ["yes", "no"], burden=1),
    ]
    rows = [
        # Establishes a differential: infection ahead of growth.
        evidence("infection", "lead", "yes", "strong_support"),
        evidence("growth", "lead", "yes", "weak_support"),
        # Raises every live condition by the same amount.
        evidence("infection", "lifts_everything", "yes", "weak_support"),
        evidence("growth", "lifts_everything", "yes", "weak_support"),
        # Raises only the one already in front.
        evidence("infection", "singles_one_out", "yes", "weak_support"),
    ]
    base = build(features=features, rows=rows, red_flags=[])
    turn = build_turn_context(base, given={"lead": "yes"}, asked=["lead"])

    ranked = [a.feature.id for a in turn.askable]
    assert ranked.index("singles_one_out") < ranked.index("lifts_everything")


def test_burden_is_a_divisor_so_an_invasive_question_must_earn_its_place() -> None:
    """Ranking is a ratio, so burden is a price rather than a veto — but a
    steep one. A burden-3 question needs roughly three times the
    discrimination of a burden-1 question to outrank it, which is the
    intended behaviour for a question like "have you been trying to
    conceive": it should be asked when it is decisively useful, not merely
    when it is somewhat useful.
    """
    features = [
        feature("lead", ["yes", "no"], burden=1),
        feature("cheap", ["yes", "no"], burden=1),
        feature("invasive", ["yes", "no"], burden=3),
    ]
    rows = [
        evidence("infection", "lead", "yes", "strong_support"),
        evidence("growth", "lead", "yes", "weak_support"),
        evidence("infection", "cheap", "yes", "weak_support"),
        evidence("infection", "invasive", "yes", "strong_support"),
    ]
    base = build(features=features, rows=rows, red_flags=[])
    turn = build_turn_context(base, given={"lead": "yes"}, asked=["lead"])

    cheap = next(a for a in turn.askable if a.feature.id == "cheap")
    invasive = next(a for a in turn.askable if a.feature.id == "invasive")
    # Strong (1.5) against weak (0.6) is only 2.5x, short of the 3x burden gap.
    assert invasive.discrimination > cheap.discrimination
    assert invasive.value < cheap.value


def test_discrimination_responds_to_what_she_has_answered() -> None:
    """The property whose absence made the questions feel arbitrary: the
    ranking must move as the differential does."""
    base = build()
    opening = build_turn_context(base, given={}, asked=[])
    narrowed = build_turn_context(base, given={"fever": "yes"}, asked=["fever"])

    def score(turn: TurnContext, feature_id: str) -> float:
        return next(a.discrimination for a in turn.askable if a.feature.id == feature_id)

    # `bleeding` carries rows for growth and normal; once `infection` leads,
    # a question about the others is worth less than it was.
    assert score(opening, "bleeding") != score(narrowed, "bleeding")


def test_discrimination_falls_as_the_differential_narrows() -> None:
    """Live, not static — the property that makes the ranking track the
    conversation. ``separation`` stays put; ``discrimination`` must not."""
    base = build()
    opening = build_turn_context(base, given={}, asked=[])
    narrowed = build_turn_context(base, given={"fever": "yes"}, asked=["fever"])

    live_now = live_conditions(narrowed.evidence)
    assert live_now == {"infection"}

    def power(turn: TurnContext, feature_id: str) -> float:
        return next(a.discrimination for a in turn.askable if a.feature.id == feature_id)

    # `bleeding` carries rows for growth and normal, neither of which survives
    # once only `infection` is live — so its discrimination collapses, while
    # its static separation is unchanged.
    assert power(opening, "bleeding") > power(narrowed, "bleeding")
    assert separation(base, "bleeding") == 2


def test_screening_still_ignores_discrimination() -> None:
    """Severity and cost decide an escalation probe. How well a feature splits
    the differential says nothing about whether she is having an emergency."""
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain"])
    assert turn.askable[0].feature.id == "fever"
    assert turn.askable[0].resolves


def test_a_feature_that_neither_screens_nor_separates_is_not_offered() -> None:
    """A question whose answer changes nothing is burden without benefit."""
    base = build(
        features=[*(feature(f, ["yes", "no"]) for f in ("pain", "fever", "inert"))],
        rows=[evidence("infection", "fever", "yes", "strong_support")],
        red_flags=[],
    )
    turn = build_turn_context(base, given={}, asked=[])
    assert "inert" not in {a.feature.id for a in turn.askable}


def test_askable_carries_the_authored_probe_and_value_vocabulary() -> None:
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain"])
    fever = next(a for a in turn.askable if a.feature.id == "fever")
    assert fever.probe == "What about fever?"
    assert fever.allowed_values == ("yes", "no")


def test_an_already_answered_feature_is_never_offered_again() -> None:
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain"])
    assert "pain" not in {a.feature.id for a in turn.askable}


# -- separation -------------------------------------------------------------


def test_separation_counts_distinct_condition_value_pairs() -> None:
    base = build()
    # pain: normal/none, normal/severe, infection/severe, growth/severe
    assert separation(base, "pain") == 4
    # bleeding: growth/heavy, normal/heavy
    assert separation(base, "bleeding") == 2


def test_a_feature_no_row_mentions_separates_nothing() -> None:
    base = build(features=[*build().features, feature("unused", ["yes", "no"])])
    assert separation(base, "unused") == 0


# -- rendering --------------------------------------------------------------


def test_the_rendered_block_carries_the_clauses_not_just_the_label() -> None:
    """The defect this whole module exists to fix.

    ``render_red_flags`` sent id, action, label and quote — never ``all_of`` —
    so a model could not tell which answer a rule was waiting on.
    """
    block = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    assert "severe_pain_with_fever" in block
    assert "Outstanding: fever equals yes" in block


def test_the_block_names_the_feature_her_newest_message_answers() -> None:
    """The fix for answers being silently dropped.

    Observed live 2026-09-10: shown only a list of what was already answered,
    the model echoed that list back in ``observed`` instead of recording the
    reply it had just read, so "large clots, very heavy bleeding" never became
    ``bleeding_heaviness=heavy`` — a clause of an EMERGENCY rule.
    """
    turn = build_turn_context(build(), given={"pain": "severe"}, asked=["pain", "fever"])
    assert turn.pending is not None
    assert turn.pending.id == "fever"

    block = render_turn_context(turn)
    assert "HER NEWEST MESSAGE IS THE ANSWER TO: fever" in block
    assert 'observed["fever"]' in block
    assert "yes, no" in block


def test_there_is_no_pending_feature_once_every_answer_is_in() -> None:
    turn = build_turn_context(
        build(), given={"pain": "severe", "fever": "no"}, asked=["pain", "fever"]
    )
    assert turn.pending is None
    assert "HER NEWEST MESSAGE IS THE ANSWER TO" not in render_turn_context(turn)


def test_the_pending_feature_is_the_most_recent_unanswered_question() -> None:
    turn = build_turn_context(
        build(), given={"pain": "severe"}, asked=["pain", "fever", "bleeding"]
    )
    assert turn.pending is not None
    assert turn.pending.id == "bleeding"


def test_the_block_tells_the_model_not_to_echo_known_answers_back() -> None:
    block = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    assert "Do NOT repeat them back in `observed`" in block


def test_the_rendered_block_states_what_is_already_answered() -> None:
    block = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    assert "pain=severe" in block


def test_the_rendered_block_says_so_when_nothing_is_answered() -> None:
    block = render_turn_context(build_turn_context(build(), given={}))
    assert "nothing yet" in block
    assert "matching_conditions must be empty" in block


def test_the_rendered_block_shows_evidence_strength_and_quote() -> None:
    block = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    assert "[argues_against]" in block
    assert "pain severe relates to normal." in block


def test_rendering_is_stable_across_identical_inputs() -> None:
    first = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    second = render_turn_context(build_turn_context(build(), given={"pain": "severe"}))
    assert first == second


# -- the whole context ------------------------------------------------------


def test_build_turn_context_decides_nothing() -> None:
    """No action code is produced anywhere in this module.

    The guarantee ADR 0011 requires: this layer describes the position, the
    model chooses. If an action code ever appears in a ``TurnContext`` field,
    that is a controller growing back.
    """
    turn = build_turn_context(build(), given={"pain": "severe", "fever": "yes"})
    assert not hasattr(turn, "action_code")
    assert not hasattr(turn, "decision")
    # A fired rule carries the action its own YAML row declares — that is the
    # rule's data, not a choice made here.
    assert turn.fired is not None
    assert turn.fired.rule.action.value == "EMERGENCY"


def test_rank_askable_respects_its_limit() -> None:
    base = build()
    ranked = rank_askable(base, {}, [], assess_rules(base, {}), limit=2)
    assert len(ranked) == 2
