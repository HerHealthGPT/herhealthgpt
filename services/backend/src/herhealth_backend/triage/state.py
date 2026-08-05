"""What a consultation knows so far, and what the controller decides.

Pure data. No logic beyond arithmetic on values already held, so a state can be
constructed in a test, printed, compared and stored without anything else being
present — no knowledge base, no model, no server.

Everything here is immutable. :func:`update` returns a new state rather than
mutating one, which means a consultation is a list of states and any of them can
be replayed. That is what makes a scripted dialogue reproducible and what will
let the evaluation harness explain *why* a case went the way it did.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from herhealth_contracts.knowledge import UNKNOWN_VALUE, ActionCode
from herhealth_contracts.scoring import plausibility

__all__ = ["Answer", "Decision", "StopReason", "TriageState"]


@dataclass(frozen=True, slots=True)
class Answer:
    """One question asked and answered.

    ``value`` may be :data:`UNKNOWN_VALUE`, meaning the user did not say. That
    is recorded rather than discarded: the controller must not ask again, and an
    evaluation needs to distinguish "asked and unknown" from "never asked".
    """

    feature_id: str
    value: str

    @property
    def is_known(self) -> bool:
        return self.value != UNKNOWN_VALUE


class StopReason(StrEnum):
    """Why the controller stopped, or did not.

    These are the six branches of ``should_stop``, in the order they are
    checked. The order is the policy: a red flag outranks everything, and
    running out of questions is the last resort rather than a normal ending.
    """

    #: A deterministic escalation rule matched. No model call, no differential.
    RED_FLAG = "red_flag"

    #: Every condition still plausible implies the same action, so asking more
    #: cannot change what the user is told.
    SHARED_ACTION = "shared_action"

    #: No unasked question could change the action. Asking would only cost the
    #: user time.
    NO_INFORMATIVE_QUESTION = "no_informative_question"

    #: One condition is clearly ahead of the rest.
    CONFIDENT = "confident"

    #: The question budget ran out. Stops with the differential, not an answer.
    MAX_QUESTIONS = "max_questions"

    #: Not a stop. Ask the next question.
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class TriageState:
    """Everything known at one point in a consultation."""

    #: Accumulated log-odds per condition. Starts at 0.0 for every condition,
    #: which is plausibility 0.5 — no evidence either way, not "unlikely".
    scores: Mapping[str, float]

    #: In the order asked, which is also the order they were answered.
    answers: tuple[Answer, ...] = ()

    #: The rule that fired, if one did. Holding the rule rather than a boolean
    #: means the response can cite the sentence the escalation came from.
    fired_red_flag_id: str | None = None

    @property
    def questions_asked(self) -> int:
        return len(self.answers)

    @property
    def asked_feature_ids(self) -> frozenset[str]:
        """Every feature already put to the user, including unknown answers."""
        return frozenset(answer.feature_id for answer in self.answers)

    def answer_for(self, feature_id: str) -> str | None:
        for answer in self.answers:
            if answer.feature_id == feature_id:
                return answer.value
        return None

    def plausibilities(self) -> dict[str, float]:
        """Each condition's score converted to 0-1, independently."""
        return {condition_id: plausibility(score) for condition_id, score in self.scores.items()}

    def live(self, floor: float) -> dict[str, float]:
        """Conditions still plausible enough to matter, highest first."""
        above = {c: p for c, p in self.plausibilities().items() if p >= floor}
        return dict(sorted(above.items(), key=lambda item: -item[1]))

    def ranked(self) -> list[tuple[str, float]]:
        """Every condition by plausibility, highest first."""
        return sorted(self.plausibilities().items(), key=lambda item: -item[1])


@dataclass(frozen=True, slots=True)
class Decision:
    """What the controller decided, and enough context to explain it."""

    reason: StopReason

    #: The action to return. None only when the reason is ASK.
    action: ActionCode | None = None

    #: The feature to ask about. None unless the reason is ASK.
    next_feature_id: str | None = None

    #: Conditions above the floor, highest plausibility first. Present on every
    #: decision, because a user told "see someone today" is owed the reason, and
    #: an evaluation cannot diagnose an error without it.
    differential: tuple[tuple[str, float], ...] = ()

    #: Set when the reason is RED_FLAG, so the response can cite the rule. Also
    #: set on an ASK issued while a flag is already fired — the controller is
    #: then probing for a worse rule, and the question is not an ordinary one.
    red_flag_id: str | None = None

    #: One line of why, for logs and for the scripted-dialogue CLI.
    explanation: str = ""

    #: Populated by the caller when it matters; kept out of __init__ ordering.
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def should_stop(self) -> bool:
        return self.reason is not StopReason.ASK
