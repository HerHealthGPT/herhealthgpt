"""The model-driven consultation loop that replaces the deterministic controller.

See docs/adr/0011-controller-free-triage.md. ``engine.py``, ``state.py`` and
the ``should_stop``-based ``dialogue.run_consultation`` are UNTOUCHED by this
file and still exist — this is new, additive code sitting next to them so it
can be reviewed and tested before anything is deleted (ADR 0011 migration
step 5; step 3, the bootstrap dataset, already ran — see
``bootstrap_dataset.py``).

Two seams, both ``Protocol``s, so nothing here needs a real model or a real
vector index to import or to test:

* :class:`ReasoningClient` — one call, one turn: history and retrieved
  context in, a validated :class:`~herhealth_contracts.decision.TriageDecision`
  out. Guided decoding against ``TriageDecision.model_json_schema()`` is
  expected to happen on the other side of this seam (``services/model``);
  Pydantic validates again on receipt here, because a client that already
  returned invalid JSON would otherwise fail somewhere less legible than this.
* :class:`RetrievalClient` — a query string in, ``RetrievedPassage`` hits out.
  ``services/data``'s ``PassageIndex.search`` does the real work; nothing here
  knows its return type, only
  :class:`herhealth_contracts.retrieval.RetrievedPassage`.

What this module deliberately does **not** do: decide anything. Every
``should_stop`` rule from ``engine.py`` is gone. The only code-level judgement
left is ``max_turns`` — a hard, dumb loop bound, not a policy — and even that
produces no action code on its own; see :class:`MaxTurnsExceeded`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase, RedFlagRule
from herhealth_contracts.retrieval import RetrievedPassage

__all__ = [
    "AgentTranscript",
    "AgentTurn",
    "DEFAULT_SYSTEM_PROMPT",
    "MaxTurnsExceeded",
    "Message",
    "ReasoningClient",
    "RetrievalClient",
    "ScriptedReasoningClient",
    "TriageAgent",
    "build_retrieval_query",
    "render_red_flags",
    "render_feature_vocabulary",
]

#: The canonical system prompt. Owns three rules code cannot check on its own.
#: First, scope: an off-scope message must be DECLINED, never answered and
#: never assigned an urgency. The schema (see decision.py) can guarantee a
#: decline carries no action code and no citation, but only this text can
#: decide that "who won world cup 2026" is one — hence the instruction
#: leading the prompt rather than trailing it. Second, medicines: this tool
#: never tells her to take, start, stop or dose a drug, even when the rest
#: of the message is in-scope period pain or PCOS — a named tablet is still
#: a prescribing question, and prescribing is diagnosing by another name.
#: Third, and the framing rule that matters most:
#: the model may say what she described MATCHES a cited pattern, and may
#: name which authored conditions match — but must never say she HAS a
#: condition. A red-flag-driven conclusion names no condition either —
#: EXCEPT at EMERGENCY, the one deliberate exception (a product decision,
#: 2026-09-02 — see decision.py's docstring and ADR 0013), where naming the
#: matching patterns is allowed alongside the red flag.
#: TriageDecision.matching_conditions enforces all of that in code, not
#: just here — see decision.py. "Never diagnose" is CLAUDE.md's binding
#: rule; this is what enforcing it in the prompt actually looks like, in
#: words a model is asked to follow rather than code that can check it.
#: `bootstrap_dataset.py` imports this rather than defining its own, so the
#: bootstrap data and the served prompt never drift apart.
DEFAULT_SYSTEM_PROMPT = (
    "You are an AI triage assistant for reproductive-health questions, not a "
    "clinician, and you must never diagnose — never tell her she \"has\" a "
    "condition. "
    "SCOPE COMES FIRST, BEFORE ANY OTHER INSTRUCTION HERE. You cover women's "
    "reproductive health, and only what the warning signs and retrieved "
    "passages below can actually ground. If the message is about anything "
    "else — not a health question at all (sport, news, politics, general "
    "trivia, coding, or anything similar), a men's health concern, or a "
    "health concern outside women's reproductive health such as chest pain, "
    "a cough or sore throat, an injury, or a mental-health crisis — you must "
    "answer with type \"decline\". A decline says plainly that this tool "
    "covers women's reproductive health only and does not provide diagnoses, "
    "and, when hers was a health question, that a doctor or pharmacist is "
    "the right place to take it. Never answer an off-scope question on its "
    "merits, never assign it an urgency level, and never attach a citation "
    "to it: the passages below were retrieved by similarity and one will "
    "always come back, but a passage that does not address what she asked is "
    "not evidence for anything. Do not stretch an unrelated question into a "
    "reproductive-health one to make it answerable. If she is plainly in "
    "danger but it is outside this scope, still decline, and say in your own "
    "words that she should seek urgent medical help now — that is not a "
    "triage verdict, it is telling her this tool is the wrong one. "
    "For anything inside scope, everything below applies. "
    "MEDICINES ARE NEVER YOURS TO ADVISE. If she asks whether to take, start, "
    "stop, buy, or dose a medicine — named or not, branded or generic, "
    "prescription or from a pharmacy, including painkillers such as ibuprofen "
    "or paracetamol, the contraceptive pill, metformin, antibiotics, or "
    "anything a pharmacist might sell — do not tell her to take it, do not "
    "tell her not to take it as if you had reviewed her, and do not suggest "
    "a dose or an alternative drug. Say plainly that you cannot diagnose and "
    "cannot advise on medicines, and that a doctor or pharmacist must decide "
    "whether that medicine is right for her. If the same message also "
    "describes in-scope symptoms, you may still ask about those symptoms or "
    "give urgency guidance for them — but the medicine question itself is "
    "always referred out. Never use SELF_CARE as a way of saying yes, take "
    "the tablet. "
    "Be genuinely thorough before you conclude: a single message "
    "is almost never enough to conclude safely, so in most consultations ask "
    "at least two or three clarifying questions — one per turn — about the "
    "things that would actually change your guidance (how long, how severe, "
    "how sudden, her age, pregnancy possibility, related symptoms) before "
    "giving an urgency level. Conclude on the first turn only when a red-flag "
    "warning sign below clearly applies, or when what she describes is so "
    "clearly minor that asking more would not change the guidance. When you "
    "conclude, you may name which of our authored conditions her answers "
    "match, always phrased as a possibility grounded in evidence, never as a "
    "conclusion about what is wrong with her — for example: \"Based on your "
    "answers, this may match patterns our sources associate with PCOS or "
    "perimenopause.\" Name only a handful of the closest matches (at most "
    "five, and usually fewer) — a long list of everything not yet ruled out "
    "is not useful guidance. When a red-flag warning sign is the reason for "
    "concluding, name a specific condition only if the urgency is EMERGENCY — "
    "at EMERGENCY, do name the matching conditions so she knows what patterns "
    "the warning sign relates to; at any lesser urgency a red-flag conclusion "
    "names no condition, because red flags escalate on a symptom pattern "
    "without asserting what it is. Every citation, whether for a matched "
    "condition or an urgency level, is tied to a cited source. Ask one "
    "clarifying question at a time, or give urgency guidance — exactly one "
    "of SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, or EMERGENCY — or "
    "decline as scope requires. "
    "Remind her plainly, in your own words, that you are an AI tool, not a "
    "clinician, and that this is based on her answers and the cited "
    "evidence, not a diagnosis. End every in-scope reply, question or final "
    "answer alike, with: \"Urgency guidance only, from cited sources. Not a "
    "diagnosis.\" A decline ends differently, because it rests on no source "
    "and gives no urgency: end that one with \"This tool covers women's "
    "reproductive health only, and does not provide diagnoses.\" "
    "Under-triage is the dominant failure mode: when in doubt, "
    "prefer sending her to care sooner rather than later — and when in "
    "doubt between asking and concluding, ask."
)


@dataclass(frozen=True, slots=True)
class Message:
    """One line of conversation. ``role`` is ``"system"``, ``"user"`` or ``"assistant"``."""

    role: str
    content: str


@runtime_checkable
class RetrievalClient(Protocol):
    """Anything that can turn a query into ranked, cited passages."""

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]: ...


@runtime_checkable
class ReasoningClient(Protocol):
    """Anything that can turn a turn's inputs into a validated decision."""

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision: ...


