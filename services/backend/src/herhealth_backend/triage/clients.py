"""Real ``ReasoningClient`` / ``RetrievalClient`` implementations — ADR 0012.

Neither class here is imported by ``agent.py``, ``engine.py``, or anything
else in the triage core — only by whoever wires ``TriageAgent`` up for real
(ADR 0012's migration checklist item 4, not started yet). That keeps the
triage core importable with no network, no server and no GPU, exactly as
``services/backend/pyproject.toml`` states as a property worth protecting.
Needs the ``agent`` extra (``httpx``) — not a base dependency, for the same
reason.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Sequence

import httpx
from herhealth_contracts.decision import TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.retrieval import RetrievedPassage
from pydantic import TypeAdapter, ValidationError

from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningClient,
    ReasoningResult,
)

__all__ = [
    "DEFAULT_MODEL",
    "DecisionValidator",
    "DEFAULT_VLLM_MODEL",
    "FallbackReasoningClient",
    "HttpRetrievalClient",
    "OPENROUTER_API_KEY_ENV",
    "OpenRouterReasoningClient",
    "VLLM_API_KEY_ENV",
    "VLLM_MODEL_ENV",
    "VLLM_URL_ENV",
    "VllmReasoningClient",
]

logger = logging.getLogger(__name__)

#: The closed-vocabulary check, bound to a ``KnowledgeBase``. Structural, not
#: an import of ``vocabulary``: keeping this a plain callable is what stops
#: ``clients`` depending on the module that owns the rule, so a client can
#: still be constructed with no knowledge base at all (every test does).
DecisionValidator = Callable[[TriageDecision, Sequence[RetrievedPassage]], None]

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
VLLM_URL_ENV = "HERHEALTH_VLLM_URL"
VLLM_MODEL_ENV = "HERHEALTH_VLLM_MODEL"
VLLM_API_KEY_ENV = "HERHEALTH_VLLM_API_KEY"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

#: The base model, unadapted. NOT the fine-tuned LoRA adapter — OpenRouter
#: serves published models, not this project's private one. Swapping to the
#: retrained adapter (once it exists and is reviewed, per CLAUDE.md) means
#: going back to a self-hosted vLLM server
#: (docs/runbooks/dev-vllm-lora-endpoint.md) and a different concrete
#: ReasoningClient — not editing this string. ReasoningClient being a
#: Protocol is what makes that swap a new class instead of a rewrite of
#: TriageAgent.
DEFAULT_MODEL = "qwen/qwen3.5-9b"

#: The LoRA adapter name as registered with ``vllm serve --lora-modules``.
DEFAULT_VLLM_MODEL = "herhealth"

#: Per-call retries when OpenRouter returns JSON that fails ``TriageDecision``
#: validation — same prompt twice often repeats the mistake; feedback helps.
MAX_DECISION_ATTEMPTS = 3

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
    '"type": "<exactly one of: ask | conclude | decline>", "rationale": "REQUIRED always. '
    "THIS IS THE TEXT SHE READS, on every decision type — write it to her, in "
    'plain words, second person", '
    '"next_feature_id": "REQUIRED string when type is ask — must be a real '
    "feature id from the list in the system prompt; null only when type is "
    'conclude", '
    '"question_text": "REQUIRED non-empty string when type is ask — the '
    'clarifying question for the user; null only when type is conclude", '
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
    "\n\nMANDATORY: citations must be non-empty UNLESS red_flag_id is set — this applies to "
    "an ask as much as a conclude. If you are asking a question because of something a "
    "retrieved passage suggests, cite that passage's id even though you have not "
    "concluded yet. An ask or conclude with empty citations and no red_flag_id is "
    "invalid and will be rejected.\n\n"
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
    if raw.get("action_code") in (
        ActionCode.EMERGENCY.value,
        ActionCode.URGENT_SAME_DAY.value,
    ):
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


def _parse_chat_completion_payload(payload: object) -> TriageDecision:
    try:
        # `assert` rather than a raised ValueError was a real gap, not a
        # style point: AssertionError is not in the except clause below, so a
        # provider returning `content: null` escaped as a bare
        # `AssertionError: ` with no message and no retry — observed
        # 2026-09-10, a consultation lost after 1,327 seconds to an error
        # that said nothing about what happened.
        if not isinstance(payload, dict):
            raise TypeError(f"expected a JSON object, got {type(payload).__name__}")
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError(
                f"message.content was {type(content).__name__}, not a string — the "
                "model returned no text to parse"
            )
        cleaned = _strip_thinking_blocks(content)
        if not cleaned.strip():
            raise ValueError("model returned an empty message")
        return TriageDecision.model_validate(
            _drop_conditions_named_beside_a_red_flag(json.loads(cleaned))
        )
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"reasoning model returned malformed JSON: {error}") from error


def _chat_completions_body(
    *,
    model: str,
    messages: list[dict[str, str]],
    enforce_json_object: bool = True,
) -> dict[str, object]:
    """Build the OpenAI-compatible chat body.

    ``response_format: json_object`` is on for OpenRouter. On campus vLLM
    (Qwen3.5 + LoRA, TP=2) that same field turns on xgrammar structured
    outputs; the Triton ``apply_token_bitmask_inplace`` kernel then hits
    ``CUDA: unspecified launch failure``, kills Worker_TP1, and takes the
    whole EngineCore down (observed 2026-09-08 on Lobot). Prompt-shaped JSON
    plus ``TriageDecision.model_validate`` is enough until guided decoding is
    wired deliberately (ADR 0011 checklist item 7).
    """
    body: dict[str, object] = {
        "model": model,
        "messages": messages,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if enforce_json_object:
        body["response_format"] = {"type": "json_object"}
    return body


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
    ):
        if not text:
            continue
        for pattern in _LEAKED_INTERNALS:
            found = pattern.search(text)
            if found is not None:
                raise ValueError(
                    f"{field} contains internal machinery {found.group(0)!r}, which is shown "
                    "to the user verbatim. Rewrite it as plain language addressed to her, "
                    "with no identifiers, no action codes and no mention of warning-sign "
                    "rules — say what to do in words instead."
                )


def _decide_via_chat_completions(
    *,
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    model: str,
    system_prompt: str,
    history: Sequence[Message],
    context: Sequence[RetrievedPassage],
    enforce_json_object: bool = True,
    validator: DecisionValidator | None = None,
    max_attempts: int = MAX_DECISION_ATTEMPTS,
) -> TriageDecision:
    """POST /v1/chat/completions with validation retries and error feedback.

    ``validator`` is the closed-vocabulary check
    (``vocabulary.validate_against_knowledge_base``, bound to a
    ``KnowledgeBase``). It runs **inside** this loop, deliberately.

    It used to run only in ``app/triage/routes.py``, after this function had
    already returned, and that placement was the direct cause of a class of
    502s: a decision naming an id that is not in ``conditions.yaml`` is
    exactly the kind of mistake a model corrects when told about it, but
    there was no path for telling it. The route could only re-run the whole
    turn — fresh retrieval, no memory of the error — and
    ``FallbackReasoningClient`` never saw the failure at all, because a
    ``ClosedVocabularyViolation`` was raised past the point where it could
    intercept.

    Running it here makes a vocabulary violation behave like every other
    validation failure: corrective feedback naming the invalid id and the
    real ones, up to ``MAX_DECISION_ATTEMPTS``, then a ``ValueError`` that
    ``FallbackReasoningClient`` can fail over on. The check in ``routes.py``
    stays as a backstop for any client wired without a validator.
    """
    retry_feedback = ""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        messages = _build_messages(
            system_prompt=system_prompt,
            history=history,
            context=context,
            retry_feedback=retry_feedback,
        )
        body = _chat_completions_body(
            model=model,
            messages=messages,
            enforce_json_object=enforce_json_object,
        )
        try:
            response = client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as error:
            # A slow answer is not a broken one, and until 2026-09-11 this
            # call sat outside the try below — so a read timeout escaped the
            # loop immediately and `max_attempts` only ever retried malformed
            # JSON. Measured that day against the campus adapter: latency for
            # an identical request swung between 4.7s and over 45s depending
            # on GPU contention, and five of six turns in one consultation
            # fell back to the base model on the first slow response, with no
            # second attempt. Retrying is worth it precisely because the
            # variance is this wide — the next attempt is often fast.
            last_error = error
            if attempt >= max_attempts:
                raise
            logger.warning(
                "reasoning request timed out (attempt %d/%d) — retrying",
                attempt,
                max_attempts,
            )
            continue
        response.raise_for_status()
        try:
            decision = _parse_chat_completion_payload(response.json())
            _reject_leaked_internals(decision)
            if validator is not None:
                # ClosedVocabularyViolation subclasses ValueError, so it is
                # caught below and fed back like a schema failure.
                validator(decision, context)
            return decision
        except ValueError as error:
            last_error = error
            if attempt >= max_attempts:
                raise
            retry_feedback = (
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
            logger.warning(
                "decision attempt %s/%s failed (%s) — retrying with feedback",
                attempt,
                max_attempts,
                error,
            )
    raise ValueError(str(last_error))


class OpenRouterReasoningClient:
    """Implements ``herhealth_backend.triage.agent.ReasoningClient`` against
    OpenRouter's chat-completions API. Requests plain JSON-object output
    (not schema-constrained ``json_schema``/``strict`` mode — see
    ``_JSON_SHAPE_INSTRUCTION``'s comment for why that hangs in practice)
    with the required shape spelled out directly in the prompt.
    ``TriageDecision.model_validate`` on receipt is what actually enforces
    the schema here, not the provider — this is a real gap against ADR
    0011's "guided decoding" guarantee, which assumed a self-hosted vLLM
    server's own constrained decoding, not a plain-JSON request to a
    third-party aggregator. A malformed or out-of-vocabulary response fails
    here, legibly, as a ``pydantic.ValidationError`` — it is not silently
    accepted.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        client: httpx.Client | None = None,
        # 120s, matching VllmReasoningClient below, because 60s was under the
        # observed latency of this very endpoint: app/triage/routes.py's
        # REASONING_TIMEOUT_SECONDS documents "a few seconds to ~90s across
        # manual testing" and budgets 150s for the whole turn. A 60s read
        # timeout therefore aborted responses that were merely slow, and an
        # httpx timeout is raised as httpx.HTTPError, which that route turns
        # straight into a 502 without a retry — so a healthy 75s answer was
        # indistinguishable to the user from a broken dependency. Confirmed
        # live 2026-09-03: "triage dependency HTTP failure: The read
        # operation timed out" at 116s wall-clock on an in-scope emergency.
        # Keep this below REASONING_TIMEOUT_SECONDS so the inner call fails
        # inside the turn's own budget rather than racing it.
        timeout: float = 120.0,
        decision_validator: DecisionValidator | None = None,
        #: How this client identifies itself in a ``ReasoningAttempt``. The
        #: model id is in it by default because the report needs to say which
        #: model, not merely which provider.
        name: str | None = None,
    ) -> None:
        key = api_key or os.environ.get(OPENROUTER_API_KEY_ENV)
        if not key:
            raise RuntimeError(
                f"{OPENROUTER_API_KEY_ENV} is not set and no api_key was given — "
                "OpenRouterReasoningClient needs an OpenRouter API key."
            )
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self._validator = decision_validator
        self._name = name or f"openrouter:{model}"

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
        decision = _decide_via_chat_completions(
            client=self._client,
            url=_OPENROUTER_URL,
            headers=self._headers,
            model=self._model,
            system_prompt=system_prompt,
            history=history,
            context=context,
            validator=self._validator,
        )
        return ReasoningResult(
            decision=decision,
            attempts=(ReasoningAttempt(client=self._name, outcome=AttemptOutcome.OK),),
        )


