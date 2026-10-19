"""What the reasoning model is told, and how its reply is checked.

The prompt's output-shape instruction, the rendering of retrieved passages,
the parsing of a reply into a ``TriageDecision``, the one repair applied to
it, and the checks on user-facing wording. No transport lives here: the
model is called through LangChain in ``triage/chain.py`` (ADR 0018), which
imports these and adds nothing to what the model is asked.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence

from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.retrieval import RetrievedPassage
from pydantic import ValidationError

from herhealth_backend.triage.agent import (
    Message,
)

__all__ = [
    "DecisionValidator",
    "WordingRejected",
    "extract_json_object",
    "parse_decision_text",
    "retry_feedback",
]

logger = logging.getLogger(__name__)

#: The closed-vocabulary check, bound to a ``KnowledgeBase``. Structural, not
#: an import of ``vocabulary``: keeping this a plain callable is what stops
#: ``clients`` depending on the module that owns the rule, so a client can
#: still be constructed with no knowledge base at all (every test does).
DecisionValidator = Callable[[TriageDecision, Sequence[RetrievedPassage]], None]

#: Qwen3.5 thinking blocks may appear in ``content`` when thinking mode is
#: left on — see docs/runbooks/dev-vllm-lora-endpoint.md.
_THINKING_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _render_context(context: Sequence[RetrievedPassage]) -> str:
    """Retrieved passages, rendered into the system prompt. Mirrors
    ``agent.render_red_flags``'s role for red flags: red flags are injected
    unconditionally, this is injected only when retrieval found something.

    Labelled ``passage_id=`` rather than a bare ``[hash]``, and evidence
    statements' own ``feature_id``/``condition_id`` are surfaced explicitly
    when present — both changes made after a live test
    (2026-09-01) returned a passage's hash where a real feature id
    belonged: ``next_feature_id="14ebb1e7a2e19149"``. A hex hash and a real
    feature id look similar enough in a wall of retrieved text that the
    model conflated the two namespaces; this makes the difference visible
    rather than relying on the instruction text alone to prevent it.
    """
    if not context:
        return "No retrieved passages matched this turn."
    lines = [
        "BACKGROUND PASSAGES, retrieved by similarity. These are for wording and "
        "context, and to cite — they are NOT authored evidence and carry no "
        "strength, so never take a condition id from one; the EVIDENCE HER "
        "ANSWERS KEY INTO block above is the authoritative set. passage_id is "
        "ONLY for `citations` — it is a content hash, never a feature or "
        "condition id, even though both are lowercase strings."
    ]
    for p in context:
        line = f'- passage_id={p.id} ({p.citation}): "{p.text}"'
        if p.feature_id is not None or p.condition_id is not None:
            line += (
                f" [this row: feature_id={p.feature_id}, condition_id={p.condition_id}"
                f", value={p.value}]"
            )
        lines.append(line)
    return "\n".join(lines)


#: Verified empirically (2026-09-01, against OpenRouter's Venice and
#: SiliconFlow routes for this model): ``response_format: {"type":
#: "json_schema", "json_schema": {"strict": true, "schema": <the full
#: TriageDecision schema>}}`` does not fail fast — it hangs indefinitely
#: (killed after 10+ minutes in testing). ``strict: false`` against the same
#: schema avoids the hang but the model spends thousands of tokens
#: "reasoning" about the request instead of answering, and
#: ``chat_template_kwargs.enable_thinking: false`` is inconsistently honoured
#: across OpenRouter's backing providers regardless of which strict setting
#: is used. Plain ``{"type": "json_object"}`` plus an explicit, direct
#: shape instruction in the prompt returned correctly in ~7 seconds in the
#: same testing. This is the documented reason this client does not use
#: ``json_schema``/``strict`` mode even though ADR 0011 describes guided
#: decoding as the intended contract — that guarantee assumed a self-hosted
#: vLLM server's own ``guided_json``, a single first-party implementation,
#: not a heterogeneous aggregation of third-party ones. Pydantic validation
#: on receipt (see :meth:`OpenRouterReasoningClient.decide`) is what actually
#: enforces the schema against this provider.
_JSON_SHAPE_INSTRUCTION = (
    "\n\nRespond with ONLY a single JSON object, no other text, matching this shape: "
    # The shape used to open '{"type": "ask", "conclude" or "decline", ...'.
    # Read as JSON that is three keys, not one key with three legal values,
    # and models copied it literally: observed live 2026-09-10 against both
    # OpenRouter and the campus adapter, which emitted a top-level
    # `"conclude": false` and were rejected by `extra="forbid"` — a whole turn
    # lost to a comma.
    # `observed` leads the shape, and its position is load-bearing. It used to
    # sit last, after ~1,700 tokens of instruction, and models simply omitted
    # it: observed live 2026-09-11, "my periods are all over the place" came
    # back with `observed: {}`, so `cycle_regularity=irregular` never entered
    # the case vector. Nothing then joined, every question scored 0.000, and
    # the ranked menu collapsed to alphabetical order — the model was left
    # choosing a follow-up from an unranked list. Recording what she said has
    # to happen before anything else is worth doing, so it is asked for first.
    '{"observed": {"a real feature_id": "one of that feature\'s listed values"}, '
    '"type": "<exactly one of: ask | conclude | inform | decline>", '
    '"rationale": "REQUIRED always. '
    "THIS IS THE TEXT SHE READS, on every decision type — write it to her, in "
    'plain words, second person", '
    '"next_feature_id": "REQUIRED string when type is ask — must be a real '
    "feature id from the list in the system prompt; null only when type is "
    'conclude", '
    '"question_text": "REQUIRED non-empty string when type is ask — the '
    'clarifying question for the user; null only when type is conclude", '
    '"answer_text": "REQUIRED non-empty string when type is inform, and legal '
    "ONLY then — the informational answer she reads, drawn from the retrieved "
    'passages and as long as the subject needs; null on every other type", '
    '"action_code": "one of SELF_CARE|ROUTINE_APPOINTMENT|URGENT_SAME_DAY|EMERGENCY, '
    'required only if type is conclude, else null", '
    '"matching_conditions": ["array of condition ids, at most 5, only if type is conclude; '
    'use [] not null when empty; '
    'allowed together with red_flag_id ONLY when action_code is EMERGENCY, and required '
    "then if any retrieved passage showed a matching condition_id; at any other urgency a "
    'red-flag-driven conclusion leaves this empty"], '
    '"citations": ["array of bare 16-hex passage ids ONLY — e.g. '
    '\\"a6bf0793b2a9a509\\"; never \\"passage_id=…\\" and never a feature '
    'or condition id; use [] not null"], '
    '"red_flag_id": "a red_flags.yaml id if this decision is driven by one, else null"}. '
    # Measured 2026-09-11 against the fine-tuned adapter: it emits well-formed
    # JSON with `observed` correctly filled, then omits `action_code` on a
    # conclude — on one probe it included it, on the next it did not, from an
    # identical request. That single missing key is the whole reason the
    # adapter's turns were being rejected and handed to the base model. The
    # shape spec already said "required only if type is conclude"; a
    # conditional requirement buried mid-spec was evidently too weak, so it is
    # restated here as a flat rule.
    "\n\nAN INFORM ANSWERS, AND ONLY ANSWERS. type \"inform\" is for an "
    "in-scope question that describes no case of her own — what something is, "
    "what causes it, what is normal. It takes `answer_text` (the answer), "
    "`citations` (every passage you drew on, never empty), `rationale` (one "
    "line on why this was a question to answer rather than a symptom to "
    "assess) and `observed` if her message happened to mention a real feature "
    "value. `action_code`, `matching_conditions`, `red_flag_id`, "
    "`next_feature_id` and `question_text` must ALL be null or [] — an "
    "informational answer assigns no urgency, names no condition as hers, and "
    "an inform carrying any of them is invalid and will be rejected. If a "
    "warning sign applies to what she said, or she is describing her own "
    "symptoms, do not inform: ask or conclude.\n"
    "\n\nTWO KEYS ARE NEVER OPTIONAL. If type is \"conclude\" you MUST include "
    "`action_code` — a conclude without one is rejected outright, however good "
    "the rest of it is. If type is \"ask\" you MUST include both "
    "`next_feature_id` and `question_text`. Check for these before you answer.\n"
    "\nFILL `observed` FIRST, BEFORE YOU DECIDE ANYTHING. It is the first key "
    "in the shape above for a reason: until her words are recorded against the "
    "feature vocabulary, nothing can be looked up, no warning sign can be "
    "checked, and the ranked question list you are given below is computed from "
    "an empty slate and is worth nothing. An empty `observed` on a message that "
    "plainly says something is the single most damaging mistake you can make "
    "here, and it is silent — you will still get an answer out, it will just be "
    "an uninformed one.\n"
    "Worked example. She writes \"my periods are all over the place\". That "
    'answers `cycle_regularity`, so observed is {"cycle_regularity": '
    '"irregular"} — not {}. She writes "I\'ve had really bad pain down there '
    'for three days and a fever": observed is {"pelvic_pain_severity": '
    '"severe", "fever": "yes"}. Everyday, indirect and emotional wording still '
    "counts: map what she means onto the closest listed value rather than "
    "waiting for her to use the clinical word.\n"
    "\nRECORDING WHAT SHE JUST SAID — the `observed` field, required on every "
    "ask and conclude. Read her most recent message and record every feature it "
    "answers: keys are feature ids from the lists above, values come from that "
    "feature's own listed values, or \"unknown\" when she was asked and could "
    "not say. Always include the feature you asked about last turn. A value "
    "outside that feature's listed values is REJECTED — it cannot be matched "
    "against a warning sign or looked up in the evidence, so recording "
    '"quite bad" where the values are mild/moderate/severe throws the answer '
    "away. Use {} only when her message answered nothing, and always on a "
    "decline: an off-scope message tells us nothing about her health. This "
    "field is what makes the next turn's warning-sign check and evidence "
    "lookup work; an answer you leave out is one she will be asked for twice."
    # Its own paragraph, deliberately. It used to be concatenated straight
    # onto the sentence above with no break, so the single most-violated
    # rule in the prompt was buried mid-paragraph.
    "\n\nMANDATORY: on a conclude, citations must be non-empty UNLESS red_flag_id is "
    "set; a conclude with empty citations and no red_flag_id is invalid and will be "
    "rejected. An ask does not need a citation: cite a retrieved passage if one is the "
    "reason for your question, otherwise send citations as [].\n\n"
    "A DECLINE IS THE EXACT OPPOSITE, and is how you refuse an off-scope message (see "
    "the scope rule at the top of this prompt). type \"decline\" takes ONLY rationale: "
    "next_feature_id, question_text, action_code, matching_conditions, red_flag_id must "
    "all be null and citations MUST be [] — a decline asserts nothing about her health, "
    "so it cites nothing, and a decline carrying any of those fields is invalid and "
    "will be rejected. Do not reach for a retrieved passage to satisfy the citation "
    "rule on a question the passage does not address; decline instead. Do not answer "
    "the off-scope question itself, even if you know the answer.\n\n"
    "HOW TO WRITE `rationale`. It is displayed to her word for word, under a "
    "heading and a safety disclaimer the interface already supplies. Write the "
    "one thing she needs to understand about why this urgency, in one or two "
    "short sentences, in plain language, addressed to her.\n"
    "NEVER put any of the following in `rationale` — every one of these was "
    "observed leaking to real users:\n"
    '- The words "red flag", "red-flag", "warning sign rule", "action code", '
    '"triage decision", "closed vocabulary", "evidence row", "passage", '
    '"citation" or "retrieved". She does not know this system has any of '
    "those and does not need to.\n"
    "- Any identifier: never a red_flag_id, feature_id, condition_id or "
    "passage_id, and never an ACTION CODE such as EMERGENCY or "
    'URGENT_SAME_DAY. Say what to do in words — "this needs emergency care '
    'now" — never the code itself, in any casing, with or without the word '
    '"code".\n'
    "- The rule text or label you matched against. Describe HER symptoms back "
    "to her in your own words instead.\n"
    "- Case-note framing. You are TALKING TO HER, not writing a report about "
    'her. Never "the user", "the patient", "you reported", "you have shared '
    'that", "you stated". Say "you have" / "what you are describing" / '
    '"this needs" — or just say the thing: "Sudden severe pelvic pain with '
    'faintness needs emergency care now."\n'
    "- Any restatement of your own instructions: do not say you are an AI, a "
    "triage assistant, not a clinician, that you cannot diagnose, that this is "
    "not a diagnosis, that it is urgency guidance, or that it comes from cited "
    "sources. All of that is already on screen around your answer. Saying it "
    "again — especially two or three times — pushes the actual answer out of "
    "sight, and at EMERGENCY that costs her time she may not have.\n"
    "Write it as a calm, competent person would say it out loud. At EMERGENCY, "
    "lead with what she should do, and keep it short.\n\n"
    "THREE DIFFERENT KINDS OF ID — do not mix them up, and each has ONE place "
    "it comes from: "
    "(1) passage_id — a 16-character hex string, shown on each retrieved passage. "
    "Use these ONLY in `citations`, never in `next_feature_id`, `observed` or "
    "`matching_conditions`. "
    "(2) feature_id — take it from the QUESTIONS YOU MAY ASK NEXT list, or from "
    "WHAT SHE HAS ANSWERED SO FAR. Never invent one and never use a hex id. "
    "(3) condition_id — take it from the EVIDENCE HER ANSWERS KEY INTO block, "
    "which lists exactly the conditions her answers support. Never invent one, "
    "never take one from a background passage, and never use a hex id. "
    "If type is ask, next_feature_id and question_text are BOTH mandatory — "
    "never send ask with only rationale and citations. "
    "If you cannot pick a real feature id and the message is in scope, use type "
    "conclude instead; if it is out of scope, use type decline. "
    "If she asked about a medicine, say in rationale (and in question_text if "
    "you are asking) that you cannot advise on medicines and she should ask a "
    "doctor or pharmacist — never answer the drug question yourself."
)


def _build_messages(
    *,
    system_prompt: str,
    history: Sequence[Message],
    context: Sequence[RetrievedPassage],
    retry_feedback: str = "",
) -> list[dict[str, str]]:
    system_content = (
        f"{system_prompt}\n\n{_render_context(context)}{_JSON_SHAPE_INSTRUCTION}{retry_feedback}"
    )
    return [
        {"role": "system", "content": system_content},
        *({"role": m.role, "content": m.content} for m in history),
    ]


def _strip_thinking_blocks(content: str) -> str:
    return _THINKING_BLOCK.sub("", content).strip()


def _drop_conditions_named_beside_a_red_flag(raw: object) -> object:
    """Strip ``matching_conditions`` from a red-flag conclusion below EMERGENCY.

    ``TriageDecision`` rejects that combination outright — ADR 0013: a red
    flag escalates on a symptom pattern without asserting what it is, and
    EMERGENCY is the one deliberate exception. That is the right rule and it
    is not being relaxed here: this removes the offending field so the rule
    holds, rather than letting the pair through.

    Rejecting is correct for a *check*, but this check runs during model
    construction, so the entire turn is lost and retried — and the model
    reliably repeats the mistake. Observed live 2026-09-17 on the base model:
    three attempts, ~132 seconds, then a 504, on a decision whose action code
    and red flag were both right.

    Same trade as ``triage.provenance.drop_unknown_conditions``: the field
    that may legally be empty gives way, and the field that gets her to care
    does not. ``action_code`` and ``red_flag_id`` are never touched, so the
    only thing removed is an assertion about what she has — which is the
    direction the rule wanted in the first place.
    """
    if not isinstance(raw, dict):
        return raw
    if not raw.get("red_flag_id") or not raw.get("matching_conditions"):
        return raw
    if raw.get("action_code") == ActionCode.EMERGENCY.value:
        return raw
    repaired = dict(raw)
    repaired["matching_conditions"] = []
    logger.info(
        "dropped matching_conditions from a red-flag %s decision (red_flag_id=%s); "
        "the escalation is unchanged",
        raw.get("action_code"),
        raw.get("red_flag_id"),
    )
    return repaired


def extract_json_object(text: str) -> str:
    """The first complete JSON object in ``text``.

    The one repair applied to a reply. A model that wraps a valid decision in
    a code fence, or adds a sentence after it, has still produced the
    decision; failing the turn on that costs a full extra generation for
    nothing. Braces inside string values are skipped, so a rationale that
    mentions one is not cut short. Nothing inside the object is changed.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("the reply contains no JSON object")
    depth = 0
    in_string = False
    escaped = False
    for position in range(start, len(text)):
        char = text[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : position + 1]
    raise ValueError("the reply contains no JSON object (it starts one and never closes it)")


