"""A small knowledge base built in memory, for testing the controller.

NOT conftest.py — see services/data/tests/ingest_factories.py for why plain
helper functions must live in a uniquely-named module.

Deliberately not the real one. These tests are about the controller's logic, and
pinning them to real clinical rows would mean every approved evidence batch
could break them for reasons that have nothing to do with the code.

The fixture is shaped to exercise the decisions rather than to be clinically
realistic: three conditions with three different baseline actions, so that
"do all live conditions share an action" can be both true and false.
"""

from __future__ import annotations

from typing import Any

from herhealth_contracts.knowledge import KnowledgeBase


def feature(feature_id: str, values: list[str], burden: int = 1) -> dict[str, Any]:
    return {
        "id": feature_id,
        "label": feature_id.replace("_", " ").title(),
        "kind": "categorical",
        "allowed_values": values,
        "burden": burden,
        "probe": {"en": f"What about {feature_id}?"},
    }


def condition(condition_id: str, action: str) -> dict[str, Any]:
    return {
        "id": condition_id,
        "label": condition_id.title(),
        "baseline_action": action,
        "source_ids": ["src_a", "src_b"],
    }


def evidence(condition_id: str, feature_id: str, value: str, strength: str) -> dict[str, Any]:
    return {
        "condition_id": condition_id,
        "feature_id": feature_id,
        "value": value,
        "strength": strength,
        "source_id": "src_a",
        "source_quote": f"{feature_id} {value} relates to {condition_id}.",
    }


def source(source_id: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "name": source_id,
        "url": f"https://example.org/{source_id}",
        "precedence": 3,
        "licence": "Public domain",
        "access": "pages",
        "status": "available",
    }


WEIGHTS: dict[str, Any] = {
    "log_odds": {
        "strong_support": 1.5,
        "weak_support": 0.6,
        "neutral": 0.0,
        "argues_against": -0.5,
        "rules_out": -4.0,
    },
    "plausibility_floor": 0.05,
    "stop_confidence": 0.65,
    "self_care_stop_confidence": 0.85,
    "stop_margin": 0.15,
    "max_questions": 6,
}

ACTIONS: dict[str, Any] = {
    "actions": [
        {"code": "SELF_CARE", "severity": 0, "description": "Manage at home."},
        {"code": "ROUTINE_APPOINTMENT", "severity": 1, "description": "See someone soon."},
        {"code": "URGENT_SAME_DAY", "severity": 2, "description": "Be seen today."},
        {"code": "EMERGENCY", "severity": 3, "description": "Seek emergency care."},
    ]
}


def build(
    *,
    features: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    rows: list[dict[str, Any]] | None = None,
    red_flags: list[dict[str, Any]] | None = None,
    weights: dict[str, Any] | None = None,
) -> KnowledgeBase:
    return KnowledgeBase(
        features=features or DEFAULT_FEATURES,
        conditions=conditions or DEFAULT_CONDITIONS,
        evidence=rows or DEFAULT_ROWS,
        red_flags=red_flags or DEFAULT_RED_FLAGS,
        sources=[source("src_a"), source("src_b")],
        weights=weights or WEIGHTS,
        actions=ACTIONS,
    )


DEFAULT_FEATURES = [
    feature("pain", ["none", "mild", "severe"], burden=1),
    feature("fever", ["yes", "no"], burden=1),
    feature("bleeding", ["light", "heavy"], burden=2),
    feature("private_question", ["yes", "no"], burden=5),
]

#: Three baselines, so shared-action can be true or false depending on which
#: conditions survive.
DEFAULT_CONDITIONS = [
    condition("infection", "URGENT_SAME_DAY"),
    condition("growth", "ROUTINE_APPOINTMENT"),
    condition("normal", "SELF_CARE"),
]

DEFAULT_ROWS = [
    evidence("infection", "fever", "yes", "strong_support"),
    evidence("infection", "pain", "severe", "weak_support"),
    evidence("growth", "bleeding", "heavy", "strong_support"),
    evidence("growth", "pain", "severe", "weak_support"),
    evidence("normal", "pain", "none", "strong_support"),
    evidence("normal", "pain", "severe", "argues_against"),
    evidence("normal", "bleeding", "heavy", "argues_against"),
    evidence("infection", "private_question", "yes", "weak_support"),
]

DEFAULT_RED_FLAGS = [
    {
        "id": "severe_pain_with_fever",
        "label": "Severe pain with fever",
        "all_of": [
            {"feature_id": "pain", "op": "equals", "value": "severe"},
            {"feature_id": "fever", "op": "equals", "value": "yes"},
        ],
        "action": "EMERGENCY",
        "source_id": "src_a",
        "source_quote": "Seek emergency care for severe pain with a fever.",
    }
]