class MaxTurnsExceeded(RuntimeError):
    """The turn cap was reached without a CONCLUDE decision.

    Deliberately not resolved here into an action code — inventing one in
    code would be exactly the kind of decision this design moved out of
    Python. The caller (the API layer) decides what the user sees, and must
    decide it knowing this is not a triage outcome, just a budget running out.
    """


def render_feature_vocabulary(base: KnowledgeBase) -> str:
    """Every feature id the model may put in ``next_feature_id`` — injected
    so OpenRouter's plain-JSON mode cannot plausibly claim no id was available.
    """
    ids = ", ".join(sorted(base.features_by_id.keys()))
    return (
        "Closed vocabulary for next_feature_id (ASK decisions only — pick one, "
        f"never invent): {ids}"
    )


#: How many of the most recent user messages join the opening complaint in a
#: composed retrieval query. Enough to carry the thread of a consultation,
#: short enough that the newest answer still moves the embedding.
_QUERY_RECENT_ANSWERS = 3


def build_retrieval_query(history: Sequence[Message]) -> str:
    """The query to retrieve on for this turn: the opening complaint plus the
    most recent answers, not the newest message alone.

    Retrieving on ``history[-1]`` alone is a correctness bug, not the tuning
    question :meth:`TriageAgent.run_consultation` used to call it. Answers in
    a real consultation are short — "yes", "about 3 months", "I'm 34" — and
    embedding one in isolation retrieves whatever that fragment happens to
    look like, not what the consultation is about. Measured against the live
    index (2026-09-03): across eleven follow-up answers to three openers, the
    top-8 passage set on turn two overlapped turn one's by **0 of 8, every
    single time**, and "yes" retrieved "Yes and no. PCOS affects many systems
    in the body."

    That is what makes it a correctness bug rather than a quality one:
    ``vocabulary.validate_against_knowledge_base`` requires every citation to
    be among the passages retrieved *this* turn, so a model that quite
    correctly still cites the evidence behind the question it just asked
    trips ``ClosedVocabularyViolation``, and the API turns that into a 502.
    Composing the query keeps the consultation's own subject in the
    embedding; :meth:`TriageAgent.run_turn`'s ``carried_context`` closes the
    remaining gap for citations that still fall out of the window.
    """
    user_messages = [m.content.strip() for m in history if m.role == "user" and m.content.strip()]
    if not user_messages:
        return ""
    if len(user_messages) == 1:
        return user_messages[0]
    # The opener carries the subject; the tail carries what has been learned
    # since. Everything in between is dropped rather than summarised — this
    # is a retrieval query, not the transcript, which the model still gets in
    # full (see routes.py: the verbatim history is replayed every turn).
    return " ".join([user_messages[0], *user_messages[-_QUERY_RECENT_ANSWERS:]])


