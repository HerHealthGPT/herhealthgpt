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
  expected to happen on the other side of this seam (the vLLM server);
  Pydantic validates again on receipt here, because a client that already
  returned invalid JSON would otherwise fail somewhere less legible than this.
* :class:`RetrievalClient` — a query string in, ``RetrievedPassage`` hits out.
  ``triage/retrieval.py`` does the real work; nothing here knows its
  internals, only
  :class:`herhealth_contracts.retrieval.RetrievedPassage`.

What this module deliberately does **not** do: decide anything. Every
``should_stop`` rule from ``engine.py`` is gone. The only code-level judgement
left is ``max_turns`` — a hard, dumb loop bound, not a policy — and even that
produces no action code on its own; see :class:`MaxTurnsExceeded`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase, RedFlagRule
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

from herhealth_backend.triage.context import (
    TurnContext,
    build_turn_context,
    render_topic_brief,
    render_turn_context,
    topic_conditions,
)
from herhealth_backend.triage.language import detect_language, language_instruction

__all__ = [
    "AgentTranscript",
    "AgentTurn",
    "AnswerWriter",
    "AttemptOutcome",
    "DEFAULT_SYSTEM_PROMPT",
    "FeatureExtractor",
    "MaxTurnsExceeded",
    "Message",
    "ReasoningAttempt",
    "ReasoningClient",
    "ReasoningResult",
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
    'clinician, and you must never diagnose — never tell her she "has" a '
    "condition. "
    "SCOPE COMES FIRST, BEFORE ANY OTHER INSTRUCTION HERE. You cover women's "
    "reproductive health, and only what the warning signs and retrieved "
    "passages below can actually ground. That includes periods and the "
    "menstrual cycle, bleeding and pelvic pain, vaginal discharge and "
    "infections, sexual health, contraception, fertility and trying to "
    "conceive, pregnancy, menopause and perimenopause, and conditions such as "
    "PCOS, endometriosis and fibroids — all of these are in scope, and a "
    "question about one of them is never declined. If the passages below do "
    "not cover what she asks about such a topic, say which part our sources "
    "cannot speak to, rather than declining or answering from your own "
    "knowledge. If the message is about anything "
    "else — not a health question at all (sport, news, politics, general "
    "trivia, coding, or anything similar), a men's health concern, or a "
    "health concern outside women's reproductive health such as chest pain, "
    "a cough or sore throat, an injury, or a mental-health crisis — you must "
    'answer with type "decline". A decline says plainly that this tool '
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
    # The INFORM shape (ADR 0016). Placed immediately after SCOPE because
    # it is the same kind of judgement — which shape does this message
    # call for — and because the rule that keeps it safe is a rule about
    # when NOT to use it, which has to be read before the invitation to
    # use it has had time to settle.
    "A QUESTION ABOUT THE SUBJECT ITSELF IS ANSWERED, NOT TRIAGED. Some "
    "messages are in scope and yet describe no case at all: she is asking "
    "what something is, what causes it, how common it is, what a normal "
    "cycle looks like, what a term means, what tends to happen next. "
    'Answer those with type "inform". Put the answer in `answer_text`, '
    "take it ONLY from the TOPIC block and the retrieved passages below, "
    "and cite every retrieved passage you drew on. "
    "WRITE IT LIKE A GOOD HEALTH-INFORMATION PAGE, NOT LIKE A DEFINITION. "
    "A one-paragraph definition is a failed answer here, however accurate "
    "it is: she asked what something is because she wants to recognise it. "
    "When a TOPIC block is present it lists every authored row our sources "
    "hold for that subject — work through ALL of them, and structure the "
    "answer in short labelled parts, separated by blank lines: what it is; "
    "the symptoms and signs our sources associate with it, as a list "
    "covering every row given, grouped sensibly rather than repeated one "
    "row at a time; anything our sources say points away from it; and last, "
    "when to get medical help. If the TOPIC block lists urgent warning "
    "signs, that final part is the most important thing on the page — give "
    "every one of them, in plain words, as "
    '"Get emergency care now if…" or "See someone today if…". If it '
    "says we hold no urgent warning sign for the subject, say instead that "
    "a clinician is the right place to take it, and do NOT invent urgency "
    "we have no source for. Never write the words warning sign, rule, "
    "action code or any identifier — describe the symptom itself. "
    "HOW TO LAY THE ANSWER OUT. The interface renders three things and "
    "nothing else: a SHORT line of its own ending in a colon becomes a "
    'section heading, a line starting with "- " becomes a bullet, and a '
    "blank line separates sections. Use exactly that. Keep a heading under "
    "about six words or it will not be recognised as one. Do NOT write "
    'markdown — "###", "**bold**" and the rest are stripped before she '
    "sees them, so they buy you nothing and cost you the heading. Prefer "
    "bullets to long sentences for symptoms and for when to seek care: she "
    "is scanning this to recognise something, not reading it through. "
    "`rationale` stays ONE short line on why this was a question to answer "
    "rather than a symptom to assess — it is not the answer, it must not "
    "repeat it, and it must not say this is not a diagnosis or that you are "
    "not a clinician: the interface already says so and the words are "
    "rejected. "
    "Do not repeat the same fact in three different wordings; our sources "
    "overlap, so say each thing once and move on. If neither block covers "
    "part of what she asked, say which part you cannot speak to rather than "
    "filling the gap from your own knowledge: an informational answer is "
    "only worth as much as the sources under it. An inform carries no "
    "urgency level and names no condition as hers. "
    "WHEN NOT TO INFORM — THE RULE THAT MATTERS MOST ON THIS PATH. If her "
    "message describes something SHE is experiencing, any symptom, now or "
    "recently, or asks what she should do about it, or whether she should "
    "be worried, then this is a consultation and not a lookup: ask or "
    "conclude, never inform. The same holds when she asks a general "
    "question and mentions her own symptoms in the same breath — record "
    "what she said in `observed`, then ask about it. It holds absolutely "
    "when a warning sign below applies: a warning sign is a reason to get "
    "her seen, never a reason to explain something to her. Never reach for "
    "an informational answer as a way of replying without committing to an "
    "urgency level. A woman who is handed an explanation when she needed "
    "to be told to be seen today has been under-triaged, which is the "
    "worst thing this tool can do to her. If you cannot tell which of the "
    "two she wants, triage: ask a clarifying question. An inform is only "
    "for a question that stands on its own, about the subject rather than "
    "about her. "
    "WHAT SHE HAS ALREADY TOLD US. Some consultations include a block headed "
    '"Known about her from her profile". When it gives her age band, that '
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
    'conclusion about what is wrong with her — for example: "Based on your '
    "answers, this may match patterns our sources associate with PCOS or "
    'perimenopause." Name only a handful of the closest matches (at most '
    "five, and usually fewer) — a long list of everything not yet ruled out "
    "is not useful guidance. When a red-flag warning sign is the reason for "
    "concluding, you may name matching conditions if the urgency is EMERGENCY "
    "or URGENT_SAME_DAY — at those two urgencies, do name them so she knows "
    "what patterns the warning sign relates to; at any lesser urgency a "
    "red-flag conclusion names no condition, because red flags escalate on a "
    "symptom pattern without asserting what it is. Every citation, whether for a matched "
    "condition or an urgency level, is tied to a cited source. Ask one "
    "clarifying question at a time, or give urgency guidance — exactly one "
    "of SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, or EMERGENCY — or "
    "answer an informational question that describes no case, or decline "
    "as scope requires. "
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
    # Added 2026-09-17. The validator has always rejected case-note framing
    # in rationale and question_text (clients._LEAKED_INTERNALS), but the
    # prompt never said so, and the model reached for "You mentioned…" /
    # "You have reported…" unprompted — 4 of the retries logged that day,
    # each costing a full extra model call of roughly 100 seconds. Same shape
    # as the 2026-09-11 fix above: a rule the checker knew and the model was
    # never told.
    "Write to her directly and never write about her. Do not open with "
    '"You mentioned", "You have reported", "You stated", "You '
    'indicated" or "You shared" — that is case-note language about a '
    "patient, and she is the person being spoken to. Refer to what she said "
    'in plain terms instead: "Pain this severe with a fever" rather than '
    '"You reported severe pain and a fever". '
    "Under-triage is the dominant failure mode: when in doubt, "
    "prefer sending her to care sooner rather than later — and when in "
    "doubt between asking and concluding, ask."
)


