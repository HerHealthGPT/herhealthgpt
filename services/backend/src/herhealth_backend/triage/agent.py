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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase, RedFlagRule
from herhealth_contracts.retrieval import RetrievedPassage

from herhealth_backend.triage.context import (
    TurnContext,
    build_turn_context,
    render_turn_context,
)

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
    "render_known_background",
    "render_red_flags",
    "render_feature_vocabulary",
]

#: The canonical system prompt. Owns four rules code cannot check on its own.
#: First, scope: an off-scope message must be DECLINED, never answered and
#: never assigned an urgency. The schema (see decision.py) can guarantee a
#: decline carries no action code and no citation, but only this text can
#: decide that "who won world cup 2026" is one — hence the instruction
#: leading the prompt rather than trailing it. Second, medicines: this tool
#: never tells her to take, start, stop or dose a drug, even when the rest
#: of the message is in-scope period pain or PCOS — a named tablet is still
#: a prescribing question, and prescribing is diagnosing by another name.
#: Third, stored profile background (ADR 0015): a known age band is an
#: answer already given and must not be asked for again, while a health
#: note is unverified background that may never fire a red flag on its own.
#: `render_known_background` supplies the values per turn; the standing rule
#: about how to treat them belongs here, so it holds even on a turn where
#: no block is injected.
#: Fourth, and the framing rule that matters most:
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
    "WHAT SHE HAS ALREADY TOLD US. Some consultations include a block headed "
    "\"Known about her from her profile\". When it gives her age band, that "
    "is a real answer she has already given to the age_band feature: use it "
    "in your reasoning, and do NOT spend a turn asking her age, how old she "
    "is, or which age group she is in — asking again wastes one of the few "
    "questions you get and reads as though you had not listened. Age is not "
    "a detail: it separates perimenopause from PCOS after 45, and it is what "
    "makes bleeding after menopause interpretable at all, so weigh it "
    "wherever it bears on a condition you are considering. When that block "
    "also carries a health note she wrote, treat it as unverified background "
    "she may have typed long ago — never as a symptom she is reporting now, "
    "never as enough on its own to conclude, and never as grounds for a "
    "warning sign. If no such block appears you know neither her age nor any "
    "background, and age is then a reasonable thing to ask about. "
    "MEDICINES ARE NEVER YOURS TO ADVISE. If she asks whether to take, start, "
    "stop, buy, or dose a medicine — named or not, branded or generic, "
    "prescription or from a pharmacy, including painkillers such as ibuprofen "
    "or paracetamol, the contraceptive pill, metformin, antibiotics, or "
    "anything a pharmacist might sell — do not tell her to take it, do not "
    "tell her not to take it as if you had reviewed her, and do not suggest "
    "a dose or an alternative drug. Say plainly that deciding on a medicine is "
    "not something this tool does, and that a doctor or pharmacist must decide "
    # Deliberately NOT "say you cannot diagnose": that phrasing matches
    # `clients._LEAKED_INTERNALS`, so the prompt would be commanding a reply
    # the validator then rejects — the same contradiction fixed above, on the
    # medicine path instead of the in-scope one.
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
    # REMOVED 2026-09-11. These two sentences commanded the model to write
    # exactly the strings `clients._LEAKED_INTERNALS` rejects — "urgency
    # guidance", "cited sources", "not a diagnosis", "not a clinician". A
    # model that obeyed the prompt was guaranteed to fail validation, retry,
    # obey again, and fail again, burning three slow generations before the
    # turn timed out. Observed live: every in-scope turn returning 504.
    #
    # The disclaimer is not lost. The interface renders it on every reply
    # ("HerHealthGPT can make mistakes. It gives urgency guidance, not a
    # diagnosis."), which is strictly better: it is always present, always
    # worded correctly, and localisable, rather than depending on a model
    # reproducing a fixed string. `_JSON_SHAPE_INSTRUCTION` already told the
    # model not to restate any of this; the system prompt simply had not
    # caught up, and the two halves contradicted each other.
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