def parse_decision_text(content: object) -> TriageDecision:
    """A model reply, as text, into a validated ``TriageDecision``."""
    try:
        if not isinstance(content, str):
            raise TypeError(
                f"message.content was {type(content).__name__}, not a string — the "
                "model returned no text to parse"
            )
        cleaned = _strip_thinking_blocks(content)
        if not cleaned.strip():
            raise ValueError("model returned an empty message")
        return TriageDecision.model_validate(
            _drop_conditions_named_beside_a_red_flag(json.loads(extract_json_object(cleaned)))
        )
    except (TypeError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"reasoning model returned malformed JSON: {error}") from error


def retry_feedback(error: Exception, context: Sequence[RetrievedPassage]) -> str:
    """What the model is told when its previous reply was rejected."""
    return (
        f"\n\nYOUR PREVIOUS JSON WAS REJECTED: {error}\n"
        "Fix it. If type is ask, include BOTH next_feature_id (a real "
        "feature id from the system prompt list) AND question_text. "
        "citations must be bare 16-character hex ids only "
        '(e.g. "a6bf0793b2a9a509"), never "passage_id=…". '
        "Use [] not null for empty arrays. If type is decline, send "
        "rationale only — every other field null, citations []. If you "
        "cannot ask a valid question, use type conclude with action_code "
        "instead, or type decline if the message is out of scope.\n"
        f"{_available_ids_hint(context)}\n"
        "Do not invent, abbreviate or pluralise an id. Copy it character "
        "for character from the list above."
    )