#: How many results each page-section search asks for. The first few are
#: often passages an earlier section already took.
PAGE_SEARCH_DEPTH = 24


@dataclass(frozen=True, slots=True)
class Message:
    """One line of conversation. ``role`` is ``"system"``, ``"user"`` or ``"assistant"``."""

    role: str
    content: str


@runtime_checkable
class RetrievalClient(Protocol):
    """Anything that can turn a query into ranked, cited passages."""

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]: ...


class AttemptOutcome(StrEnum):
    """How one call to one reasoning backend ended.

    A plain string enum enforced in the application layer, matching this
    repo's existing preference (``ActionCode`` and friends in
    ``herhealth_contracts``) over a database enum.
    """

    OK = "ok"
    #: ``httpx.ConnectError`` / ``httpx.TimeoutException`` — nothing answered.
    UNREACHABLE = "unreachable"
    #: HTTP 502/503/504 — something answered, and it was a sick gateway.
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    #: Answered, but never produced a schema-valid ``TriageDecision``.
    INVALID_DECISION = "invalid_decision"
    #: Produced a decision the client accepted and the **server** then refused
    #: — a closed-vocabulary violation, or a citation that was never retrieved.
    #: Recorded because the API layer retries the whole turn when this happens,
    #: and counting the discarded call as ``OK`` would overstate how often a
    #: backend answered usefully. See ``app/triage/routes.py``'s retry loop.
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ReasoningAttempt:
    """One call to one named backend, and how it ended.

    Recorded per call rather than per turn because a single turn can involve
    several: the answer step is written by a **different model**, and
    :meth:`TriageAgent._refuse_premature_conclusion` calls ``decide`` a second
    time. "Which model answered this turn" is therefore a sequence, not a
    value, and collapsing it to a value early is what made the question
    unanswerable before this existed.
    """

    client: str
    outcome: AttemptOutcome
    #: Why it failed, when it failed. ``None`` on :attr:`AttemptOutcome.OK`.
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    """A decision, and the record of what it took to get it.

    **Deliberately not a field on ``TriageDecision``.** That schema is
    ``extra="forbid"`` and is the structure vLLM guided decoding constrains,
    so every field in it is *generated by the model* — a model reporting its
    own identity could report it wrongly or invent one. Attribution is
    observed at the transport and travels beside the decision, never inside
    it.
    """

    decision: TriageDecision
    attempts: tuple[ReasoningAttempt, ...] = ()

    @property
    def served_by(self) -> str | None:
        """The backend this decision actually came from.

        The last attempt that succeeded, not the first that was tried — on a
        fallback those are different clients, which is the whole point.
        ``None`` only when a client reported no attempts at all.
        """
        for attempt in reversed(self.attempts):
            if attempt.outcome is AttemptOutcome.OK:
                return attempt.client
        return None


