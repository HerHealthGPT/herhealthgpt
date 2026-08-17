"""Tests for the evaluation runner and the case schema.

Against the synthetic three-condition fixture, so an approved annotation batch
cannot break them for reasons that have nothing to do with the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from herhealth_contracts.evaluation import (
    CanonicalCase,
    CaseLabel,
    CaseVariant,
    EvaluationSet,
    Language,
    RegisterStyle,
)
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.loading import load_evaluation_set
from pydantic import ValidationError
from triage_factories import build

from herhealth_backend.evaluation.runner import failing_cases, run_case, run_evaluation
from herhealth_backend.triage.engine import TriageEngine


def label(
    action: ActionCode = ActionCode.ROUTINE_APPOINTMENT,
    *,
    clarify: bool = False,
    red_flag: str = "",
) -> CaseLabel:
    return CaseLabel(
        expected_action=action,
        needs_clarification=clarify,
        expected_red_flag_id=red_flag,
        label_quote="The reference answer sentence the label was read from.",
    )


def case(case_id: str, features: dict[str, str], **kwargs: object) -> CanonicalCase:
    return CanonicalCase(
        id=case_id,
        topic="Test",
        features=features,
        label=kwargs.pop("label", label()),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.fixture
def engine() -> TriageEngine:
    return TriageEngine(build())


# --------------------------------------------------------------------------
# The schema property that matters: a variant cannot carry a label
# --------------------------------------------------------------------------


def test_a_variant_cannot_carry_an_expected_action() -> None:
    """The whole point of the schema. Deriving labels per language is what
    produced French under-triage of 0.994; here a second opinion has nowhere
    to be written, so it cannot exist."""
    with pytest.raises(ValidationError):
        CaseVariant(
            canonical_case_id="c1",
            style=RegisterStyle.CLINICAL,
            language=Language.FR,
            text="Une question.",
            expected_action=ActionCode.SELF_CARE,  # type: ignore[call-arg]
        )


def test_variants_inherit_their_label_by_canonical_case_id() -> None:
    evaluation_set = EvaluationSet(
        cases=[case("c1", {"pain": "severe"}, label=label(ActionCode.URGENT_SAME_DAY))],
        variants=[
            CaseVariant(
                canonical_case_id="c1", style=s, language=lang, text=f"{s.value} {lang.value}"
            )
            for s in (RegisterStyle.CANONICAL, RegisterStyle.CLINICAL)
            for lang in (Language.EN, Language.FR, Language.AR)
        ],
    )
    expected = evaluation_set.cases_by_id["c1"].label.expected_action
    assert expected is ActionCode.URGENT_SAME_DAY
    assert len(evaluation_set.variants) == 6
    assert set(evaluation_set.languages) == {Language.EN, Language.FR, Language.AR}


def test_a_variant_with_no_case_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown canonical cases"):
        EvaluationSet(
            cases=[case("c1", {})],
            variants=[
                CaseVariant(
                    canonical_case_id="ghost",
                    style=RegisterStyle.CANONICAL,
                    language=Language.EN,
                    text="orphan",
                )
            ],
        )


def test_duplicate_case_ids_are_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate canonical case ids"):
        EvaluationSet(cases=[case("c1", {}), case("c1", {})])


def test_duplicate_variants_are_refused() -> None:
    variant = CaseVariant(
        canonical_case_id="c1",
        style=RegisterStyle.CANONICAL,
        language=Language.EN,
        text="same slot twice",
    )
    with pytest.raises(ValidationError, match="duplicate"):
        EvaluationSet(cases=[case("c1", {})], variants=[variant, variant])


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_out_of_scope_needs_a_reason() -> None:
    with pytest.raises(ValidationError, match="without a reason"):
        case("c1", {}, in_scope=False)


def test_in_scope_must_not_carry_a_reason() -> None:
    with pytest.raises(ValidationError, match="not mistaken for an exclusion"):
        case("c1", {}, out_of_scope_reason="pregnancy is not modelled")


def test_out_of_scope_cases_are_not_scored(engine: TriageEngine) -> None:
    evaluation_set = EvaluationSet(
        cases=[
            case("kept", {"pain": "none"}),
            case("dropped", {"pain": "none"}, in_scope=False, out_of_scope_reason="unmodelled"),
        ]
    )
    evaluation = run_evaluation(engine, evaluation_set)
    assert evaluation.metrics.cases_scored == 1
    assert evaluation.metrics.cases_out_of_scope == 1


def test_a_red_flag_label_may_not_expect_self_care() -> None:
    with pytest.raises(ValidationError, match="only escalates"):
        label(ActionCode.SELF_CARE, red_flag="severe_pain_with_fever")


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


def test_a_case_runs_and_produces_an_outcome(engine: TriageEngine) -> None:
    outcome, transcript = run_case(engine, case("c1", {"pain": "severe", "fever": "yes"}))
    assert outcome.canonical_case_id == "c1"
    assert outcome.predicted_action is ActionCode.EMERGENCY
    assert transcript.final_decision.should_stop


def test_the_fired_rule_is_recorded(engine: TriageEngine) -> None:
    outcome, _ = run_case(engine, case("c1", {"pain": "severe", "fever": "yes"}))
    assert outcome.fired_red_flag_id == "severe_pain_with_fever"


def test_transcripts_are_kept(engine: TriageEngine) -> None:
    """A failing metric is not actionable on its own — the question that should
    have been asked is in the trace and nowhere else."""
    evaluation = run_evaluation(engine, EvaluationSet(cases=[case("c1", {"pain": "none"})]))
    assert evaluation.transcripts["c1"].turns


def test_an_annotation_typo_is_refused_not_scored_as_a_miss(engine: TriageEngine) -> None:
    """It would move no score and read as an honest unknown, so the case would
    surface as a triage failure rather than the typo it is."""
    with pytest.raises(ValueError, match="not one of"):
        run_case(engine, case("c1", {"pain": "extreme"}))


def test_probes_are_distinguishable_from_clarifying_questions(engine: TriageEngine) -> None:
    """A question asked because a red flag already fired is the system
    confirming how bad things are, not asking what is going on. The two are
    told apart by `red_flag_id` on the decision that produced them.

    Note what this test does NOT claim. At controller level `asked_a_question`
    is effectively always true, because the controller starts with no answers
    and must ask before it can conclude anything. Clarification recall only
    becomes a real measurement end to end, where a model may answer straight
    from the prose without asking at all. Recorded here so the number is not
    read as a pass it did not earn.
    """
    engine_with_probe = TriageEngine(
        build(
            red_flags=[
                {
                    "id": "mild",
                    "label": "Mild",
                    "all_of": [{"feature_id": "pain", "op": "equals", "value": "severe"}],
                    "action": "URGENT_SAME_DAY",
                    "source_id": "src_a",
                    "source_quote": "Escalation language.",
                },
                {
                    "id": "worse",
                    "label": "Worse",
                    "all_of": [
                        {"feature_id": "pain", "op": "equals", "value": "severe"},
                        {"feature_id": "fever", "op": "equals", "value": "yes"},
                    ],
                    "action": "EMERGENCY",
                    "source_id": "src_a",
                    "source_quote": "Worse escalation language.",
                },
            ]
        )
    )
    outcome, transcript = run_case(
        engine_with_probe, case("c1", {"pain": "severe"}, label=label(clarify=True))
    )
    asked = [t for t in transcript.turns if t.answer]
    probes = [t for t in asked if t.decision.red_flag_id]
    ordinary = [t for t in asked if not t.decision.red_flag_id]

    assert probes, "the escalation screen should have run"
    assert ordinary, "the first question precedes any flag, so it is ordinary"
    assert outcome.asked_a_question


def test_failing_cases_lists_under_triage_and_missed_flags(engine: TriageEngine) -> None:
    evaluation = run_evaluation(
        engine,
        EvaluationSet(
            cases=[
                case("missed", {"pain": "none"}, label=label(ActionCode.EMERGENCY)),
                case("fine", {"pain": "none"}, label=label(ActionCode.SELF_CARE)),
            ]
        ),
    )
    assert [o.canonical_case_id for o in failing_cases(evaluation)] == ["missed"]


def test_over_triage_is_not_listed_as_a_failure(engine: TriageEngine) -> None:
    """It is a cost this design accepts; listing it would bury the real ones."""
    evaluation = run_evaluation(
        engine,
        EvaluationSet(
            cases=[case("loud", {"pain": "none"}, label=label(ActionCode.SELF_CARE))]
        ),
    )
    assert all(not o.over_triaged for o in failing_cases(evaluation))


# --------------------------------------------------------------------------
# Loading from files
# --------------------------------------------------------------------------


CASE_YAML = """
cases:
  - id: c1
    topic: Test
    features:
      pain: severe
    label:
      expected_action: URGENT_SAME_DAY
      label_quote: See a doctor today if the pain is severe.
