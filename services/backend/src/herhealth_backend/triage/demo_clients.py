"""Offline triage clients for local MVP testing — no OpenRouter, no model service.

Wired when ``HERHEALTH_TRIAGE_MODE=demo`` (see ``app/config.py``). Uses the
same valid decisions as ``tests/app/test_triage_routes.py`` so vocabulary
and provenance checks pass against the real knowledge base.

The demo client picks a small scenario from the user's words so local testing
feels coherent. It is **not** clinical reasoning — switch to
``HERHEALTH_TRIAGE_MODE=openrouter`` for real triage.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

from herhealth_backend.triage.agent import Message

__all__ = ["DEMO_PASSAGE", "MvpDemoReasoningClient", "StaticRetrievalClient"]

DEMO_PASSAGE = RetrievedPassage(
    id="0123456789abcdef",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text="Irregular or heavy, painful periods are not normal.",
    citation="womenshealth/menstruation § Menstrual Cycle",
    score=0.7,
)

_HEAVY_BLEEDING_PASSAGE = RetrievedPassage(
    id="fedcba9876543210",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text=(
        "If you have heavy menstrual bleeding, talk with your doctor or nurse. "
        "You should also see your doctor if you have bleeding that does not stop."
    ),
    citation="womenshealth/heavy_menstrual_bleeding",
    score=0.7,
)


class _DemoScenario(StrEnum):
    PERSISTENT_BLEEDING = "persistent_bleeding"
    IRREGULAR_PERIODS = "irregular_periods"


def _user_text(history: Sequence[Message]) -> str:
    return " ".join(message.content.lower() for message in history if message.role == "user")


def _detect_scenario(text: str) -> _DemoScenario:
    persistent_bleeding_phrases = (
        "does not stop",
        "doesn't stop",
        "won't stop",
        "wont stop",
        "not stopping",
        "keep bleeding",
        "bleeding won't",
        "bleeding wont",
        "won't stop bleeding",
        "wont stop bleeding",
        "heavy bleeding",
        "soaking through",
        "soaking pads",
    )
    if any(phrase in text for phrase in persistent_bleeding_phrases):
        return _DemoScenario.PERSISTENT_BLEEDING
    return _DemoScenario.IRREGULAR_PERIODS


class StaticRetrievalClient:
    """Returns fixed passages for the active demo scenario."""

    def __init__(
        self,
        *,
        default_passages: tuple[RetrievedPassage, ...] = (DEMO_PASSAGE,),
        bleeding_passages: tuple[RetrievedPassage, ...] = (_HEAVY_BLEEDING_PASSAGE,),
    ) -> None:
        self._default_passages = default_passages
        self._bleeding_passages = bleeding_passages
        self._last_query = ""

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        self._last_query = query
        scenario = _detect_scenario(
            _user_text([Message(role="user", content=query)])
        )
        passages = (
            self._bleeding_passages
            if scenario is _DemoScenario.PERSISTENT_BLEEDING
            else self._default_passages
        )
        return list(passages[:k])


class MvpDemoReasoningClient:
    """Scenario-aware scripted triage for local MVP — ask once, then conclude."""

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        del system_prompt  # demo does not call a model
        passage_id = context[0].id if context else DEMO_PASSAGE.id
        user_turns = sum(1 for message in history if message.role == "user")
        scenario = _detect_scenario(_user_text(history))

        if scenario is _DemoScenario.PERSISTENT_BLEEDING:
            return self._decide_bleeding(user_turns=user_turns, passage_id=passage_id)
        return self._decide_irregular_periods(user_turns=user_turns, passage_id=passage_id)

    def _decide_bleeding(self, *, user_turns: int, passage_id: str) -> TriageDecision:
        if user_turns < 2:
            return TriageDecision(
                type=DecisionType.ASK,
                next_feature_id="bleeding_heaviness",
                question_text=(
                    "How heavy is the bleeding right now? For example, are you soaking "
                    "through a pad or tampon every hour, or passing clots larger than a coin?"
                ),
                citations=(passage_id,),
                rationale=(
                    "Bleeding that will not stop needs a clearer picture of how heavy it "
                    "is before I can suggest how urgently to seek care."
                ),
            )

        return TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.URGENT_SAME_DAY,
            matching_conditions=(),
            citations=(passage_id,),
            rationale=(
                "Bleeding that does not stop is something our sources say should be "
                "assessed soon rather than left for a routine appointment. Please contact "
                "a healthcare professional today. If you feel faint, dizzy, or very unwell, "
                "seek urgent care straight away. Urgency guidance only, from cited sources. "
                "Not a diagnosis."
            ),
        )

    def _decide_irregular_periods(self, *, user_turns: int, passage_id: str) -> TriageDecision:
        if user_turns < 2:
            return TriageDecision(
                type=DecisionType.ASK,
                next_feature_id="pregnancy_status",
                question_text="Are you currently pregnant or could you be?",
                citations=(passage_id,),
                rationale=(
                    "I need to know whether pregnancy could explain what you are "
                    "describing before I suggest what to do next."
                ),
            )

        return TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=ActionCode.ROUTINE_APPOINTMENT,
            matching_conditions=("pcos", "normal_variation"),
            citations=(passage_id,),
            rationale=(
                "Based on what you have shared, the patterns may fit conditions "
                "our sources associate with irregular periods. A routine "
                "appointment with a clinician would be sensible so someone can "
                "listen to you properly. Urgency guidance only, from cited "
                "sources. Not a diagnosis."
            ),
        )