@runtime_checkable
class ReasoningClient(Protocol):
    """Anything that can turn a turn's inputs into a validated decision.

    ``name`` is part of the contract because attribution is: a client that
    cannot say what it is cannot be reported on.
    """

    @property
    def name(self) -> str: ...

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult: ...


@runtime_checkable
class FeatureExtractor(Protocol):
    """Maps her latest message onto the feature list, before the decision.

    A separate, focused step because the decision model, asked to do this
    and decide at once, recorded what she said in only 3 of 23 valid turns
    (measured 2026-10-12). Everything that makes a clarifying question
    possible is computed from that record, so with it empty the model had
    nothing to ask about and explained instead. See ADR 0018.

    Returns only real feature ids with listed values, and ``{}`` on any
    failure: extraction improves a turn and must never fail one.
    """

    def extract(
        self, history: Sequence[Message], *, pending_feature: str | None
    ) -> dict[str, str]: ...


@runtime_checkable
class AnswerWriter(Protocol):
    """Writes the text of an informational answer from the cited passages.

    Returns ``None`` when it has nothing usable; the decision model's own
    answer then stands. It never sees or sets an action code.
    """

    @property
    def name(self) -> str: ...

    def write(
        self, question: str, passages: Sequence[RetrievedPassage], base_answer: str
    ) -> str | None: ...


#: The rationale when code concludes on a fired warning sign. The urgency
#: itself is shown by the interface from the action code, in her language.
_RED_FLAG_RATIONALE = {
    "": "What you have described matches a warning sign in our sources that "
    "should be checked by a healthcare professional without waiting.",
    "Arabic": "ما وصفتِه يطابق علامة تحذيرية في مصادرنا يجب أن يفحصها أحد "
    "مقدّمي الرعاية الصحية دون انتظار.",
    "French": "Ce que vous décrivez correspond à un signe d'alerte de nos sources, "
    "qui doit être examiné par un professionnel de santé sans attendre.",
}