variants:
  - canonical_case_id: c1
    style: canonical
    language: en
    text: My pain is severe.
"""


def test_a_batch_file_loads(tmp_path: Path) -> None:
    (tmp_path / "batch_01.yaml").write_text(CASE_YAML, encoding="utf-8")
    evaluation_set = load_evaluation_set(tmp_path)
    assert [c.id for c in evaluation_set.cases] == ["c1"]
    assert len(evaluation_set.variants) == 1


def test_several_batches_merge(tmp_path: Path) -> None:
    """Batches stay separately reviewable, same as evidence rows."""
    (tmp_path / "batch_01.yaml").write_text(CASE_YAML, encoding="utf-8")
    (tmp_path / "batch_02.yaml").write_text(CASE_YAML.replace("c1", "c2"), encoding="utf-8")
    assert len(load_evaluation_set(tmp_path).cases) == 2


def test_an_empty_directory_loads_to_nothing(tmp_path: Path) -> None:
    assert load_evaluation_set(tmp_path).cases == ()


def test_features_are_checked_against_the_knowledge_base(tmp_path: Path) -> None:
    (tmp_path / "b.yaml").write_text(
        CASE_YAML.replace("pain: severe", "no_such_feature: mild"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no such feature"):
        load_evaluation_set(tmp_path, build())


def test_yaml_booleans_become_value_tokens(tmp_path: Path) -> None:
    """REGRESSION. `fever: yes` parses as True under YAML 1.1, and roughly half
    the knowledge base is yes/no features — so this is the commonest line an
    annotator will write."""
    (tmp_path / "b.yaml").write_text(
        CASE_YAML.replace("pain: severe", "fever: yes"), encoding="utf-8"
    )
    assert load_evaluation_set(tmp_path, build()).cases[0].features == {"fever": "yes"}


def test_a_number_is_refused_rather_than_stringified(tmp_path: Path) -> None:
    """`30` becoming "30" would be a silent wrong answer that scores as a
    triage failure rather than as the typo it is."""
    (tmp_path / "b.yaml").write_text(
        CASE_YAML.replace("pain: severe", "pain: 30"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="quote it"):
        load_evaluation_set(tmp_path)


def test_a_value_outside_allowed_values_is_refused(tmp_path: Path) -> None:
    (tmp_path / "b.yaml").write_text(
        CASE_YAML.replace("pain: severe", "pain: extreme"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="is not one of"):
        load_evaluation_set(tmp_path, build())


def test_an_unknown_expected_red_flag_is_refused(tmp_path: Path) -> None:
    body = CASE_YAML.replace(
        "      label_quote:", "      expected_red_flag_id: ghost_rule\n      label_quote:"
    )
    (tmp_path / "b.yaml").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="no such red flag"):
        load_evaluation_set(tmp_path, build())