def render_known_background(*, age_band: str | None, health_note: str | None) -> str | None:
    """What she told us about herself once, framed so it cannot be mistaken
    for what she is reporting today. ``None`` when there is nothing to say.

    Two things are load-bearing about the wording, both from ADR 0015:

    * The age band is presented as an **answer she already gave** to the
      ``age_band`` feature, so the model stops spending a turn on it. It is
      not written into the transcript as a user message, because she did not
      say it in this consultation and a fabricated turn would be a lie in an
      auditable record.
    * The note is presented as **unverified background, explicitly not a
      symptom report and explicitly not able to fire a red flag**. A woman
      who typed "I have PCOS" in Settings last month has not told us
      anything about today, and a red flag inferred from stored free text
      would escalate on something nobody checked.
    """
    lines: list[str] = []
    if age_band is not None:
        lines.append(
            f"- Her age band is {age_band} (the age_band feature is already "
            "answered — do not ask her age again)."
        )
    if health_note:
        lines.append(
            "- She has previously written this background about herself, in "
            f'her own words: "{health_note}"'
        )
    if not lines:
        return None
    return "\n".join(
        [
            "Known about her from her profile, not from this conversation:",
            *lines,
            "Treat the above as background only. It is unverified, she may "
            "have written it long ago, and it is NOT a symptom she is "
            "reporting now — never conclude from it alone, and never let it "
            "fire a warning sign on its own. Still ask about what is "
            "happening today.",
        ]
    )


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

    #: How many of her answers must be recorded before a conclusion is
    #: accepted without challenge. **Zero here, and switched on by the
    #: deployment** (``app/main.py``): refusing a conclusion is a policy about
    #: how much this product wants to ask before answering, not a property of
    #: the loop, and a scripted test client has no second answer to give when
    #: challenged. See :meth:`_refuse_premature_conclusion` for why it cannot
    #: simply be left to the prompt.
    min_answers: int = 0

    def run_turn(
        self,
        history: Sequence[Message],
        *,
        query: str | None = None,
        k: int = 8,
        carried_context: Sequence[RetrievedPassage] = (),
        background: str | None = None,
        observed: Mapping[str, str] | None = None,
        asked: Sequence[str] = (),
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

        # The grounding block, built by joining the knowledge base against what
        # she has actually answered rather than by rendering all of it every
        # turn. Replaces `render_feature_vocabulary` (39 bare ids, no labels,
        # no value vocabularies) and `render_red_flags` (16 rules with their
        # `all_of` clauses stripped out, so a rule one answer away was
        # indistinguishable from one nothing had touched). Both of those
        # functions are kept — `bootstrap_dataset` still imports them, and the
        # comparison in docs is worth being able to reproduce — but nothing on
        # the serving path calls them any more.
        #
        # `prose=()` deliberately: the retrieved passages are still rendered by
        # the reasoning client (`clients._render_context`), which is also what
        # feeds `_available_ids_hint` on a retry. Rendering them here as well
        # would put the same text in the prompt twice.
        turn_context = build_turn_context(self.base, given=observed or {}, asked=asked, prose=())
        system = f"{self.system_prompt}\n\n{render_turn_context(turn_context)}"
        if background:
            # Appended to the system prompt rather than injected into
            # ``history`` as a turn: she never said it in this consultation,
            # and inventing a user message would put words in her mouth in a
            # transcript that is meant to be replayable and auditable.
            system = f"{system}\n\n{background}"
        decision = self.reasoning.decide(system_prompt=system, history=history, context=context)
        decision = self._refuse_premature_conclusion(
            decision, turn_context, system, history, context
        )
        return AgentTurn(history_before=tuple(history), retrieved=context, decision=decision)

    def _refuse_premature_conclusion(
        self,
        decision: TriageDecision,
        turn_context: TurnContext,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> TriageDecision:
        """Send a conclusion back when something material is still unanswered.

        **This is an abstention gate, and it is the one place this module comes
        close to deciding.** It is worth being precise about what it does and
        does not do. It never picks an action code, never picks a question, and
        never converts a CONCLUDE into an ASK itself. It refuses a conclusion
        and asks the model to think again, naming what is outstanding. The
        model still chooses everything.

        **Why it has to exist.** ADR 0011 moved ask-vs-conclude to the model,
        and the system prompt asks for "at least two or three clarifying
        questions". Measured 2026-09-11 against the fine-tuned adapter: it
        concluded on the opening message in five of six probes, and in a live
        consultation concluded after a single question whose answer raised
        nothing. Instruction alone does not produce question-asking — MediQ
        (arXiv:2406.00922) reports that prompting a model to ask questions
        *degrades* performance, and that an explicit abstention step is what
        recovers it, worth 22.3% diagnostic accuracy there. The adapter's
        training data contains no example where the correct reply is a
        question (CLAUDE.md), so there is nothing in it to appeal to.

        Two conditions, and only two:

        * **A more severe warning sign is one answer away.** Concluding at a
          lower urgency while an EMERGENCY rule needs one more answer is the
          under-triage this project exists to prevent, and it is what
          ``should_stop`` rule 1 guaranteed by code before ADR 0011 retired it.
        * **Almost nothing has been asked.** Fewer than ``min_answers``
          features recorded while a question with real discriminating value is
          on the menu. This is a judgement, it is deliberately low, and it is
          the condition to relax first if consultations start feeling long.

        Both are refusals to accept, not instructions to obey. If the model
        concludes again after being told, that conclusion stands: the gate
        gives way rather than looping, because a model that insists is more
        likely to be right than a rule that cannot see her words.
        """
        if decision.type is not DecisionType.CONCLUDE or self.min_answers <= 0:
            return decision

        met = turn_context.fired.severity if turn_context.fired else -1
        escalation = next((s for s in turn_context.near_misses if s.severity > met), None)

        # A FIRED RULE IS NEVER CHALLENGED FOR THINNESS. This is the condition
        # that matters most here, and the first version of this method got it
        # wrong: a woman with no stored date of birth, reporting severe pelvic
        # pain and faintness, has two answers recorded when
        # `pelvic_pain_with_faintness` fires — and the thinness rule would have
        # sent that EMERGENCY back to ask a third question first. Delaying an
        # escalation to gather more history is exactly the failure this project
        # exists to prevent, and the rule was doing it for the sake of a count.
        #
        # A fired rule needs no corroboration from question volume: it is the
        # source's own escalation language, matched clause by clause against
        # what she actually said. The only thing that may still send an
        # escalation back is a STRICTLY MORE SEVERE rule one answer away —
        # which asks her to escalate further, never to wait.
        thin = (
            turn_context.fired is None
            and len(turn_context.given) < self.min_answers
            and bool(turn_context.askable)
        )
        if escalation is None and not thin:
            return decision

        if escalation is not None:
            clause = escalation.outstanding[0]
            why = (
                f"A more serious warning sign is one answer away: "
                f"{escalation.rule.id} ({escalation.rule.action.value}) needs "
                f"{clause.feature_id}. You must ask about {clause.feature_id} "
                "before concluding at a lower urgency."
            )
        else:
            best = turn_context.askable[0]
            why = (
                f"She has answered only {len(turn_context.given)} thing(s), and "
                f"{best.feature.id} is still unanswered and would change the "
                "picture. Ask one clarifying question instead of concluding."
            )

        retry = (
            f"{system}\n\nYOUR PREVIOUS ANSWER CONCLUDED TOO EARLY AND WAS "
            f"REJECTED. {why}\nRespond again with type \"ask\", a real "
            "next_feature_id from the list above, and question_text."
        )
        try:
            return self.reasoning.decide(
                system_prompt=retry, history=history, context=context
            )
        except Exception:
            # The gate is an improvement, not a guarantee. A client that
            # cannot answer the re-prompt leaves the original conclusion
            # standing rather than failing her turn outright.
            return decision

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
        # The case vector, accumulated across turns. Each decision reports what
        # it understood from the message it just read (`observed`), and those
        # readings are merged forward — a later turn may correct an earlier
        # value, which is why this is an update rather than a setdefault.
        observed: dict[str, str] = {}
        asked: list[str] = []

        for _ in range(self.max_turns):
            turn = self.run_turn(
                history,
                carried_context=tuple(cited_so_far.values()),
                observed=observed,
                asked=asked,
            )
            turns.append(turn)
            observed.update(turn.decision.observed)
            by_id = {passage.id: passage for passage in turn.retrieved}
            for citation in turn.decision.citations:
                if citation in by_id:
                    cited_so_far.setdefault(citation, by_id[citation])

            if turn.decision.type is DecisionType.CONCLUDE:
                return AgentTranscript(turns=tuple(turns), final_decision=turn.decision)

            assert turn.decision.question_text is not None  # ASK always carries one
            # Recorded as asked the moment the question goes out, not when the
            # answer comes back. A feature she was asked about and could not
            # answer must still count as asked, or the escalation screen would
            # keep offering the same probe every turn.
            if turn.decision.next_feature_id is not None:
                asked.append(turn.decision.next_feature_id)
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