class SymptomTopics(Protocol):
    """Which features a question is about, whether or not she has them."""

    def mentioned(self, question: str) -> tuple[str, ...]: ...


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
    """One decision, what it was made from, and which backend produced it."""

    history_before: tuple[Message, ...]
    retrieved: tuple[RetrievedPassage, ...]
    decision: TriageDecision
    #: Every ``decide`` call this turn took, in order. Defaulted so the many
    #: tests that build an AgentTurn directly keep working; a turn that went
    #: through :meth:`TriageAgent.run_turn` always has at least one.
    attempts: tuple[ReasoningAttempt, ...] = ()
    #: On an ``inform``: the features its question is about, for the "when to
    #: get help" section (``context.care_guidance``). Empty otherwise.
    mentioned: tuple[str, ...] = ()

    @property
    def served_by(self) -> str | None:
        """The backend whose decision reached the caller. See
        :attr:`ReasoningResult.served_by`."""
        for attempt in reversed(self.attempts):
            if attempt.outcome is AttemptOutcome.OK:
                return attempt.client
        return None


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

    #: The extract step. ``None`` in tests and in demo mode.
    extractor: FeatureExtractor | None = None

    #: Refuse an ``inform`` once when she has described symptoms of her own or
    #: a warning sign is close. Off here and switched on by the deployment,
    #: for the same reason as ``min_answers``.
    refuse_inform_with_symptoms: bool = False

    #: The answer step, applied to an accepted ``inform``. ``None`` leaves the
    #: decision model's own answer in place.
    answer_writer: AnswerWriter | None = None

    #: The sections of a page-style informational answer: (heading, words
    #: added to her question to search for that section). Empty leaves the
    #: answer step writing from the cited passages alone. Used only when the
    #: writer can write a page (``write_page``).
    page_sections: tuple[tuple[str, str], ...] = ()
    #: Source passages kept per section.
    page_passages_per_section: int = 6

    #: Reads which symptoms an informational question is about, for the
    #: "when to get help" section. ``None`` leaves that to the extract step.
    symptom_topics: SymptomTopics | None = None

    #: Refuse, once, a question about the feature she was asked last turn and
    #: has now answered. Off here and switched on by the deployment.
    refuse_repeated_question: bool = False

    #: When her recorded answers satisfy a warning-sign rule and the model did
    #: not conclude at that rule's urgency, send the reply back once naming the
    #: rule; if it still does not escalate, conclude at the rule's urgency in
    #: code. Off here and switched on by the deployment. See
    #: :meth:`_enforce_red_flag`.
    enforce_red_flags: bool = False

    #: Send a decline back once: an unclear message that may be in scope
    #: should get a clarifying question, not a refusal. See
    #: :meth:`_refuse_unclear_decline`.
    refuse_unclear_decline: bool = False

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
        fallback_language: str | None = None,
        about_her_data: bool = False,
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
        given = dict(observed or {})
        extracted: dict[str, str] = {}
        if self.extractor is not None:
            # The last feature asked, whether or not something is already
            # recorded for it: the model may re-ask what an earlier misreading
            # recorded, and her reply must still be read as the answer to it.
            pending = list(asked)[-1] if asked else None
            extracted = self.extractor.extract(history, pending_feature=pending)
            given.update(extracted)
        turn_context = build_turn_context(self.base, given=given, asked=asked, prose=())
        system = f"{self.system_prompt}\n\n{render_turn_context(turn_context)}"

        # The topic channel, for an informational question (ADR 0016). The
        # block above is keyed on what she has ANSWERED, which is the right key
        # for triage and returns nothing at all for "what is PCOS?" — so the
        # model was left with whatever cosine similarity found, which for a
        # definition question is more definitions. Measured on the first real
        # informational turn: four retrieved passages, all four restating the
        # definition, a 433-character answer naming no symptom, while
        # evidence.csv held ten authored and quoted PCOS symptom rows.
        #
        # Injected on any turn where a topic is identifiable, not only when the
        # model goes on to inform — it cannot know which it will choose until
        # it has read the prompt. The block labels itself as topic material
        # that may not be used to conclude or to name a condition as hers,
        # because the same rows on a triage turn would otherwise pull the
        # differential toward whichever condition she happened to name.
        brief = render_topic_brief(
            self.base,
            topic_conditions(
                self.base,
                next((m.content for m in reversed(history) if m.role == "user"), ""),
                context,
            ),
        )
        if brief:
            system = f"{system}\n\n{brief}"
        if background:
            # Appended to the system prompt rather than injected into
            # ``history`` as a turn: she never said it in this consultation,
            # and inventing a user message would put words in her mouth in a
            # transcript that is meant to be replayable and auditable.
            system = f"{system}\n\n{background}"
        # Last, so it is the nearest thing to her message: reply in her language.
        # Her own words decide. The interface language is used only when none
        # of her messages has a word in it ("29"), so writing in English with
        # the interface in Arabic still gets an English reply.
        her_words = [m.content for m in history if m.role == "user"]
        language = detect_language(her_words)
        if language is None and not any(re.search(r"[^\W\d_]", text) for text in her_words):
            language = fallback_language
        if language is not None:
            system = f"{system}\n\n{language_instruction(language)}"
        result = self.reasoning.decide(system_prompt=system, history=history, context=context)
        # The inform gate first. Its re-prompt can come back as a conclusion,
        # and that conclusion has to meet the early-conclusion gate like any
        # other: in the other order it would be accepted unchallenged, on a
        # path the model takes often (it informed on 21 of 23 first turns).
        if about_her_data:
            # Covers what the two gates below would: she asked about her own
            # data, so neither a decline nor an explanation will do.
            result = self._require_triage_for_her_data(
                result, turn_context, system, history, context, language
            )
        else:
            result = self._refuse_unclear_decline(result, system, history, context)
            result = self._refuse_inform_with_symptoms(
                result, turn_context, system, history, context
            )
        result = self._refuse_premature_conclusion(result, turn_context, system, history, context)
        result = self._refuse_repeated_question(
            result, turn_context, asked, system, history, context, language
        )
        # Last, so no other gate can undo it.
        result = self._enforce_red_flag(result, turn_context, system, history, context, language)
        decision, attempts = result.decision, result.attempts

        # What the extract step read is carried on the decision, so the
        # caller's existing merge-and-persist of ``observed`` keeps it for the
        # next turn. The model's own reading wins where both name a feature.
        # Not on a decline: an off-scope message asserts nothing about her.
        if extracted and decision.type is not DecisionType.DECLINE:
            decision = decision.model_copy(update={"observed": {**extracted, **decision.observed}})

        if decision.type is DecisionType.INFORM and self.answer_writer is not None:
            decision, written, context = self._write_answer(
                decision, history, context, language=language
            )
            attempts = (*attempts, *written)

        mentioned: tuple[str, ...] = ()
        if decision.type is DecisionType.INFORM and self.symptom_topics is not None:
            question = next((m.content for m in reversed(history) if m.role == "user"), "")
            try:
                mentioned = self.symptom_topics.mentioned(question)
            except Exception:
                # A missing list only makes the section shorter; never a failed turn.
                mentioned = ()

        return AgentTurn(
            history_before=tuple(history),
            retrieved=context,
            decision=decision,
            attempts=attempts,
            mentioned=mentioned,
        )

    def _refuse_inform_with_symptoms(
        self,
        result: ReasoningResult,
        turn_context: TurnContext,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        """Send an explanation back when she has described symptoms of her own.

        An ``inform`` carries no urgency level. Measured 2026-10-12, the
        decision model informed on 21 of 23 valid first turns, including
        messages such as "now my period is all over the place" — which is
        under-triage by another route: she is handed an explanation when she
        needed a question or a level. The prompt already forbids it; this is
        the check that the prompt alone did not deliver.

        Same shape, and the same limit, as :meth:`_refuse_premature_conclusion`:
        it refuses once, names why, and picks nothing itself. If the model
        informs again, that stands.
        """
        if not self.refuse_inform_with_symptoms or result.decision.type is not DecisionType.INFORM:
            return result
        # Her age band comes from her profile, not from what she said today.
        described = sorted(f for f in turn_context.given if f != "age_band")
        near = turn_context.fired is not None or bool(turn_context.near_misses)
        if not described and not near:
            return result

        why = (
            # The answers may come from her imported cycle data rather than
            # from her words: measured 2026-10-19, "can you see my cycle data,
            # is it healthy?" was answered with a generic page after this
            # reason told the model she had described a symptom, which she
            # had not.
            "the question is about her own situation: what she has described or "
            f"what her imported cycle data records ({', '.join(described)})"
            if described
            else "a warning sign applies or is one answer away"
        )
        retry = (
            f'{system}\n\nYOUR PREVIOUS ANSWER WAS AN EXPLANATION (type "inform") AND WAS '
            f"REJECTED, because {why}. This is a consultation, not a lookup. Respond again "
            'with type "ask" (a real next_feature_id from the list above, and '
            'question_text) or type "conclude". Do not use type "inform".'
        )
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
        except Exception:
            # As with the conclusion gate: an improvement, not a guarantee.
            return result
        return ReasoningResult(
            decision=retried.decision,
            attempts=(*result.attempts, *retried.attempts),
        )

    def _require_triage_for_her_data(
        self,
        result: ReasoningResult,
        turn_context: TurnContext,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
        language: str | None,
    ) -> ReasoningResult:
        """When she asks about her imported cycle data, ask or conclude.

        Measured 2026-10-19: asked "is my cycle healthy? give me a breakdown"
        with her data in the prompt, the model first declined ("I cannot view
        attached files"), then, told it could see the data, answered with a
        general health page every time it was asked in English, even after
        the inform gate sent it back. A page carries no urgency level. The
        breakdown she asked for is written by code (``render_cycle_breakdown``)
        and shown above the reply, so the model's one job here is the triage.

        Sends anything else back once, then once more naming the top
        unanswered question on the menu. If the model still does not ask or
        conclude, code asks that question in its authored English wording; in
        another language the model's reply stands, as in the repeat gate.
        """
        triage = (DecisionType.ASK, DecisionType.CONCLUDE)
        if result.decision.type in triage:
            return result
        retry = (
            f"{system}\n\nYOUR PREVIOUS ANSWER WAS REJECTED. She asked about her own "
            "imported cycle data. A breakdown of it, written by code, is already shown to "
            'her above your reply, so do not restate it. Respond with type "ask" (a real '
            'next_feature_id from the list above, and question_text) or type "conclude". '
            'Do not use type "inform" or "decline".'
        )
        attempts = result.attempts
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
        except Exception:
            return result
        attempts = (*attempts, *retried.attempts)
        if retried.decision.type in triage:
            return ReasoningResult(decision=retried.decision, attempts=attempts)

        best = next(
            (
                item.feature
                for item in turn_context.askable
                if item.feature.id not in turn_context.given
            ),
            None,
        )
        if best is None:
            return ReasoningResult(decision=retried.decision, attempts=attempts)
        # Name the question, so the model can still word it in her language.
        named = (
            f"{retry}\n\nYOU DID NOT TRIAGE AGAIN. Ask about {best.id} ({best.label}) now: "
            f'type "ask", next_feature_id {best.id}, and question_text in her language.'
        )
        try:
            third = self.reasoning.decide(system_prompt=named, history=history, context=context)
            attempts = (*attempts, *third.attempts)
            if third.decision.type in triage:
                return ReasoningResult(decision=third.decision, attempts=attempts)
        except Exception:
            pass
        wording = best.probe.get("en") if language is None else None
        if not wording:
            return ReasoningResult(decision=retried.decision, attempts=attempts)
        decision = TriageDecision(
            type=DecisionType.ASK,
            next_feature_id=best.id,
            question_text=wording,
            rationale="One more detail would change the advice.",
        )
        return ReasoningResult(
            decision=decision,
            attempts=(
                *attempts,
                ReasoningAttempt(
                    client="her-data-gate",
                    outcome=AttemptOutcome.OK,
                    detail=f"asked {best.id} in code after the model would not triage",
                ),
            ),
        )

    def _refuse_unclear_decline(
        self,
        result: ReasoningResult,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        """Send a decline back once, so an unclear message is clarified.

        Measured on the benchmark's vague rewordings (ADR 0018), 22 of 90 were
        declined as out of scope, e.g. "What does having this actually mean
        for me?": unclear, not off-topic. A clarifying question must name a
        feature, so there is no plain "what do you mean?", and the model
        declined instead. It is told to ask with the closest feature, or to
        answer if the topic is clear, and to decline only a message clearly
        about something else. A second decline stands, but if it is a decline
        for being unclear, its words must ask her what she means instead of
        saying the topic is not covered.
        """
        if not self.refuse_unclear_decline or result.decision.type is not DecisionType.DECLINE:
            return result
        retry = (
            f"{system}\n\nYOUR PREVIOUS ANSWER DECLINED AND WAS REJECTED. Decline only a "
            "message that is clearly about something other than women's reproductive "
            "health. A message that is unclear but could be about periods, pain, "
            "bleeding, discharge, fertility, pregnancy, menopause or a related "
            "condition is in scope: ask ONE clarifying question with the feature from "
            "the list that best narrows down what she means, or answer it as an "
            "informational question if its topic is clear. If you still decline "
            "because you cannot tell what she means, your rationale must ask her, in "
            "one or two plain sentences, to say a little more about what she means "
            '(for example what she is noticing, or what "this" refers to), and must '
            "NOT say that this tool only covers reproductive health. Use that sentence "
            "only for a message clearly about something else."
        )
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
        except Exception:
            return result
        return ReasoningResult(
            decision=retried.decision,
            attempts=(*result.attempts, *retried.attempts),
        )

    def _enforce_red_flag(
        self,
        result: ReasoningResult,
        turn_context: TurnContext,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
        language: str | None,
    ) -> ReasoningResult:
        """Escalate when a warning sign has fired, whatever the model chose.

        **This partly reverses ADR 0011, deliberately.** Measured on
        2026-10-19 (``make eval-red-flags``, ADR 0018), the model escalated on
        the turn a warning sign was present in 6 of 17 rules with her answers
        recorded, mostly asking another question instead. CLAUDE.md promises
        that a matched rule escalates "immediately without asking anything
        further", and that a missed escalation is worse than a false alarm.

        Which rule has fired is computed by code from her recorded answers
        (``TurnContext.fired``, the most severe one), as ``should_stop`` rule
        1 did. The model is first sent back once with the rule named; if it
        still does not conclude at that urgency or higher, code concludes at
        the rule's urgency with the rule as its ground. A conclusion at a
        higher urgency than the rule is left alone.
        """
        fired = turn_context.fired
        if not self.enforce_red_flags or fired is None:
            return result
        severity = {action.code: action.severity for action in self.base.actions.actions}
        needed = severity[fired.rule.action]

        def escalated(decision: TriageDecision) -> bool:
            return (
                decision.type is DecisionType.CONCLUDE
                and decision.action_code is not None
                and severity[decision.action_code] >= needed
            )

        if escalated(result.decision):
            return result
        retry = (
            f"{system}\n\nYOUR PREVIOUS ANSWER DID NOT ESCALATE AND WAS REJECTED. Her "
            f"answers satisfy the warning-sign rule {fired.rule.id} "
            f'({fired.rule.action.value}). Respond again with type "conclude", '
            f"action_code {fired.rule.action.value} or higher, red_flag_id "
            f"{fired.rule.id}, and a rationale telling her plainly how soon to be "
            "seen. Ask nothing further."
        )
        attempts = result.attempts
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
            attempts = (*attempts, *retried.attempts)
            if escalated(retried.decision):
                return ReasoningResult(decision=retried.decision, attempts=attempts)
        except Exception:
            pass
        decision = TriageDecision(
            type=DecisionType.CONCLUDE,
            action_code=fired.rule.action,
            red_flag_id=fired.rule.id,
            rationale=_RED_FLAG_RATIONALE.get(language or "", _RED_FLAG_RATIONALE[""]),
            observed=dict(result.decision.observed),
        )
        return ReasoningResult(
            decision=decision,
            attempts=(
                *attempts,
                ReasoningAttempt(
                    client="red-flag-gate",
                    outcome=AttemptOutcome.OK,
                    detail=f"concluded {fired.rule.action.value} on {fired.rule.id} in code",
                ),
            ),
        )

    def _refuse_repeated_question(
        self,
        result: ReasoningResult,
        turn_context: TurnContext,
        asked: Sequence[str],
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
        language: str | None = None,
    ) -> ReasoningResult:
        """Send back a question she answered in the message just read.

        Measured 2026-10-12: three of ten scripted consultations were still
        asking after eight turns, one of them the same question four times.
        The answer was recorded each time; the model asked again anyway.

        A repeat is a question she has already answered, or the question
        asked on the turn just before, answered or not. Measured 2026-10-19:
        when her reply was not recorded, the model put the same question
        straight back, twice in one consultation. A question she could not
        answer may still be put again later, just not back to back.
        """
        given = turn_context.given
        last = list(asked)[-1] if asked else None

        def repeats(decision: TriageDecision) -> bool:
            # Any question she has already answered, not only the last one:
            # measured, a model refused once came straight back to it.
            return (
                decision.type is DecisionType.ASK
                and decision.next_feature_id is not None
                and (decision.next_feature_id in given or decision.next_feature_id == last)
            )

        if not self.refuse_repeated_question or not repeats(result.decision):
            return result
        feature = result.decision.next_feature_id
        if feature in given:
            reason = (
                "SHE HAS ALREADY ANSWERED IT. "
                f"Her answer about {feature} is recorded as {given.get(feature or '')!r}."
            )
        else:
            reason = (
                f"YOU ASKED ABOUT {feature} ON THE LAST TURN. Her reply did not settle it; "
                "asking the same thing again straight away will not either."
            )
        retry = (
            f"{system}\n\nYOUR PREVIOUS QUESTION WAS REJECTED: {reason} Do not ask about "
            "anything she has already answered, or the same thing twice in a row. Ask about "
            "a different feature from the list above, or conclude if you have enough."
        )
        attempts = result.attempts
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
        except Exception:
            return result
        attempts = (*attempts, *retried.attempts)
        if not repeats(retried.decision):
            return ReasoningResult(decision=retried.decision, attempts=attempts)

        # Refused once and still repeating: name the question to ask instead,
        # the best unanswered one on the ranked menu.
        best = next(
            (
                item.feature
                for item in turn_context.askable
                if item.feature.id not in given and item.feature.id != last
            ),
            None,
        )
        if best is None:
            return ReasoningResult(decision=retried.decision, attempts=attempts)
        retry = (
            f"{retry}\n\nYOU REPEATED THE QUESTION AGAIN. Ask about {best.id} "
            f"({best.label}) now, with next_feature_id {best.id}."
        )
        try:
            third = self.reasoning.decide(system_prompt=retry, history=history, context=context)
            attempts = (*attempts, *third.attempts)
            if not repeats(third.decision):
                return ReasoningResult(decision=third.decision, attempts=attempts)
        except Exception:
            pass
        # Still repeating. Ask the menu's question in its authored wording,
        # which exists in English only (CLAUDE.md, "Language scope"); in
        # another language the model's reply stands rather than switch
        # language mid-conversation.
        wording = best.probe.get("en") if language is None else None
        if not wording:
            return ReasoningResult(decision=retried.decision, attempts=attempts)
        decision = TriageDecision(
            type=DecisionType.ASK,
            next_feature_id=best.id,
            question_text=wording,
            rationale="One more detail would change the advice.",
            observed=dict(retried.decision.observed),
        )
        return ReasoningResult(
            decision=decision,
            attempts=(
                *attempts,
                ReasoningAttempt(
                    client="repeat-gate",
                    outcome=AttemptOutcome.OK,
                    detail=f"asked {best.id} in code after repeated questions",
                ),
            ),
        )

    def _write_answer(
        self,
        decision: TriageDecision,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
        *,
        language: str | None = None,
    ) -> tuple[TriageDecision, tuple[ReasoningAttempt, ...], Sequence[RetrievedPassage]]:
        """Let the answer writer word an accepted ``inform``.

        With ``page_sections`` set it writes a page: one search per section,
        the passages found handed to the writer under their headings beside
        the decision model's own answer as a draft, and every passage it was
        shown added to the citations and to the turn's context. Without
        ``page_sections`` it is shown only the passages the decision cited.
        Either way its text replaces ``answer_text`` alone, and if it returns
        nothing usable the decision model's own answer stands and the turn is
        unaffected.
        """
        assert self.answer_writer is not None
        assert decision.answer_text is not None  # INFORM always carries one
        writer = self.answer_writer
        question = next((m.content for m in reversed(history) if m.role == "user"), "")
        attempts: list[ReasoningAttempt] = []

        write_page = getattr(writer, "write_page", None)
        if self.page_sections and callable(write_page):
            try:
                sections = self._page_passages(question, context)
                page = write_page(
                    question,
                    sections,
                    decision.answer_text,
                    language=language,
                )
            except Exception:
                # As below: a better answer is never worth a failed turn.
                sections, page = [], None
            if page is not None:
                text, written_by = page
                if written_by != writer.name:
                    attempts.append(
                        ReasoningAttempt(
                            client=writer.name,
                            outcome=AttemptOutcome.REJECTED,
                            detail="no usable page; another model wrote it",
                        )
                    )
                attempts.append(ReasoningAttempt(client=written_by, outcome=AttemptOutcome.OK))
                known = {passage.id for passage in context}
                shown = [passage for _, found in sections for passage in found]
                extra = [passage for passage in shown if passage.id not in known]
                citations = tuple(
                    dict.fromkeys((*decision.citations, *(passage.id for passage in shown)))
                )
                return (
                    decision.model_copy(update={"answer_text": text, "citations": citations}),
                    tuple(attempts),
                    (*context, *extra),
                )

            # No page: the decision model's own answer stands. It is already
            # written from the TOPIC block and the passages in the layout the
            # prompt asks for, and the short rewrite below would cut it down
            # to the cited passages alone, which is how a PCOS answer once
            # lost its whole symptom list.
            attempts.append(
                ReasoningAttempt(
                    client=writer.name,
                    outcome=AttemptOutcome.REJECTED,
                    detail="no usable page; the decision model's own answer was kept",
                )
            )
            return decision, tuple(attempts), context

        cited = [passage for passage in context if passage.id in decision.citations]
        try:
            text = writer.write(question, cited, decision.answer_text)
        except Exception:
            # Wording an answer is an improvement, never a requirement: no
            # failure here may cost her a turn that already has a valid reply.
            text = None
        if not text:
            attempts.append(
                ReasoningAttempt(
                    client=writer.name,
                    outcome=AttemptOutcome.REJECTED,
                    detail="no usable answer; the decision model's own answer was kept",
                )
            )
            return decision, tuple(attempts), context
        attempts.append(ReasoningAttempt(client=writer.name, outcome=AttemptOutcome.OK))
        return decision.model_copy(update={"answer_text": text}), tuple(attempts), context

    def _page_passages(
        self, question: str, context: Sequence[RetrievedPassage] = ()
    ) -> list[tuple[str, list[RetrievedPassage]]]:
        """One search per page section. Source passages only, each used once.

        The search names the subject, not her question. Searching with
        "What is endometriosis? symptoms and signs" returned the same five
        definition sentences for every section, because the question
        outweighs the two words added to it; "symptoms and signs of
        Endometriosis" does not. When no authored condition is recognised in
        her words, her question is all there is to search with.
        """
        topics = topic_conditions(self.base, question, context, limit=1)
        labels = {condition.id: condition.label for condition in self.base.conditions}
        subject = labels.get(topics[0]) if topics else None
        seen: set[str] = set()
        sections: list[tuple[str, list[RetrievedPassage]]] = []
        for index, (title, words) in enumerate(self.page_sections):
            if index == 0 or subject is None:
                query = f"{question} {words}"
            else:
                query = f"{words} of {subject}"
            found = [
                passage
                for passage in self.retrieval.search(query, k=PAGE_SEARCH_DEPTH)
                if passage.passage_type is PassageType.SOURCE_PASSAGE and passage.id not in seen
            ][: self.page_passages_per_section]
            seen.update(passage.id for passage in found)
            sections.append((title, found))
        return sections

    def _refuse_premature_conclusion(
        self,
        result: ReasoningResult,
        turn_context: TurnContext,
        system: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
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
        decision = result.decision
        if decision.type is not DecisionType.CONCLUDE or self.min_answers <= 0:
            return result

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
            return result

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
            f'REJECTED. {why}\nRespond again with type "ask", a real '
            "next_feature_id from the list above, and question_text."
        )
        try:
            retried = self.reasoning.decide(system_prompt=retry, history=history, context=context)
        except Exception:
            # The gate is an improvement, not a guarantee. A client that
            # cannot answer the re-prompt leaves the original conclusion
            # standing rather than failing her turn outright.
            return result
        # Both calls are kept, in order: a turn where the adapter concluded
        # early and the base model answered the re-prompt is two different
        # models in one turn, and reporting only the second would hide that.
        return ReasoningResult(
            decision=retried.decision,
            attempts=(*result.attempts, *retried.attempts),
        )

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

            if turn.decision.type is DecisionType.INFORM:
                # Answered, but nothing was asked and nothing concluded, so
                # the consultation is still open and no feature joins `asked`.
                # The answer goes into the history because the next turn has
                # to see what she was already told; `answer_provider` is then
                # asked what she says next, exactly as after a question.
                assert turn.decision.answer_text is not None  # INFORM always carries one
                history.append(Message(role="assistant", content=turn.decision.answer_text))
                history.append(Message(role="user", content=answer_provider(turn.decision)))
                continue

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

    def __init__(self, decisions: Sequence[TriageDecision], *, name: str = "scripted") -> None:
        self._decisions = list(decisions)
        self._calls = 0
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        if self._calls >= len(self._decisions):
            raise IndexError("ScriptedReasoningClient ran out of scripted decisions")
        decision = self._decisions[self._calls]
        self._calls += 1
        return ReasoningResult(
            decision=decision,
            attempts=(ReasoningAttempt(client=self._name, outcome=AttemptOutcome.OK),),
        )
