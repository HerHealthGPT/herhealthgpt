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
    "render_red_flags",
]

#: The canonical system prompt. Owns the one framing rule that matters most:
#: the model may say what she described MATCHES a cited pattern, and may
#: name which authored conditions match — but must never say she HAS a
#: condition, and must never name one at all when a red flag is the reason
#: (TriageDecision.matching_conditions enforces that second half in code,
#: not just here — see decision.py). "Never diagnose" is CLAUDE.md's binding
#: rule; this is what enforcing it in the prompt actually looks like, in
#: words a model is asked to follow rather than code that can check it.
#: `bootstrap_dataset.py` imports this rather than defining its own, so the
#: bootstrap data and the served prompt never drift apart.
DEFAULT_SYSTEM_PROMPT = (
    "You are an AI triage assistant for reproductive-health questions, not a "
    "clinician, and you must never diagnose — never tell her she \"has\" a "
    "condition. When you conclude for a reason OTHER than a red-flag rule, "
    "you may name which of our authored conditions her answers match, always "
    "phrased as a possibility grounded in evidence, never as a conclusion "
    "about what is wrong with her — for example: \"Based on your answers, "
    "this may match patterns our sources associate with PCOS or "
    "perimenopause.\" Name only a handful of the closest matches (at most "
    "five, and usually fewer) — a long list of everything not yet ruled out "
    "is not useful guidance. Never name a specific disease when a red-flag warning "
    "sign is the reason for concluding — red flags exist to escalate on a "
    "symptom pattern without asserting what it is. Every citation, whether "
    "for a matched condition or an urgency level, is tied to a cited source. "
    "Ask one clarifying question at a time, or give urgency guidance — "
    "exactly one of SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, or "
    "EMERGENCY. Remind her plainly, in your own words, that you are an AI "
    "tool, not a clinician, and that this is based on her answers and the "
    "cited evidence, not a diagnosis. End every reply, question or final "
    "answer alike, with: \"Urgency guidance only, from cited sources. Not a "
    "diagnosis.\" Under-triage is the dominant failure mode: when in doubt, "
    "prefer sending her to care sooner rather than later."
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


def render_red_flags(red_flags: Sequence[RedFlagRule]) -> str:
    """Every red flag, verbatim, as the block injected into every turn.

    Not retrieved — see docs/adr/0011-controller-free-triage.md, "the flow,
    end to end": retrieval is approximate, and a rule that fires because a
    sentence scored 0.71 cosine is not what "red flag" meant when it was
    code. Rendered fresh per call; callers making many turns from one
    :class:`KnowledgeBase` should cache the result themselves.
    """
    lines = ["Known warning signs — check every one of these against what she has said:"]
    for rule in red_flags:
        lines.append(f'- {rule.label} ({rule.action.value}): "{rule.source_quote}"')
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

    def run_turn(self, history: Sequence[Message], *, query: str, k: int = 8) -> AgentTurn:
        """One retrieve-then-reason step. Does not mutate ``history``."""
        hits = self.retrieval.search(query, k=k)
        system = f"{self.system_prompt}\n\n{render_red_flags(self.base.red_flags)}"
        decision = self.reasoning.decide(system_prompt=system, history=history, context=hits)
        return AgentTurn(history_before=tuple(history), retrieved=tuple(hits), decision=decision)

    def run_consultation(
        self, opening_message: str, answer_provider: Callable[[TriageDecision], str]
    ) -> AgentTranscript:
        """Loop until CONCLUDE or ``max_turns``.

        ``answer_provider`` mirrors ``dialogue.AnswerProvider``'s role — it is
        how a test or a script supplies what the user says next, given the
        question the model just asked. The retrieval query each turn is the
        most recent message; concatenating fuller history into the query is a
        tuning question, not a correctness one, and is left open on purpose.
        """
        history: list[Message] = [Message(role="user", content=opening_message)]
        turns: list[AgentTurn] = []

        for _ in range(self.max_turns):
            turn = self.run_turn(history, query=history[-1].content)
            turns.append(turn)

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