def render_red_flags(red_flags: Sequence[RedFlagRule]) -> str:
    """Every red flag, verbatim, as the block injected into every turn.

    Not retrieved — see docs/adr/0011-controller-free-triage.md, "the flow,
    end to end": retrieval is approximate, and a rule that fires because a
    sentence scored 0.71 cosine is not what "red flag" meant when it was
    code. Rendered fresh per call; callers making many turns from one
    :class:`KnowledgeBase` should cache the result themselves.

    Each line leads with ``red_flag_id=`` for the same reason
    :func:`render_feature_vocabulary` lists every feature id: the model is
    asked to put a real ``red_flags.yaml`` id in
    ``TriageDecision.red_flag_id``, and until 2026-09-03 this block showed
    it only the human ``label``, so it had to reverse-engineer the id from
    prose. It reverse-engineered it wrong — observed live on a
    severe-pain-with-faintness case: ``red_flag_id=
    "sudden_severe_pelvic_pain_emergency"``, the label snake-cased with the
    action appended, against a real id of ``sudden_severe_pelvic_pain``.
    That trips ``vocabulary.ClosedVocabularyViolation`` and the API returns
    502, so an emergency escalation was lost to a naming guess. Showing the
    id is the fix; the ids were always the contract, they were just never
    shown.
    """
    lines = [
        "Known warning signs — check every one of these against what she has said. "
        "Use the red_flag_id EXACTLY as written when one applies; never adjust it, "
        "extend it, or build one from the description:"
    ]
    for rule in red_flags:
        lines.append(
            f'- red_flag_id={rule.id} ({rule.action.value}) — {rule.label}: "{rule.source_quote}"'
        )
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AgentTurn:
    """One decision, and what it was made from."""

    history_before: tuple[Message, ...]
    retrieved: tuple[RetrievedPassage, ...]
    decision: TriageDecision


@dataclass(frozen=True, slots=True)
class AgentTranscript:
    """A finished consultation, model-driven turns only."""

    turns: tuple[AgentTurn, ...]
    final_decision: TriageDecision

    @property
    def turns_taken(self) -> int:
        return len(self.turns)


