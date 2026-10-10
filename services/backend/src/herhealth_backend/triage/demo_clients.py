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

from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningResult,
)

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


#: Enough to exercise the decline path offline — the three shapes of
#: off-scope message ADR 0014 names (not health at all, men's health, health
#: outside this scope). Deliberately a crude keyword list: it stands in for a
#: scope judgement the real reasoning model makes from the system prompt, and
#: pretending otherwise would make ``demo`` mode look like it validates that
#: judgement. Same disclaimer ``MvpDemoReasoningClient`` already carries.
_OUT_OF_SCOPE_PHRASES = (
    "world cup",
    "super bowl",
    "football",
    "election",
    "president",
    "weather",
    "prostate",
    "erectile",
    "testicle",
    "my penis",
    "chest pain",
    "sore throat",
    "sprained",
    "twisted my knee",
)


def _user_text(history: Sequence[Message]) -> str:
    return " ".join(message.content.lower() for message in history if message.role == "user")


def _is_out_of_scope(text: str) -> bool:
    return any(phrase in text for phrase in _OUT_OF_SCOPE_PHRASES)


#: What an in-scope question with no case behind it looks like (ADR 0016).
#: As crude and as deliberately crude as _OUT_OF_SCOPE_PHRASES above: the
#: real judgement is the model's, made from the system prompt, and a keyword
#: list here must not be read as evidence that it works.
#:
#: Each phrase asks about the subject, not about her. The guard below also
#: requires that she said nothing in the first person about herself, because
#: "what is PCOS, I have really irregular periods" is a consultation that
#: opened with a question — and triage wins that tie, as the prompt says.
_INFORMATIONAL_OPENERS = (
    "what is ",
    "what are ",
    "what causes",
    "what does ",
    "whats ",
    "what's ",
    "how common",
    "how long does",
    "tell me about",
    "can you explain",
    "explain ",
    "definition of",
)

#: First-person symptom talk. Any of these and the message is triaged, not
#: answered, however much it also reads like a question.
_FIRST_PERSON_SYMPTOM_MARKERS = (
    "i have",
    "i've",
    "ive ",
    "i am",
    "i'm",
    "im ",
    "my period",
    "my pain",
    "my bleeding",
    "my symptoms",
    "mine",
    "should i",
    "do i need",
    "am i",
    "me?",
)


def _is_informational(text: str) -> bool:
    """A question about the subject, with no case of her own in it."""
    if any(marker in text for marker in _FIRST_PERSON_SYMPTOM_MARKERS):
        return False
    return any(opener in text for opener in _INFORMATIONAL_OPENERS)


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

    #: Named like the real clients so a demo turn is attributable too — a
    #: screenshot of a demo answer should never be mistakable for a served one.
    name = "demo:scripted"

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        """Wraps :meth:`_decide` so the scripted body keeps its many return
        points instead of every one of them having to build a result."""
        return ReasoningResult(
            decision=self._decide(
                system_prompt=system_prompt, history=history, context=context
            ),
            attempts=(ReasoningAttempt(client=self.name, outcome=AttemptOutcome.OK),),
        )

    def _decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        del system_prompt  # demo does not call a model
        passage_id = context[0].id if context else DEMO_PASSAGE.id
        user_turns = sum(1 for message in history if message.role == "user")

        # Scope is judged on the newest message alone, unlike the two health
        # scenarios below, which read the whole transcript so a follow-up
        # ("yes", "about 3 months") stays in the scenario it belongs to. An
        # off-scope aside must be declined on its own terms without an
        # earlier in-scope complaint dragging it into a triage answer, and
        # must not taint the turns after it either.
        latest_message = next(
            (message.content.lower() for message in reversed(history) if message.role == "user"),
            "",
        )
        if _is_out_of_scope(latest_message):
            return self._decline()

        if _is_informational(latest_message):
            return self._inform(passage_id)

        scenario = _detect_scenario(_user_text(history))
        if scenario is _DemoScenario.PERSISTENT_BLEEDING:
            return self._decide_bleeding(user_turns=user_turns, passage_id=passage_id)
        return self._decide_irregular_periods(user_turns=user_turns, passage_id=passage_id)

    def _inform(self, passage_id: str) -> TriageDecision:
        """An in-scope question about the subject, answered — see ADR 0016.

        No action code and no named condition, so this demo answer cannot be
        mistaken for a verdict on anyone's case.
        """
        return TriageDecision(
            type=DecisionType.INFORM,
            answer_text=(
                "Polycystic ovary syndrome is a common condition affecting how the "
                "ovaries work. Our sources describe three main features: periods "
                "that are irregular or absent, higher-than-usual levels of "
                "androgens, which can show up as extra hair growth or acne, and "
                "ovaries that look enlarged on a scan. It is often linked to how "
                "the body handles insulin, which is why weight, blood sugar and "
                "fertility come up alongside it. There is no cure described, but "
                "the symptoms are treatable, and which treatment fits depends on "
                "which symptoms matter most to you.\n\n"
                "That is general information about the condition, not an "
                "assessment of anything you are experiencing. If some of this "
                "sounds like you, tell me what you have noticed and I will ask a "
                "few questions."
            ),
            citations=(passage_id,),
            rationale=(
                "She asked what the condition is, without describing anything she "
                "is experiencing, so this is a question to answer rather than a "
                "symptom to assess."
            ),
        )

    def _decline(self) -> TriageDecision:
        """No action code, no citation — see ADR 0014."""
        return TriageDecision(
            type=DecisionType.DECLINE,
            rationale=(
                "I'm sorry — I can't help with that one. This tool covers women's "
                "reproductive health only, and does not provide diagnoses. If it is "
                "a health worry, please take it to a doctor or pharmacist, and seek "
                "urgent medical help now if it feels serious. If you do have a "
                "reproductive-health concern, tell me about it and I'll help."
            ),
        )

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