def _parse_chat_completion_payload(payload: object) -> TriageDecision:
    try:
        if not isinstance(payload, dict):
            raise TypeError(f"expected a JSON object, got {type(payload).__name__}")
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"reasoning model returned malformed JSON: {error}") from error
    return parse_decision_text(content)


def _available_ids_hint(context: Sequence[RetrievedPassage]) -> str:
    """The real condition and feature ids this turn actually offered.

    Fed back on a rejection because the model cannot be expected to guess a
    closed vocabulary it was never shown. ``render_feature_vocabulary``
    injects all 39 feature ids up front, but there is deliberately no
    equivalent for conditions: ``_JSON_SHAPE_INSTRUCTION`` requires a
    condition to come from a retrieved passage, so that the differential
    stays grounded in evidence rather than in the roster. Listing the whole
    of ``conditions.yaml`` here would undo that. Listing what *this turn*
    retrieved corrects the mistake without loosening the grounding rule —
    which is exactly the distinction that produced ``menopause`` where
    ``perimenopause`` was meant (observed 2026-09-09).
    """
    conditions = sorted({p.condition_id for p in context if p.condition_id is not None})
    features = sorted({p.feature_id for p in context if p.feature_id is not None})
    parts = []
    # Passage ids first, because the commonest rejection by far is an ASK sent
    # with empty citations — measured 2026-09-11 against the campus adapter,
    # four of five ASK decisions. The retry text told the model citations had
    # to be bare hex ids but never said which ones existed, so the correction
    # it was given was unactionable: the ids were only ever in the system
    # prompt it had already failed to use them from.
    passage_ids = [p.id for p in context]
    if passage_ids:
        parts.append(
            "The passage ids available to cite this turn, copied exactly: "
            f"{', '.join(passage_ids)}. citations must contain at least one of "
            "these unless red_flag_id is set — this is true for an ask as much "
            "as a conclude."
        )
    if conditions:
        parts.append(
            "The ONLY condition ids you may use in matching_conditions this turn, "
            f"copied exactly: {', '.join(conditions)}."
        )
    else:
        parts.append(
            "No retrieved passage carried a condition_id this turn. Take "
            "matching_conditions from the EVIDENCE HER ANSWERS KEY INTO block "
            "in the system prompt instead — those condition ids come from a "
            "lookup against what she answered and are the authoritative set. "
            "If that block is empty too, matching_conditions MUST be []."
        )
    if features:
        parts.append(f"Feature ids shown on this turn's passages: {', '.join(features)}.")
    return " ".join(parts)


