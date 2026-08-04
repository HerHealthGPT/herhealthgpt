"""Tests for the knowledge schemas.

Weighted toward the invariants that exist for safety reasons: source_quote is
mandatory, neutral rows are rejected, red flags cannot de-escalate, and the
SELF_CARE bar is strictly higher than the ROUTINE_APPOINTMENT one.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from herhealth_contracts.knowledge import (
    ActionCode,
    Actions,
    Condition,
    EvidenceRow,
    EvidenceStrength,
    Feature,
    FeatureKind,
    FeaturesFile,
    KnowledgeBase,
    RedFlagRule,
    Source,
    Weights,
)


def evidence_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "condition_id": "pcos",
        "feature_id": "cycle_regularity",
        "value": "irregular",
        "strength": "strong_support",
        "source_id": "nichd_pcos",
        "source_quote": "Irregular menstrual periods are a common sign of PCOS.",
    }
    row.update(overrides)
    return row


def red_flag(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "id": "soaking_pad_hourly",
        "label": "Bleeding through a pad every hour",
        "all_of": [{"feature_id": "bleeding_heaviness", "op": "equals", "value": "soaking_hourly"}],
        "action": "URGENT_SAME_DAY",
        "source_id": "nichd_bleeding",
        "source_quote": "Get help if you are soaking through a pad every hour.",
    }
    rule.update(overrides)
    return rule


def weights(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "log_odds": {
            "strong_support": 1.5,
            "weak_support": 0.6,
            "neutral": 0.0,
            "argues_against": -0.8,
            "rules_out": -4.0,
        },
        "plausibility_floor": 0.05,
        "stop_confidence": 0.65,
        "self_care_stop_confidence": 0.85,
        "stop_margin": 0.15,
    }
    values.update(overrides)
    return values


# --------------------------------------------------------------------------
# source_quote — the verification protocol
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_evidence_row_rejects_empty_source_quote(bad: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceRow(**evidence_row(source_quote=bad))


def test_evidence_row_requires_source_quote_at_all() -> None:
    row = evidence_row()
    del row["source_quote"]
    with pytest.raises(ValidationError):
        EvidenceRow(**row)


@pytest.mark.parametrize("bad", ["", "   "])
def test_red_flag_rejects_empty_source_quote(bad: str) -> None:
    with pytest.raises(ValidationError):
        RedFlagRule(**red_flag(source_quote=bad))


def test_source_quote_is_stripped_but_preserved() -> None:
    row = EvidenceRow(**evidence_row(source_quote="  a real sentence.  "))
    assert row.source_quote == "a real sentence."


def test_no_clinician_review_field_exists() -> None:
    """The protocol replaces review with traceability; no flag may imply otherwise."""
    fields = set(EvidenceRow.model_fields) | set(RedFlagRule.model_fields)
    assert not [f for f in fields if "clinic" in f or "review" in f or "approv" in f]

    # extra="forbid" means one cannot be smuggled in either.
    with pytest.raises(ValidationError):
        EvidenceRow(**evidence_row(reviewed_by_clinician=True))


# --------------------------------------------------------------------------
# Evidence rows
# --------------------------------------------------------------------------


def test_neutral_is_rejected_because_it_means_omit_the_row() -> None:
    with pytest.raises(ValidationError, match="sparse"):
        EvidenceRow(**evidence_row(strength="neutral"))


def test_all_four_usable_strengths_are_accepted() -> None:
    usable = set(EvidenceStrength) - {EvidenceStrength.NEUTRAL}
    for strength in usable:
        assert EvidenceRow(**evidence_row(strength=strength.value)).strength is strength


def test_unknown_strength_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceRow(**evidence_row(strength="probably"))


# --------------------------------------------------------------------------
# Red flags
# --------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["SELF_CARE", "ROUTINE_APPOINTMENT"])
def test_red_flag_may_not_de_escalate(action: str) -> None:
    with pytest.raises(ValidationError, match="only escalate"):
        RedFlagRule(**red_flag(action=action))


@pytest.mark.parametrize("action", ["URGENT_SAME_DAY", "EMERGENCY"])
def test_red_flag_accepts_escalating_actions(action: str) -> None:
    assert RedFlagRule(**red_flag(action=action)).action is ActionCode(action)


def test_red_flag_needs_at_least_one_clause() -> None:
    with pytest.raises(ValidationError):
        RedFlagRule(**red_flag(all_of=[]))


def test_in_clause_requires_a_list() -> None:
    with pytest.raises(ValidationError):
        RedFlagRule(
            **red_flag(all_of=[{"feature_id": "age_band", "op": "in", "value": "over_45"}])
        )


def test_gte_clause_requires_a_number() -> None:
    with pytest.raises(ValidationError):
        RedFlagRule(**red_flag(all_of=[{"feature_id": "age", "op": "gte", "value": "old"}]))


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------


def feature(**overrides: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "id": "cycle_regularity",
        "label": "Cycle regularity",
        "kind": "categorical",
        "allowed_values": ["regular", "irregular", "absent"],
        "burden": 1,
        "probe": {"en": "Are your periods usually regular?"},
    }
    f.update(overrides)
    return f


def test_probe_must_include_english() -> None:
    with pytest.raises(ValidationError, match="'en'"):
        Feature(**feature(probe={"fr": "Vos regles sont-elles regulieres ?"}))


def test_probe_mapping_accepts_future_languages_without_migration() -> None:
    f = Feature(**feature(probe={"en": "Are your periods regular?", "ar_eg": "..."}))
    assert set(f.probe) == {"en", "ar_eg"}


def test_unknown_is_never_an_allowed_value() -> None:
    with pytest.raises(ValidationError, match="implicit"):
        Feature(**feature(allowed_values=["regular", "irregular", "unknown"]))


def test_numeric_feature_must_not_enumerate_values() -> None:
    with pytest.raises(ValidationError, match="numeric"):
        Feature(**feature(kind="numeric", allowed_values=["1", "2"]))


def test_categorical_feature_must_enumerate_values() -> None:
    with pytest.raises(ValidationError, match="allowed_values"):
        Feature(**feature(allowed_values=[]))


def test_boolean_feature_must_be_yes_no() -> None:
    with pytest.raises(ValidationError, match="yes"):
        Feature(**feature(kind="boolean", allowed_values=["true", "false"]))
    assert Feature(**feature(kind="boolean", allowed_values=["yes", "no"]))


def test_burden_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Feature(**feature(burden=9))


def test_duplicate_feature_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate feature id"):
        FeaturesFile(features=[feature(), feature()])


# --------------------------------------------------------------------------
# Conditions
# --------------------------------------------------------------------------


def test_condition_needs_two_sources() -> None:
    with pytest.raises(ValidationError):
        Condition(
            id="pcos",
            label="Polycystic ovary syndrome",
            baseline_action="ROUTINE_APPOINTMENT",
            source_ids=["nichd_pcos"],
        )


def test_icd_defaults_to_todo_verify() -> None:
    c = Condition(
        id="pcos",
        label="Polycystic ovary syndrome",
        baseline_action="ROUTINE_APPOINTMENT",
        source_ids=["nichd_pcos", "medlineplus_pcos"],
    )
    assert c.icd11 == "TODO_VERIFY"


# --------------------------------------------------------------------------
# Sources — licensing status
# --------------------------------------------------------------------------


def source(**overrides: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "id": "nichd_pcos",
        "name": "NICHD PCOS",
        "url": "https://www.nichd.nih.gov/health/topics/pcos",
        "precedence": 3,
        "licence": "US federal, public domain",
        "access": "page ingestion",
        "status": "available",
    }
    s.update(overrides)
    return s


def test_status_is_required_so_unchecked_licensing_cannot_default_to_usable() -> None:
    s = source()
    del s["status"]
    with pytest.raises(ValidationError):
        Source(**s)


@pytest.mark.parametrize(
    ("status", "citable", "ingestible"),
    [
        ("available", True, True),
        ("citable_only", True, False),
        ("restricted", False, False),
    ],
)
def test_permissions_follow_status(status: str, citable: bool, ingestible: bool) -> None:
    s = Source(**source(status=status))
    assert s.may_be_cited is citable
    assert s.may_be_ingested is ingestible


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Source(**source(status="probably_fine"))


def test_precedence_ranks_sources_that_are_not_yet_usable() -> None:
    """NICE CKS outranks everything and is unusable; both facts must be storable."""
    cks = Source(**source(id="nice_cks", precedence=1, status="restricted"))
    assert cks.precedence == 1
    assert not cks.may_be_cited


# --------------------------------------------------------------------------
# Weights — the tunable constants
# --------------------------------------------------------------------------


def test_self_care_bar_must_exceed_the_routine_bar() -> None:
    with pytest.raises(ValidationError, match="under-triage"):
        Weights(**weights(self_care_stop_confidence=0.60))


def test_equal_bars_are_rejected_not_merely_lower_ones() -> None:
    with pytest.raises(ValidationError, match="under-triage"):
        Weights(**weights(self_care_stop_confidence=0.65, stop_confidence=0.65))


def test_log_odds_must_be_monotonic() -> None:
    broken = weights()["log_odds"] | {"weak_support": 2.0}
    with pytest.raises(ValidationError, match="monotonic"):
        Weights(**weights(log_odds=broken))


def test_neutral_must_be_zero() -> None:
    broken = weights()["log_odds"] | {"neutral": 0.3}
    with pytest.raises(ValidationError, match="absence of evidence"):
        Weights(**weights(log_odds=broken))


def test_all_five_strengths_must_be_present() -> None:
    partial = {k: v for k, v in weights()["log_odds"].items() if k != "rules_out"}
    with pytest.raises(ValidationError, match="rules_out"):
        Weights(**weights(log_odds=partial))


def test_max_questions_defaults_to_six() -> None:
    assert Weights(**weights()).max_questions == 6


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------


def action_defs() -> list[dict[str, Any]]:
    return [
        {"code": "SELF_CARE", "severity": 0, "description": "Manage at home."},
        {"code": "ROUTINE_APPOINTMENT", "severity": 1, "description": "Arrange an appointment."},
        {"code": "URGENT_SAME_DAY", "severity": 2, "description": "Be seen today."},
        {"code": "EMERGENCY", "severity": 3, "description": "Seek emergency care now."},
    ]


def test_all_four_actions_required() -> None:
    with pytest.raises(ValidationError, match="EMERGENCY"):
        Actions(actions=action_defs()[:3])


def test_severity_must_increase_with_urgency() -> None:
    scrambled = action_defs()
    scrambled[0]["severity"] = 9
    with pytest.raises(ValidationError, match="severity"):
        Actions(actions=scrambled)


# --------------------------------------------------------------------------
# The loaded whole
# --------------------------------------------------------------------------


def knowledge_base(**overrides: Any) -> dict[str, Any]:
    kb: dict[str, Any] = {
        "features": [feature()],
        "conditions": [
            {
                "id": "pcos",
                "label": "Polycystic ovary syndrome",
                "baseline_action": "ROUTINE_APPOINTMENT",
                "source_ids": ["nichd_pcos", "medlineplus_pcos"],
            }
        ],
        "evidence": [evidence_row()],
        "red_flags": [red_flag()],
        "sources": [source()],
        "weights": weights(),
        "actions": {"actions": action_defs()},
    }
    kb.update(overrides)
    return kb


def test_knowledge_base_loads() -> None:
    kb = KnowledgeBase(**knowledge_base())
    assert kb.features_by_id["cycle_regularity"].kind is FeatureKind.CATEGORICAL
    assert kb.conditions_by_id["pcos"].baseline_action is ActionCode.ROUTINE_APPOINTMENT
    assert "nichd_pcos" in kb.sources_by_id


def test_duplicate_evidence_cells_are_rejected() -> None:
    duplicated = [evidence_row(), evidence_row(strength="weak_support")]
    with pytest.raises(ValidationError, match="duplicate"):
        KnowledgeBase(**knowledge_base(evidence=duplicated))


def test_same_feature_different_value_is_not_a_duplicate() -> None:
    rows = [
        evidence_row(),
        evidence_row(
            value="regular",
            strength="argues_against",
            source_quote="Regular cycles make PCOS less likely.",
        ),
    ]
    assert len(KnowledgeBase(**knowledge_base(evidence=rows)).evidence) == 2


def test_typo_in_a_column_name_fails_loudly() -> None:
    with pytest.raises(ValidationError):
        EvidenceRow(**evidence_row(strenght="strong_support"))


def test_models_are_frozen() -> None:
    row = EvidenceRow(**evidence_row())
    with pytest.raises(ValidationError):
        row.strength = EvidenceStrength.RULES_OUT  # type: ignore[misc]


# --------------------------------------------------------------------------
# The single-source exception (ADR 0006)
# --------------------------------------------------------------------------


def test_one_source_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cites only one source"):
        Condition(
            id="adenomyosis",
            label="Adenomyosis",
            baseline_action="ROUTINE_APPOINTMENT",
            source_ids=["nhs"],
        )


def test_one_source_with_a_reason_is_accepted() -> None:
    condition = Condition(
        id="adenomyosis",
        label="Adenomyosis",
        baseline_action="ROUTINE_APPOINTMENT",
        source_ids=["nhs"],
        single_source_reason="No second usable source exists; NHS covers it across three pages.",
    )
    assert condition.single_source_reason


def test_a_reason_alongside_two_sources_is_rejected() -> None:
    """So the field cannot become a standing exemption nobody notices."""
    with pytest.raises(ValidationError, match="standing exemption"):
        Condition(
            id="pcos",
            label="PCOS",
            baseline_action="ROUTINE_APPOINTMENT",
            source_ids=["medlineplus", "nichd"],
            single_source_reason="unnecessary",
        )


def test_whitespace_is_not_a_reason() -> None:
    with pytest.raises(ValidationError, match="cites only one source"):
        Condition(
            id="adenomyosis",
            label="Adenomyosis",
            baseline_action="ROUTINE_APPOINTMENT",
            source_ids=["nhs"],
            single_source_reason="   ",
        )


def test_zero_sources_is_still_rejected() -> None:
    with pytest.raises(ValidationError):
        Condition(
            id="ghost",
            label="Ghost",
            baseline_action="ROUTINE_APPOINTMENT",
            source_ids=[],
            single_source_reason="trying to cite nothing at all",
        )
