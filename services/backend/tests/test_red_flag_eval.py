"""The red-flag recall cases: derived from red_flags.yaml, one per rule."""

from __future__ import annotations

from pathlib import Path

from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.evaluation.red_flag_eval import case_message, rule_cases, score
from herhealth_backend.triage.context import build_turn_context

BASE = load_knowledge_base(Path(__file__).resolve().parents[3] / "knowledge")


def test_there_is_one_case_per_rule() -> None:
    assert [rule.id for rule, _ in rule_cases(BASE)] == [rule.id for rule in BASE.red_flags]


def test_every_case_fires_its_rule_or_a_more_severe_one() -> None:
    severity = {a.code: a.severity for a in BASE.actions.actions}
    for rule, features in rule_cases(BASE):
        context = build_turn_context(BASE, given=features, asked=[], prose=())
        assert context.fired is not None, rule.id
        assert severity[context.fired.rule.action] >= severity[rule.action], rule.id


def test_every_case_value_is_allowed_for_its_feature() -> None:
    for _, features in rule_cases(BASE):
        for feature_id, value in features.items():
            allowed = {str(v) for v in BASE.features_by_id[feature_id].allowed_values}
            assert value in allowed, (feature_id, value)


def test_the_words_mode_message_names_each_feature() -> None:
    rule, features = rule_cases(BASE)[0]
    message = case_message(BASE, features)
    for feature_id in features:
        assert BASE.features_by_id[feature_id].label in message


def test_scoring_counts_a_question_and_a_lower_conclusion_as_misses() -> None:
    records = [
        {
            "rule_id": "a",
            "action": "EMERGENCY",
            "mode": "answers",
            "type": "conclude",
            "action_given": "EMERGENCY",
            "red_flag_given": "a",
        },
        {
            "rule_id": "b",
            "action": "EMERGENCY",
            "mode": "answers",
            "type": "conclude",
            "action_given": "URGENT_SAME_DAY",
            "red_flag_given": None,
        },
        {
            "rule_id": "c",
            "action": "URGENT_SAME_DAY",
            "mode": "answers",
            "type": "ask",
            "action_given": None,
            "red_flag_given": None,
        },
    ]
    summary = score(records, BASE)["answers"]
    assert summary["recall"] == 1 / 3
    assert summary["outcomes"] == {"escalated": 1, "concluded lower": 1, "ask instead": 1}
    assert summary["by_level"] == {"EMERGENCY": "1/2", "URGENT_SAME_DAY": "0/1"}