#: Machine tokens that must never reach a user inside ``rationale`` or
#: ``question_text``. Deliberately narrow, and matched case-sensitively where
#: case is what distinguishes a code from ordinary English: "go to an
#: emergency room" is exactly right and must not be flagged, while
#: "action_code: EMERGENCY" must be. Each pattern below was written against
#: text this system actually produced (2026-09-09) — see
#: :func:`_reject_leaked_internals`.
_LEAKED_INTERNALS = (
    re.compile(r"\b(SELF_CARE|ROUTINE_APPOINTMENT|URGENT_SAME_DAY|EMERGENCY)\b"),
    re.compile(r"\b(red[_ -]?flag|action[_ ]code|next_feature_id|matching_conditions"
               r"|passage_id|condition_id|feature_id|red_flag_id|triage decision)\b",
               re.IGNORECASE),
    # Case-note framing. She is the person being spoken to, not a case being
    # written up about. Observed: "You reported heavy bleeding while 8 weeks
    # pregnant", "You have shared that you have a fever".
    re.compile(r"\b(the user|the patient|this patient|the woman|the individual"
               r"|user report(s|ed)?|patient report(s|ed)?"
               r"|you (have )?(report(ed)?|shared|stated|indicated|mentioned)( that)?)\b",
               re.IGNORECASE),
    # The disclaimer the interface already shows, parroted back. Observed
    # three times in a single EMERGENCY answer, crowding out the instruction
    # that actually mattered.
    re.compile(r"(not a diagnosis|urgency guidance|cited sources|cited evidence"
               r"|I am an AI|as an AI|not a clinician|cannot (provide |give )?diagnos)",
               re.IGNORECASE),
)


