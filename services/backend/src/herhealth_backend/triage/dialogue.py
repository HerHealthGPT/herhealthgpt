"""Run a whole consultation and keep the trace.

The engine decides one turn at a time. This drives it to a conclusion and
records every step, so a consultation can be inspected after the fact: which
question was chosen, what it was worth, how the differential moved, and which of
the six rules ended it.

Pure. No printing, no files, no argument parsing — those are in ``cli.py``. The
evaluation harness will import :func:`run_consultation` directly and score the
transcripts rather than re-implementing the loop, which is the point of keeping
the loop out of the CLI.

**The user is a lookup, not a script of turns.** A case says what is true of a
person — ``heavy_bleeding: yes``, ``age_band: over_40`` — and the controller
decides what to ask. Encoding a case as an ordered list of answers would bake
the question order into the fixture and hide the very thing under test.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from herhealth_contracts.knowledge import UNKNOWN_VALUE, Feature

from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import Answer, Decision, TriageState

__all__ = [
    "AnswerProvider",
    "ScriptedAnswers",
    "Transcript",
    "Turn",
    "run_consultation",
]

#: Given the feature the controller chose, return a value for it. Returning
#: :data:`UNKNOWN_VALUE` is always legal and means "she did not say".
AnswerProvider = Callable[[Feature], str]


@dataclass(frozen=True, slots=True)
class Turn:
    """One decision and, if it was a question, the answer that followed."""

    number: int

    #: The state the decision was made from — before the answer was applied.
    state: TriageState

    decision: Decision

    #: None on the final turn, which concluded rather than asked.
    answer: Answer | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    """A finished consultation."""

    turns: tuple[Turn, ...]

    #: The state after the last answer was applied. The decision was made from
    #: it, so this is what the final differential describes.
    final_state: TriageState

    final_decision: Decision

    @property
    def questions_asked(self) -> int:
        return self.final_state.questions_asked

    @property
    def answers(self) -> tuple[Answer, ...]:
        return self.final_state.answers


class ScriptedAnswers:
    """A fixed set of facts about one person, answered on demand.

    Anything not in the mapping comes back as ``unknown``, which is how a case
    says "she was asked and did not know" without having to enumerate all fifty
    features.
    """

    def __init__(self, answers: Mapping[str, str]) -> None:
        self._answers = dict(answers)

    def __call__(self, feature: Feature) -> str:
        return self._answers.get(feature.id, UNKNOWN_VALUE)

    @property
    def answers(self) -> Mapping[str, str]:
        return dict(self._answers)

    @classmethod
    def validated(
        cls, answers: Mapping[str, str], features: Mapping[str, Feature]
    ) -> ScriptedAnswers:
        """Build one, refusing anything the knowledge base would not recognise.

        Checked rather than tolerated, because a typo is silently dangerous
        here: an unrecognised value would be applied, match no evidence row,
        move no score, and read exactly like an honest ``unknown``. A case that
        was meant to escalate would quietly come back routine and nothing in the
        output would say why.
        """
        problems: list[str] = []
        for feature_id, value in answers.items():
            feature = features.get(feature_id)
            if feature is None:
                problems.append(f"no such feature: {feature_id!r}")
                continue
            allowed = (*feature.allowed_values, UNKNOWN_VALUE)
            if feature.allowed_values and value not in allowed:
                problems.append(
                    f"{feature_id}={value!r} is not one of {', '.join(sorted(allowed))}"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return cls(answers)


def run_consultation(
    engine: TriageEngine, provider: AnswerProvider, *, hard_limit: int | None = None
) -> Transcript:
    """Ask until the controller stops, recording every turn.

    ``hard_limit`` bounds the loop independently of ``max_questions``. The
    engine already stops at its budget and never re-asks a feature, so this
    cannot trigger in normal operation — it is there so a future bug in question
    selection surfaces as a clear error rather than a hung process.
    """
    limit = hard_limit if hard_limit is not None else len(engine.base.features) + 1
    features = engine.base.features_by_id

    state = engine.initial_state()
    turns: list[Turn] = []

    for number in range(1, limit + 1):
        decision = engine.should_stop(state)

        if decision.should_stop:
            turns.append(Turn(number=number, state=state, decision=decision))
            return Transcript(
                turns=tuple(turns), final_state=state, final_decision=decision
            )

        assert decision.next_feature_id is not None  # ASK always carries one
        feature = features[decision.next_feature_id]
        value = provider(feature)
        turns.append(
            Turn(
                number=number,
                state=state,
                decision=decision,
                answer=Answer(feature_id=feature.id, value=value),
            )
        )
        state = engine.update(state, feature.id, value)

    raise RuntimeError(
        f"the controller asked {limit} questions without stopping; "
        "question selection is repeating itself"
    )