class VllmReasoningClient:
    """Self-hosted vLLM with the project's LoRA adapter (``herhealth``).

    See ``docs/runbooks/dev-vllm-lora-endpoint.md`` and
    ``docs/runbooks/friend-pc-vllm-setup.md``. Uses the same plain-JSON
    contract as :class:`OpenRouterReasoningClient` until guided decoding is
    wired (ADR 0011 migration checklist item 7). Does **not** send
    ``response_format: json_object`` — on the Lobot Qwen3.5 + LoRA serve that
    path crashes the engine via xgrammar/Triton (see
    ``_chat_completions_body``).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        # 50s, not 120s: the campus endpoint sits behind a reverse proxy
        # that cuts at ~60s and returns 504. Losing that race on purpose
        # turns "slow" into a clean, fast fail-over instead of a gateway
        # error — see app/config.py's vllm_timeout for the full reasoning.
        timeout: float = 50.0,
        decision_validator: DecisionValidator | None = None,
        max_attempts: int = 2,
        #: See OpenRouterReasoningClient's ``name``. Defaults to the adapter
        #: name as registered with ``--lora-modules``, so "vllm:herhealth" in
        #: a report is unambiguously the fine-tuned adapter.
        name: str | None = None,
    ) -> None:
        raw_url = base_url or os.environ.get(VLLM_URL_ENV, "http://127.0.0.1:8002")
        self._url = f"{raw_url.rstrip('/')}{_CHAT_COMPLETIONS_PATH}"
        self._model = model or os.environ.get(VLLM_MODEL_ENV, DEFAULT_VLLM_MODEL)
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"Content-Type": "application/json"}
        # vLLM's ``--api-key`` makes it expect the same Bearer scheme
        # OpenRouter uses. Added only when a key exists: an empty
        # Authorization header is worse than none, because a server that
        # requires no key would still see a malformed credential.
        key = api_key or os.environ.get(VLLM_API_KEY_ENV) or None
        if key:
            self._headers["Authorization"] = f"Bearer {key}"
        self._validator = decision_validator
        self._max_attempts = max_attempts
        self._name = name or f"vllm:{self._model}"

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
        decision = _decide_via_chat_completions(
            client=self._client,
            url=self._url,
            headers=self._headers,
            model=self._model,
            system_prompt=system_prompt,
            history=history,
            context=context,
            enforce_json_object=False,
            validator=self._validator,
            max_attempts=self._max_attempts,
        )
        return ReasoningResult(
            decision=decision,
            attempts=(ReasoningAttempt(client=self._name, outcome=AttemptOutcome.OK),),
        )


#: Failure detail is stored and later rendered in a report, so it is capped:
#: an unbounded exception string can carry a whole HTTP body, and this ends up
#: in a database column read by a human.
_MAX_ATTEMPT_DETAIL = 200


def _attempt_detail(error: Exception) -> str:
    """A short, readable reason a call failed. Never the whole exception."""
    text = str(error).strip() or type(error).__name__
    if len(text) > _MAX_ATTEMPT_DETAIL:
        return f"{text[: _MAX_ATTEMPT_DETAIL - 1]}…"
    return text


class FallbackReasoningClient:
    """Try a primary ``ReasoningClient`` (typically the fine-tuned vLLM
    adapter), then a fallback (typically the OpenRouter base model) when the
    primary does not return a usable ``TriageDecision``.

    Three classes of failure hand over:

    * **Unreachable** — ``httpx.ConnectError`` / ``httpx.TimeoutException``.
    * **Upstream unavailable** — HTTP 502/503/504. Any other status is
      re-raised, because a 400 or 401 is a bug in the request, not a sick
      server, and retrying it elsewhere hides that.
    * **No valid decision** — ``ValueError``, which is what
      :func:`_decide_via_chat_completions` raises once it has exhausted
      ``MAX_DECISION_ATTEMPTS`` and still has nothing that validates.

    That third case reverses an earlier decision recorded here, and the
    reversal is deliberate. This class previously re-raised a malformed
    response on the grounds that "a different server cannot fix it". That
    reasoning holds when the fallback is another instance of the same model;
    it does not hold here, where the fallback is a **different model**. The
    fine-tuned adapter was trained on `gold_seeds_styled.csv`, which contains
    no example of emitting a structured decision under uncertainty, and it
    fails the schema in ways the base model does not: measured 2026-09-09
    over repeated identical in-scope turns, roughly one turn in four ended in
    a 502, dominated by ``ask`` decisions sent with empty ``citations``. The
    base model is precisely the thing that can fix that, so it is now given
    the chance.

    **This does not make the primary's output trustworthy** — it makes a
    failed turn recoverable. The decision that reaches the user in that case
    came from the fallback, and ``reasoning_model`` still names the model the
    *caller selected*, which on a fallback is not the one that answered.

    **Which model actually answered is recorded.** Every call is appended to
    :attr:`~herhealth_backend.triage.agent.ReasoningResult.attempts` as a
    :class:`~herhealth_backend.triage.agent.ReasoningAttempt` — the client's
    name, how the call ended, and why it failed when it did. That trail
    reaches the API response and the ``messages.served_by`` column, so a
    fallback is visible downstream and the fallback *rate* is measurable
    rather than anecdotal. It is deliberately **not** carried on
    ``TriageDecision``: that schema is ``extra="forbid"`` and is what guided
    decoding constrains, so a field there would be the model asserting its
    own identity instead of the transport observing it.

    Naming is owned here, not by the children: this class labels both
    backends, so a nested fallback flattens to the outer labels. Pass
    ``primary_name``/``fallback_name`` to override what a child calls itself.

    What is still **not** caught here: ``ClosedVocabularyViolation``, raised
    by ``app/triage/routes.py`` *after* ``decide`` returns, so this client
    never sees it. A decision citing a condition outside
    ``conditions.yaml`` — observed once, ``menopause`` for the real
    ``perimenopause`` — is retried by that route's own loop against the same
    client, not failed over. Closing that gap means either moving validation
    inside the client or making the route fallback-aware.
    """

    def __init__(
        self,
        *,
        # The Protocol, not the two concrete classes: this wrapper is itself a
        # ReasoningClient, so widening here is what lets it be nested or given
        # a demo client in a test without special-casing.
        primary: ReasoningClient,
        fallback: ReasoningClient,
        primary_name: str | None = None,
        fallback_name: str | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        # ``getattr`` rather than ``primary.name``: the Protocol requires the
        # attribute, but a test double predating it should degrade to a
        # readable label instead of an AttributeError mid-turn.
        self._primary_name = primary_name or getattr(primary, "name", "vllm")
        self._fallback_name = fallback_name or getattr(fallback, "name", "openrouter")

    @property
    def name(self) -> str:
        return f"{self._primary_name} -> {self._fallback_name}"

    def decide(
        self,
        *,
        system_prompt: str,
        history: Sequence[Message],
        context: Sequence[RetrievedPassage],
    ) -> ReasoningResult:
        try:
            served = self._primary.decide(
                system_prompt=system_prompt, history=history, context=context
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in {502, 503, 504}:
                raise
            logger.warning(
                "%s returned HTTP %s — falling back to %s",
                self._primary_name,
                error.response.status_code,
                self._fallback_name,
            )
            failure = ReasoningAttempt(
                client=self._primary_name,
                outcome=AttemptOutcome.UPSTREAM_UNAVAILABLE,
                detail=f"HTTP {error.response.status_code}",
            )
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            logger.warning(
                "%s unreachable (%s) — falling back to %s",
                self._primary_name,
                error,
                self._fallback_name,
            )
            failure = ReasoningAttempt(
                client=self._primary_name,
                outcome=AttemptOutcome.UNREACHABLE,
                detail=_attempt_detail(error),
            )
        except ValueError as error:
            # Raised by _decide_via_chat_completions after MAX_DECISION_ATTEMPTS
            # of prompt-level correction still failed to validate. Listed last:
            # the httpx clauses above are not ValueError subclasses, but keeping
            # this at the bottom makes the precedence obvious to a reader rather
            # than dependent on knowing that.
            logger.warning(
                "%s produced no valid decision (%s) — falling back to %s",
                self._primary_name,
                error,
                self._fallback_name,
            )
            failure = ReasoningAttempt(
                client=self._primary_name,
                outcome=AttemptOutcome.INVALID_DECISION,
                detail=_attempt_detail(error),
            )
        else:
            # The primary answered. Relabelled to this class's name for the
            # primary rather than passed through, so one turn's trail reads in
            # one vocabulary — see the naming note in the class docstring.
            return ReasoningResult(
                decision=served.decision,
                attempts=(
                    ReasoningAttempt(
                        client=self._primary_name, outcome=AttemptOutcome.OK
                    ),
                ),
            )

        recovered = self._fallback.decide(
            system_prompt=system_prompt, history=history, context=context
        )
        return ReasoningResult(
            decision=recovered.decision,
            attempts=(
                failure,
                ReasoningAttempt(client=self._fallback_name, outcome=AttemptOutcome.OK),
            ),
        )


class HttpRetrievalClient:
    """Implements ``herhealth_backend.triage.agent.RetrievalClient`` against
    ``services/model``'s ``/search`` endpoint. Never imports
    ``herhealth_data`` — the whole reason that service exists is so this
    client does not have to (import-linter forbids it across this boundary).
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8001",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        response = self._client.post(f"{self._base_url}/search", json={"query": query, "k": k})
        response.raise_for_status()
        return TypeAdapter(list[RetrievedPassage]).validate_python(response.json())