class WordingRejected(ValueError):
    """A reply whose decision is sound but whose user-facing text is not.

    A ``ValueError``, so every existing handler still treats it as an invalid
    reply. A type of its own because it is the one failure where everything
    that matters is right and only a phrase is wrong, which is worth one more
    attempt with feedback about the phrase alone.
    """

    def __init__(self, field: str, phrase: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.phrase = phrase


def _reject_leaked_internals(decision: TriageDecision) -> None:
    """Raise ``ValueError`` if user-facing text carries this system's plumbing.

    ``rationale`` is rendered to the user verbatim (``conclusion-card.tsx``,
    ``chat-message.tsx``, ``decline-card.tsx``), and ``question_text`` is the
    question she is asked. Observed leaking on 2026-09-09, before the
    prompt rules above existed: *"This matches a red-flag warning: pelvic
    pain with faintness or collapse"* — the system narrating its own rule
    machinery at a frightened user.

    Prompt instructions reduce that; they cannot guarantee it, and at
    ``EMERGENCY`` the cost of a confusing answer is measured in her time. So
    this is a hard check rather than a hope. It raises rather than rewrites:
    a silently stripped code leaves a sentence with a hole in it, and unlike
    ``provenance.enforce_provenance_cap``'s ``SELF_CARE`` floor there is no
    safe substitute for a sentence written to the wrong audience. Raising
    puts it through the same corrective-retry-then-fallback path as any other
    invalid decision.

    Note the deliberate asymmetry with ``ActionCode`` itself: the *field*
    ``action_code`` must of course hold ``EMERGENCY``. Only the prose is
    checked.
    """
    for field, text in (
        ("rationale", decision.rationale),
        ("question_text", decision.question_text),
        # An informational answer is rendered verbatim too, in an ordinary
        # assistant bubble (chat-message.tsx), and it is the longest
        # user-facing text this system produces — so the most room for the
        # plumbing to surface in.
        ("answer_text", decision.answer_text),
    ):
        if not text:
            continue
        for pattern in _LEAKED_INTERNALS:
            found = pattern.search(text)
            if found is not None:
                raise WordingRejected(
                    field,
                    found.group(0),
                    f"{field} contains internal machinery {found.group(0)!r}, which is shown "
                    "to the user verbatim. Rewrite it as plain language addressed to her, "
                    "with no identifiers, no action codes and no mention of warning-sign "
                    "rules — say what to do in words instead."
                )
