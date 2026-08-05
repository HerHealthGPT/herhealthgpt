"""Tests for the scripted-dialogue CLI.

Unlike the rest of the backend suite, these run against the REAL knowledge base.
That is deliberate and it is the point of the CLI: the controller had only ever
been exercised against a three-condition fixture, and the behaviour worth
pinning is what it does with twelve real conditions and eighty-nine real rows.

The cost is that an approved evidence batch can fail these. That is the
intended alarm, not a nuisance — a new row that changes what a demonstration
case is told should be seen by a person before it merges. When one fails, run
the case and read the trace before touching the assertion.

No network, no model, no server. Only files already in the repository.

Named test_triage_cli rather than test_cli because services/data/tests already
has a test_cli.py, and pytest resolves test modules by basename across the whole
run — two files sharing one would abort collection for the entire suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.cli import (
    DISCLAIMER,
    as_json,
    build_parser,
    find_knowledge_dir,
    load_case,
    main,
    parse_inline,
)
from herhealth_backend.triage.dialogue import ScriptedAnswers, run_consultation
from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import StopReason

REPO = Path(__file__).resolve().parents[3]
KNOWLEDGE = REPO / "knowledge"
CASES = REPO / "services" / "backend" / "cases"

ALL_CASES = sorted(CASES.glob("*.yaml"))


@pytest.fixture(scope="module")
def real_engine() -> TriageEngine:
    return TriageEngine(load_knowledge_base(KNOWLEDGE))


def run(name: str, engine: TriageEngine):  # type: ignore[no-untyped-def]
    _, answers = load_case(CASES / f"{name}.yaml")
    provider = ScriptedAnswers.validated(answers, engine.base.features_by_id)
    return run_consultation(engine, provider)


# --------------------------------------------------------------------------
# The real knowledge base loads and runs
# --------------------------------------------------------------------------


def test_the_real_knowledge_base_loads() -> None:
    base = load_knowledge_base(KNOWLEDGE)
    assert base.conditions and base.features and base.evidence and base.red_flags


def test_the_shipped_cases_are_all_valid(real_engine: TriageEngine) -> None:
    """Every case file names real features and legal values."""
    assert ALL_CASES, "no case files found"
    for path in ALL_CASES:
        _, answers = load_case(path)
        ScriptedAnswers.validated(answers, real_engine.base.features_by_id)


@pytest.mark.parametrize("path", ALL_CASES, ids=lambda p: p.stem)
def test_every_case_reaches_a_conclusion(path: Path, real_engine: TriageEngine) -> None:
    transcript = run(path.stem, real_engine)
    assert transcript.final_decision.should_stop
    assert transcript.final_decision.action is not None


# --------------------------------------------------------------------------
# Pinned behaviour, per case
# --------------------------------------------------------------------------


def test_sudden_severe_pain_reaches_emergency(real_engine: TriageEngine) -> None:
    """REGRESSION, and the reason the assertion is this specific.

    This used to assert only "some red flag fired", which passed while the case
    came back URGENT_SAME_DAY. Sudden onset of severe pelvic pain matches
    `sudden_severe_pelvic_pain`, an EMERGENCY rule; the controller was matching
    the one-clause `severe_pelvic_pain` rule on severity alone and concluding
    before it ever asked about onset.
    """
    decision = run("sudden_severe_pain", real_engine).final_decision
    assert decision.reason is StopReason.RED_FLAG
    assert decision.action is ActionCode.EMERGENCY
    assert decision.red_flag_id == "sudden_severe_pelvic_pain"


def test_reaching_emergency_costs_the_escalation_screen(
    real_engine: TriageEngine,
) -> None:
    """The price of the fix, pinned so a change to it is visible.

    Six EMERGENCY rules are each one answer from firing once severe pelvic pain
    is known, so the screen runs past `max_questions`. That is deliberate — the
    question budget is about patience, and emergency screening is not subject
    to it — but it is a real cost and it should not drift silently.
    """
    transcript = run("sudden_severe_pain", real_engine)
    assert transcript.questions_asked > real_engine.weights.max_questions
    probes = [t for t in transcript.turns if t.answer and t.decision.red_flag_id]
    assert len(probes) == 6


def test_a_red_flag_cites_the_sentence_it_came_from(real_engine: TriageEngine) -> None:
    """A user told to seek care today is owed the reason, and the reason is a
    quote from a named source, not a paraphrase."""
    decision = run("sudden_severe_pain", real_engine).final_decision
    rule = next(r for r in real_engine.base.red_flags if r.id == decision.red_flag_id)
    assert rule.source_quote.strip()
    assert rule.source_id in real_engine.base.sources_by_id


def test_severe_pain_is_never_answered_with_self_care(real_engine: TriageEngine) -> None:
    decision = run("sudden_severe_pain", real_engine).final_decision
    assert decision.action is not ActionCode.SELF_CARE


def test_itching_and_discharge_does_not_conclude_self_care(
    real_engine: TriageEngine,
) -> None:
    """Thrush is in the differential and carries SELF_CARE, but so is pelvic
    inflammatory disease. Concluding "manage it at home" while an urgent
    condition is unexcluded is the failure this project exists to avoid."""
    decision = run("itching_and_discharge", real_engine).final_decision
    assert decision.action is not ActionCode.SELF_CARE


def test_saying_nothing_asks_the_full_budget(real_engine: TriageEngine) -> None:
    transcript = run("says_nothing", real_engine)
    assert transcript.final_decision.reason is StopReason.MAX_QUESTIONS
    assert transcript.questions_asked == real_engine.weights.max_questions


def test_saying_nothing_moves_no_score(real_engine: TriageEngine) -> None:
    """Every answer unknown, so every condition stays where it started."""
    transcript = run("says_nothing", real_engine)
    assert set(transcript.final_state.scores.values()) == {0.0}


def test_no_case_ends_below_its_most_urgent_live_condition(
    real_engine: TriageEngine,
) -> None:
    """The invariant, checked against real conditions rather than a fixture."""
    severities = {a.code: a.severity for a in real_engine.base.actions.actions}
    conditions = real_engine.base.conditions_by_id

    for path in ALL_CASES:
        decision = run(path.stem, real_engine).final_decision
        if decision.reason is StopReason.RED_FLAG:
            continue  # a red flag answers on its own terms, not the differential
        worst = max(
            (severities[conditions[c].baseline_action] for c, _ in decision.differential),
            default=0,
        )
        assert decision.action is not None
        assert severities[decision.action] >= worst, path.stem


# --------------------------------------------------------------------------
# Case-file parsing
# --------------------------------------------------------------------------


def test_yaml_booleans_become_value_tokens(tmp_path: Path) -> None:
    """REGRESSION. `fever: yes` parses as True under YAML 1.1, not "yes"."""
    path = tmp_path / "c.yaml"
    path.write_text("answers:\n  fever: yes\n  vulval_itching: no\n", encoding="utf-8")
    assert load_case(path)[1] == {"fever": "yes", "vulval_itching": "no"}


def test_a_number_is_refused_rather_than_stringified(tmp_path: Path) -> None:
    """`1.0` becoming "1.0" would be a silent wrong answer, not a near miss."""
    path = tmp_path / "c.yaml"
    path.write_text("answers:\n  age_band: 30\n", encoding="utf-8")
    with pytest.raises(ValueError, match="quote it in the case file"):
        load_case(path)


def test_a_case_without_answers_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("name: nothing here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no 'answers' mapping"):
        load_case(path)


def test_a_case_falls_back_to_its_filename(tmp_path: Path) -> None:
    path = tmp_path / "unnamed.yaml"
    path.write_text("answers: {}\n", encoding="utf-8")
    assert load_case(path)[0] == "unnamed"


def test_inline_answers_parse() -> None:
    assert parse_inline(["fever=yes", "age_band=30_to_39"]) == {
        "fever": "yes",
        "age_band": "30_to_39",
    }


@pytest.mark.parametrize("bad", ["fever", "fever=", "=yes", ""])
def test_a_malformed_inline_answer_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="expected feature=value"):
        parse_inline([bad])


# --------------------------------------------------------------------------
# Locating the knowledge base
# --------------------------------------------------------------------------


def test_the_explicit_path_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERHEALTH_KNOWLEDGE_DIR", str(tmp_path / "env"))
    assert find_knowledge_dir(tmp_path / "flag") == tmp_path / "flag"


def test_the_environment_is_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERHEALTH_KNOWLEDGE_DIR", str(tmp_path / "env"))
    assert find_knowledge_dir() == tmp_path / "env"


def test_otherwise_it_is_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never a walk up the tree: that silently finds a different knowledge base
    depending on where you were standing."""
    monkeypatch.delenv("HERHEALTH_KNOWLEDGE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert find_knowledge_dir() == tmp_path / "knowledge"


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def test_json_output_is_serialisable(real_engine: TriageEngine) -> None:
    payload = as_json(run("heavy_periods_over_40", real_engine), "x")
    assert json.loads(json.dumps(payload))["stop_reason"]


def test_json_output_carries_the_disclaimer(real_engine: TriageEngine) -> None:
    assert as_json(run("says_nothing", real_engine), "x")["disclaimer"] == DISCLAIMER


def test_the_disclaimer_does_not_claim_a_diagnosis() -> None:
    """No string in this system may describe it as diagnosing."""
    assert "not a diagnosis" in DISCLAIMER.lower()


def test_a_conclusion_always_prints_the_disclaimer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--knowledge", str(KNOWLEDGE), "--case", str(CASES / "says_nothing.yaml")])
    assert DISCLAIMER in capsys.readouterr().out


def test_a_bad_knowledge_directory_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--knowledge", str(tmp_path)]) == 2
    assert "could not load" in capsys.readouterr().err


def test_a_bad_case_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--knowledge", str(KNOWLEDGE), "--answer", "nope=yes"]) == 2
    assert "bad case" in capsys.readouterr().err


def test_a_good_run_exits_zero_or_one() -> None:
    """One means EMERGENCY, so a shell script can key on it."""
    assert main(["--knowledge", str(KNOWLEDGE), "--case", str(CASES / "says_nothing.yaml")]) in (
        0,
        1,
    )


def test_the_parser_accepts_repeated_answers() -> None:
    args = build_parser().parse_args(["--answer", "a=1", "--answer", "b=2"])
    assert args.answer == ["a=1", "b=2"]