@dataclass(frozen=True, slots=True)
class TriageAgent:
    """Owns nothing but the loop. Every decision belongs to ``reasoning``."""

    base: KnowledgeBase
    reasoning: ReasoningClient
    retrieval: RetrievalClient
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_turns: int = 12

    def run_turn(
        self,
        history: Sequence[Message],
        *,
        query: str | None = None,
        k: int = 8,
        carried_context: Sequence[RetrievedPassage] = (),
    ) -> AgentTurn:
        """One retrieve-then-reason step. Does not mutate ``history``.

        ``query`` defaults to :func:`build_retrieval_query` over ``history``
        — pass one explicitly only to retrieve on something other than the
        conversation itself. ``carried_context`` is passages this
        consultation already showed the model on earlier turns, typically the
        ones it cited; they are merged into this turn's retrieval so a
        citation the model carries forward is still valid against
        ``vocabulary.validate_against_knowledge_base``, which checks
        citations against ``AgentTurn.retrieved``. Without it, a consultation
        that spans turns cannot cite its own earlier evidence without
        failing, because each turn re-runs an approximate similarity search
        whose result set is not stable across turns — see
        :func:`build_retrieval_query` for the measurement.

        Merging rather than replacing: fresh hits come first (they answer
        what she just said), carried ones fill the tail, deduplicated by
        passage id.
        """
        hits = self.retrieval.search(query or build_retrieval_query(history), k=k)
        by_id = {passage.id: passage for passage in hits}
        for passage in carried_context:
            by_id.setdefault(passage.id, passage)
        context = tuple(by_id.values())
        system = (
            f"{self.system_prompt}\n\n"
            f"{render_feature_vocabulary(self.base)}\n\n"
            f"{render_red_flags(self.base.red_flags)}"
        )
        decision = self.reasoning.decide(system_prompt=system, history=history, context=context)
        return AgentTurn(history_before=tuple(history), retrieved=context, decision=decision)

    def run_consultation(
        self, opening_message: str, answer_provider: Callable[[TriageDecision], str]
    ) -> AgentTranscript:
        """Loop until CONCLUDE or ``max_turns``.

        ``answer_provider`` mirrors ``dialogue.AnswerProvider``'s role — it is
        how a test or a script supplies what the user says next, given the
        question the model just asked. The retrieval query each turn is
        composed from the conversation by :func:`build_retrieval_query`, and
        every passage cited so far is carried forward into the next turn's
        context — see :meth:`run_turn`. Both used to be "the most recent
        message only", which that function's docstring records as a measured
        correctness bug rather than the tuning question it was assumed to be.
        """
        history: list[Message] = [Message(role="user", content=opening_message)]
        turns: list[AgentTurn] = []
        cited_so_far: dict[str, RetrievedPassage] = {}

        for _ in range(self.max_turns):
            turn = self.run_turn(history, carried_context=tuple(cited_so_far.values()))
            turns.append(turn)
            by_id = {passage.id: passage for passage in turn.retrieved}
            for citation in turn.decision.citations:
                if citation in by_id:
                    cited_so_far.setdefault(citation, by_id[citation])

            if turn.decision.type is DecisionType.CONCLUDE:
                return AgentTranscript(turns=tuple(turns), final_decision=turn.decision)

            assert turn.decision.question_text is not None  # ASK always carries one
            history.append(Message(role="assistant", content=turn.decision.question_text))
            history.append(Message(role="user", content=answer_provider(turn.decision)))

        raise MaxTurnsExceeded(
            f"no CONCLUDE decision within {self.max_turns} turn(s); this is a budget "
            "running out, not a triage outcome — see MaxTurnsExceeded"
        )


class ScriptedReasoningClient:
    """A reasoning client with no model, for tests. Deterministic, no network.

    Plays the same role as ``herhealth_data.retrieval.embed.HashingEmbedder``:
    real enough to exercise :class:`TriageAgent`'s loop, control flow and
    turn-cap behaviour, and emphatically not a stand-in for whether the real
    model decides *well*.
    """

    def __init__(self, decisions: Sequence[TriageDecision]) -> None:
        self._decisions = list(decisions)
        self._calls = 0

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        if self._calls >= len(self._decisions):
            raise IndexError("ScriptedReasoningClient ran out of scripted decisions")
        decision = self._decisions[self._calls]
        self._calls += 1
        return decision
