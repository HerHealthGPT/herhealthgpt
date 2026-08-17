"""Run an evaluation set through the controller.

No model in the loop. Cases are expressed as feature values, so this measures
the controller alone: given what the user said, does the stopping policy reach
the right action, ask when it should, and never miss a red flag?

That boundary is the point. The end-to-end evaluation — prose in, action out —
needs a model to turn a sentence into feature values, and it will confound two
different failures: the model extracted the wrong feature, or the controller
reasoned wrongly from the right one. Measuring the controller first means the
end-to-end number can later be read against a known baseline instead of being
the only number there is.

Because the input is feature values, the register variants collapse to identical
runs. That is honest rather than wasteful: it makes register agreement a
tautology at this level (the metrics report ``None`` rather than a flattering
1.0), and the variants are still carried so the same labels serve the
end-to-end run without re-annotation.

**Two gated metrics are close to vacuous here, and that must be stated rather
than enjoyed.**

- *Cross-language and register agreement* return ``None``, because each case
  runs once from language-independent input. Nothing to compare, so nothing is
  claimed.
- *Clarification recall* is effectively a guaranteed 1.0. The controller starts
  with no answers and cannot conclude before asking, so it always asks. The
  metric only becomes a real measurement end to end, where a model may answer
  straight from the prose without asking at all.

Unlike agreement, clarification recall cannot report ``None`` — the controller
genuinely did ask, and saying otherwise would be false. So it is reported at
face value with this caveat attached wherever it is printed. A 1.000 here is a
true statement about a question that was never hard.
"""

from __future__ import annotations

from dataclasses import dataclass

from herhealth_contracts.evaluation import CanonicalCase, EvaluationSet, Language, RegisterStyle
from herhealth_contracts.knowledge import ActionCode

from herhealth_backend.evaluation.metrics import CaseOutcome, Metrics, score
from herhealth_backend.triage.dialogue import ScriptedAnswers, Transcript, run_consultation
from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import StopReason

__all__ = ["Evaluation", "run_case", "run_evaluation"]


@dataclass(frozen=True, slots=True)
class Evaluation:
    """The scored run, with every transcript kept.

    Transcripts are retained rather than discarded because a failing metric on
    its own is not actionable — the question that should have been asked and was
    not is in the trace, and nowhere else.
    """

    metrics: Metrics
    outcomes: tuple[CaseOutcome, ...]
    transcripts: dict[str, Transcript]

    @property
    def passed(self) -> bool:
        return not self.metrics.gated_failures()


def run_case(engine: TriageEngine, case: CanonicalCase) -> tuple[CaseOutcome, Transcript]:
    """Run one case and score it.

    The answers are validated against the knowledge base first. An unrecognised
    value would move no score and read exactly like an honest ``unknown``, so it
    would surface as a triage failure rather than as the annotation error it is.
    """
    provider = ScriptedAnswers.validated(case.features, engine.base.features_by_id)
    transcript = run_consultation(engine, provider)
    decision = transcript.final_decision

    outcome = CaseOutcome(
        canonical_case_id=case.id,
        # Feature values carry no language; the label was derived from English
        # and reaches every other language through canonical_case_id.
        language=Language.EN,
        style=RegisterStyle.CANONICAL,
        expected_action=case.label.expected_action,
        # A decision always carries an action unless it is still asking, and
        # run_consultation only returns once it has stopped. Defaulting to the
        # most urgent rather than the least would flatter the numbers, so this
        # falls back to the label-independent floor and lets it score as a miss.
        predicted_action=decision.action or ActionCode.SELF_CARE,
        expected_red_flag_id=case.label.expected_red_flag_id,
        fired_red_flag_id=transcript.final_state.fired_red_flag_id,
        needs_clarification=case.label.needs_clarification,
        asked_a_question=_asked_a_question(transcript),
        questions_asked=transcript.questions_asked,
    )
    return outcome, transcript


def _asked_a_question(transcript: Transcript) -> bool:
    """Whether the controller sought clarification before concluding.

    Escalation probes do not count. A question asked because a red flag already
    fired is the system confirming how bad things are, not asking what is going
    on, and counting it would let a case score as "clarified" on a consultation
    that never clarified anything.
    """
    return any(
        turn.answer is not None and turn.decision.red_flag_id is None
        for turn in transcript.turns
    )


def run_evaluation(engine: TriageEngine, evaluation_set: EvaluationSet) -> Evaluation:
    """Run every in-scope case."""
    outcomes: list[CaseOutcome] = []
    transcripts: dict[str, Transcript] = {}

    for case in evaluation_set.scored:
        outcome, transcript = run_case(engine, case)
        outcomes.append(outcome)
        transcripts[case.id] = transcript

    return Evaluation(
        metrics=score(
            outcomes,
            out_of_scope=len(evaluation_set.cases) - len(evaluation_set.scored),
        ),
        outcomes=tuple(outcomes),
        transcripts=transcripts,
    )


def failing_cases(evaluation: Evaluation) -> tuple[CaseOutcome, ...]:
    """Under-triaged cases and missed red flags, worst first.

    Deliberately not "everything that was not exact". Over-triage is a cost this
    design accepts, and listing it beside missed escalations would bury the ones
    that matter.
    """
    interesting = [
        outcome
        for outcome in evaluation.outcomes
        if outcome.under_triaged
        or (
            outcome.expected_red_flag_id
            and outcome.fired_red_flag_id != outcome.expected_red_flag_id
        )
    ]
    return tuple(
        sorted(interesting, key=lambda o: (-len(o.expected_red_flag_id), o.canonical_case_id))
    )


def stop_reason_counts(evaluation: Evaluation) -> dict[StopReason, int]:
    """How the consultations ended.

    Reported because it explains the other numbers. A run that is almost all
    ``max_questions`` is a run where the differential never resolved, which is a
    knowledge-base problem rather than a threshold problem.
    """
    counts: dict[StopReason, int] = {}
    for transcript in evaluation.transcripts.values():
        reason = transcript.final_decision.reason
        counts[reason] = counts.get(reason, 0) + 1
    return counts
