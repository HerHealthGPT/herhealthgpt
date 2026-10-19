"""The structured-output contract for the reasoning model's per-turn decision.

Stands in for ``herhealth_backend.triage.state.Decision`` /
``herhealth_backend.triage.state.StopReason`` now that no deterministic
``should_stop`` controller runs between the user and the model. A
:class:`TriageDecision` is what the reasoning model is asked to emit each
turn, as guided JSON, instead of free text — ``TriageDecision.model_json_schema()``
is the contract passed to the model server (vLLM's ``guided_json`` /
structured-output parameter) so the model is constrained to the same closed
vocabularies (:class:`~herhealth_contracts.knowledge.ActionCode`, a real
``feature_id``) that the deterministic controller used to enforce in code.

Read this as the one deterministic safety net left once the controller is
removed, and no more than that: schema validation stops the model from
emitting an action code or a feature id that does not exist. It cannot stop
the model from choosing the wrong *one* — that risk is what the retraining
plan and the eval changes described alongside this file exist to manage, not
this schema.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from herhealth_contracts.knowledge import ActionCode, Identifier, NonEmptyText
from herhealth_contracts.retrieval import PassageId

__all__ = ["DecisionType", "TriageDecision"]

#: OpenRouter models often copy the prompt's ``passage_id=…`` label into
#: ``citations`` instead of the bare 16-hex id. Strip that prefix before
#: schema validation so one bad format does not cost a full model retry
#: (observed live: 1–3 retries × ~10–60s each).
_PASSAGE_ID_PREFIX = re.compile(r"^(?:passage_id\s*=\s*)?", re.IGNORECASE)

#: The shape ``Identifier`` requires. Used to drop malformed condition names
#: before validation rather than failing the decision on them — see
#: ``_coerce_null_collections``.
_IDENTIFIER_SHAPE = re.compile(r"[a-z][a-z0-9_]*")


class DecisionType(StrEnum):
    """What the reasoning model chose to do this turn. Nothing else is legal."""

    ASK = "ask"
    CONCLUDE = "conclude"
    INFORM = "inform"
    DECLINE = "decline"


class TriageDecision(BaseModel):
    """One turn's decision, emitted by the reasoning model as guided JSON.

    ``rationale`` is required on every decision, including an ``ask`` — a
    question still has to say why, from what has been seen so far, which is
    what makes the transcript auditable without a deterministic trace to fall
    back on. An ``ask`` or a ``conclude`` must also point at *something* it
    was grounded on — ``citations``, ``red_flag_id``, or both — for the same
    reason: a decision citing nothing is not distinguishable from one the
    model made up. ``DECLINE`` is the one exemption, and the next paragraph
    is why.

    **Why ``DECLINE`` exists, and why it grounds nothing.** With only ASK and
    CONCLUDE, this schema had no way to represent "that is not something this
    system does", so every input got an urgency verdict whether or not it was
    a women's-reproductive-health question at all. Observed live 2026-09-03:
    asked *"who won world cup 2026"*, the model returned CONCLUDE /
    ``SELF_CARE`` and — because the grounding rule above left it no other
    legal move — attached a real Office on Women's Health quote about a
    complete blood count as the evidence for it. Nothing misbehaved; the
    model picked the only shape available. The failure was that a refusal was
    unrepresentable.

    A DECLINE therefore carries **no** ``action_code``, ``next_feature_id``,
    ``question_text``, ``matching_conditions``, ``red_flag_id`` or
    ``citations`` — only its ``rationale``, which is what she reads. It is
    exempt from the grounding rule because it asserts nothing about her
    health for a citation to support, and requiring one is precisely what
    manufactured the spurious citation above. Forbidden rather than merely
    optional, so "declined *and* assigned an urgency" cannot be built at all.

    Scope is defined as what the knowledge base can actually ground — the
    conditions in ``conditions.yaml``, the features in ``features.yaml``, the
    rules in ``red_flags.yaml``. A question those cannot speak to is declined
    rather than answered thinly, which keeps a refusal provable instead of a
    matter of taste. See ADR 0014.

    **Why ``INFORM`` exists, and why it is the most tightly bounded shape
    here.** ASK, CONCLUDE and DECLINE between them covered every message
    *about her* — a symptom to narrow, a symptom to rule on, or a topic this
    system does not cover. They did not cover a question about the subject
    matter itself. Asked "what actually is PCOS?", the only legal moves were
    to put a clarifying question to a woman who had reported no symptom, to
    assign an urgency level to a question that described no case, or to
    refuse a question squarely inside the knowledge base's own subject
    matter. INFORM is the fourth shape: answer the question from what the
    retrieved passages say, cite them, and assign no urgency.

    It is deliberately the *narrowest* shape in this enum, because an
    informational reply is the one shape that could be used to walk around
    triage altogether — and under-triage is this project's dominant failure
    mode (CLAUDE.md). Three properties hold by schema rather than by prompt:

    * **No ``action_code``.** An INFORM cannot say SELF_CARE, so it can never
      function as reassurance. It is information, not a verdict, and the
      absence of an urgency level is what makes that structural.
    * **No ``red_flag_id``, and ``citations`` required non-empty.** Note the
      direction: this is *stricter* than ASK and CONCLUDE, which may ground
      themselves on a red flag instead of a citation. A warning sign is a
      reason to escalate, never a reason to explain — so a decision that has
      noticed one cannot be an INFORM at all, and an INFORM with nothing
      retrieved to stand on is unrepresentable. That closes the hole ADR 0014
      found, from the other side: there, a refusal was forced to manufacture
      a citation; here, an answer cannot be given without one.
    * **No ``matching_conditions``.** That field means "conditions whose
      pattern *her answers* matched", and an INFORM has matched nothing
      against her — she described no case. An informational answer may
      discuss a condition in prose, grounded in the passages it cites, but it
      may never attach one to her. "Never diagnoses" therefore holds on this
      path by construction rather than by wording.

    ``observed`` *is* allowed, unlike on a DECLINE, and the asymmetry is the
    point: an off-scope message tells us nothing about her health, whereas an
    in-scope question may carry real information in passing ("I get awful
    cramps — what is endometriosis?"). Recording that is what lets the next
    turn pick up where this one left off rather than starting cold.

    What the schema cannot enforce, and the prompt therefore must: that a
    message describing her own current symptoms is triaged rather than
    explained. See ADR 0016's risk register, which names that rather than
    implying it is covered.

    **Why two separate grounding fields, not one.** Walking a real example
    through the flow (a case matching both ``severe_pelvic_pain`` and, one
    answer away, the more severe ``sudden_severe_pelvic_pain``) surfaced that
    a decision driven by a red flag has nothing to put in ``citations``:
    ``red_flags.yaml`` is deliberately never embedded or retrieved (see
    ``herhealth_backend.triage.agent.render_red_flags``), so it produces no
    ``PassageId`` to cite. ``citations`` alone, required non-empty, could not
    represent that decision at all. ``red_flag_id`` is the fix: it names a
    real ``id`` from ``red_flags.yaml`` directly, the same closed vocabulary
    a ``next_feature_id`` names one from ``features.yaml``.

    **Why ``matching_conditions`` is conditionally forbidden, not just
    optional.** The product decision is to name which authored conditions a
    CONCLUDE decision's pattern matches — "matches patterns associated with
    X, Y", never "you have X" — so a user gets more than an urgency level.
    ``CLAUDE.md`` also carries one hard-won rule about naming conditions:
    cancer is deliberately unmodelled and *"served by red flags instead —
    postmenopausal bleeding routes to a GP without ever naming why."*
    ADR 0011 generalised that to every red flag — a decision driven by one
    must not name a condition, because red flags exist to escalate on a
    symptom pattern without asserting what it is.

    **This was later narrowed, deliberately, for ``EMERGENCY`` specifically**
    (product decision, not a safety finding reversed): the team decided an
    emergency conclusion should be allowed to name matching conditions
    alongside the ``red_flag_id`` that drove it, on the reasoning that at
    EMERGENCY severity the value of naming what she might be dealing with
    outweighs the "never assert a specific condition while escalating" rule
    the cancer/red-flag discipline otherwise holds everywhere else.
    ``URGENT_SAME_DAY`` (and every other action) keeps the original rule
    unchanged: a red-flag-driven decision at that severity still may not
    name a condition. This is enforced below, not left to the prompt alone.

    **Why ``matching_conditions`` is capped at 5.** Generating the bootstrap
    dataset against the real knowledge base showed what an uncapped list
    actually looks like: most of the 18 authored conditions have no row that
    argues against them (ADR 0007 finding 1), so a "live differential" barely
    narrows at all — the first uncapped run named 18 or 19 conditions on
    almost every conclusion, which is not a differential, it is the condition
    roster. A hard cap forces a shortlist even when nothing upstream narrowed
    one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    type: DecisionType

    #: Required, and only legal, when type is ASK.
    next_feature_id: Identifier | None = None
    question_text: NonEmptyText | None = None

    #: Required, and only legal, when type is CONCLUDE.
    action_code: ActionCode | None = None

    #: Required, and only legal, when type is INFORM: the answer she reads,
    #: assembled from the passages named in ``citations``.
    #:
    #: A field of its own rather than a long ``rationale``, for the same
    #: reason ``question_text`` is one: ``rationale`` is one or two sentences
    #: saying *why* this turn went the way it did, and it is held to that by
    #: the prompt and by ``clients._reject_leaked_internals``. An
    #: informational body is a different kind of text, at a different length,
    #: so conflating the two would leave neither field reliably meaning
    #: either thing. A reader of this schema can see which field is the
    #: answer.
    answer_text: NonEmptyText | None = None

    #: Real conditions.yaml ids whose pattern the answers matched, for a
    #: CONCLUDE only. Legal alongside red_flag_id only when action_code is
    #: EMERGENCY (the deliberate exception — see the class docstring);
    #: otherwise a red-flag-driven decision may not carry this. Always
    #: rendered to the user as "matches patterns associated with", never as
    #: "you have". May be empty even on a qualifying CONCLUDE: naming
    #: conditions is offered, not mandatory. Capped at 5 — see the class
    #: docstring for why an uncapped list is actively unhelpful in this
    #: knowledge base, not just verbose.
    matching_conditions: tuple[Identifier, ...] = Field(default=(), max_length=5)

    #: Passage ids (see herhealth_contracts.retrieval.RetrievedPassage) the
    #: decision was grounded on. May be empty only if red_flag_id is set —
    #: see _shape_matches_type.
    citations: tuple[PassageId, ...] = ()

    #: A real red_flags.yaml id, when this decision is driven by one — either
    #: concluding because it fired, or asking because a more severe rule is
    #: one unanswered clause away (the old engine's "escalation screen", now
    #: something the model has to notice for itself rather than something
    #: should_stop guaranteed).
    red_flag_id: Identifier | None = None

    #: What she said, mapped onto the closed feature vocabulary — the case
    #: vector. Keys are ``features.yaml`` ids, values are that feature's
    #: ``allowed_values`` (or ``unknown``). Filled on the turn the model
    #: *reads* her answer, not the turn it asks the question, so no extra
    #: model call is needed to extract it.
    #:
    #: This is the field that makes the knowledge base's structure reachable
    #: at runtime. Without it, ``red_flags.yaml``'s clauses cannot be
    #: evaluated against anything, and ``evidence.csv``'s 140 keyed rows can
    #: only be reached by similarity search — which measurably returns none of
    #: them on a typical query. With it, both become lookups. See
    #: ``herhealth_backend.triage.context``.
    #:
    #: **It records, it does not decide.** Nothing in this package or in
    #: ``context`` turns an observation into an action code; ADR 0011 leaves
    #: that with the model. Cross-checking the keys and values against the
    #: real knowledge base happens in
    #: ``herhealth_backend.triage.vocabulary``, for the same reason citations
    #: are checked there — this package has no knowledge base to check against.
    #:
    #: Empty on a DECLINE, like citations and for the same reason: an
    #: off-scope message tells us nothing about her health, so recording a
    #: symptom from one would put a fact in the case vector that she never
    #: reported about a topic this system does not cover.
    #:
    #: One consequence worth knowing before it surprises someone: a mapping
    #: field makes this ``frozen=True`` model **unhashable**, and the same
    #: goes for the frozen dataclasses that hold one (``AgentTurn``). Nothing
    #: currently puts a decision in a set or uses one as a dict key — they
    #: only ever go into lists — so this costs nothing today, but a future
    #: caller that tries will get ``unhashable type: 'dict'`` rather than a
    #: schema error, which is not an obvious message to debug from.
    observed: Mapping[Identifier, str] = Field(default_factory=dict)

    #: Why, in the model's own words. Logged verbatim alongside the decision.
    rationale: NonEmptyText

    @model_validator(mode="before")
    @classmethod
    def _coerce_null_collections(cls, data: object) -> object:
        """OpenRouter often emits ``null`` for empty array fields; Pydantic
        tuple fields reject that. Coerce before shape validation runs.

        Also normalises citation ids that were copied with a ``passage_id=``
        prefix from the retrieval prompt — the id itself is still the same
        16-hex hash; only the label is wrong.
        """
        if not isinstance(data, dict):
            return data
        patched = dict(data)
        # A key the schema does not have, set to null, says nothing: the model
        # copied feature names in beside the real fields ("fever": null).
        # Observed 2026-10-19 in Arabic consultations, where it cost a whole
        # retry each time. Dropped; an unknown key WITH a value still fails.
        for key in [k for k, v in patched.items() if v is None and k not in cls.model_fields]:
            del patched[key]
        for key in ("matching_conditions", "citations"):
            if patched.get(key) is None:
                patched[key] = []
        if patched.get("observed") is None:
            patched["observed"] = {}

        # Drop condition names that are not even shaped like an id, rather
        # than failing the whole decision on them.
        #
        # Observed live 2026-09-11 against the fine-tuned adapter: asked about
        # sudden severe pelvic pain it answered EMERGENCY — the right urgency —
        # and attached ``["appendicitis", "tubal pregnancy", "ovarian cyst
        # torsion", "ovarian-cyst rupture", "bowel obstruction"]``. Three of
        # those contain spaces or hyphens, so ``Identifier`` rejected them and
        # nine validation errors sank the entire turn. The user got a 502 and
        # no urgency at all.
        #
        # Naming conditions is explicitly optional on a CONCLUDE (see
        # ``matching_conditions`` below), while the action code is the
        # safety-critical part. Throwing away an unusable *name* and keeping a
        # correct EMERGENCY is strictly better than discarding both, and it is
        # the same direction as every other tie-break in this project: prefer
        # the outcome that still gets her to care.
        #
        # This only removes the malformed ones. An id that is well-shaped but
        # not a real condition still reaches
        # ``herhealth_backend.triage.provenance.drop_unknown_conditions``,
        # which has the knowledge base to check it against; this package does
        # not.
        raw_conditions = patched.get("matching_conditions")
        if isinstance(raw_conditions, list):
            patched["matching_conditions"] = [
                condition
                for condition in raw_conditions
                if isinstance(condition, str) and _IDENTIFIER_SHAPE.fullmatch(condition.strip())
            ]
        # An INFORM that put its answer in `rationale` and left
        # `answer_text` empty is recoverable, so recover it rather than losing
        # the turn. Same trade as `matching_conditions` above and as
        # `clients._drop_conditions_named_beside_a_red_flag`: a model that has
        # found the right shape and filled the wrong field of it is one
        # correction away, and a corrective retry costs a whole extra
        # generation (89-104s measured on this route). The text is then
        # duplicated across both fields, which the UI tolerates — it renders
        # `answer_text` and shows `rationale` only behind the reasoning
        # disclosure — and which is strictly better than a 502.
        if patched.get("type") == DecisionType.INFORM.value and not patched.get("answer_text"):
            promoted = patched.get("rationale")
            if isinstance(promoted, str) and promoted.strip():
                patched["answer_text"] = promoted

        raw_citations = patched.get("citations")
        if isinstance(raw_citations, list):
            patched["citations"] = [
                _PASSAGE_ID_PREFIX.sub("", citation.strip())
                if isinstance(citation, str)
                else citation
                for citation in raw_citations
            ]
        return patched

    @model_validator(mode="after")
    def _shape_matches_type(self) -> Self:
        if self.type is DecisionType.DECLINE:
            # Every other field is forbidden, so a decline cannot smuggle an
            # urgency level or a citation in alongside the refusal — see the
            # class docstring for the live case that made this necessary.
            # Named individually in the error because clients.py feeds it
            # back to the model verbatim on retry.
            forbidden = {
                "next_feature_id": self.next_feature_id,
                "question_text": self.question_text,
                "action_code": self.action_code,
                "red_flag_id": self.red_flag_id,
                "matching_conditions": self.matching_conditions or None,
                "citations": self.citations or None,
                # An off-scope message tells us nothing about her health.
                # Recording a feature value from one would put a symptom in
                # the case vector that she never reported, about a topic this
                # system does not cover — and every later turn's red-flag
                # evaluation and evidence join would then read from it.
                "observed": dict(self.observed) or None,
            }
            carried = sorted(name for name, value in forbidden.items() if value is not None)
            if carried:
                raise ValueError(
                    f"a DECLINE decision must not carry {', '.join(carried)} — it "
                    "assigns no urgency and asserts nothing about her health, so "
                    "there is nothing for a citation to support"
                )
            return self

        if self.type is DecisionType.INFORM:
            # The backstop behind the promotion in `_coerce_null_collections`,
            # not a path a model reaches: `rationale` is itself required, so
            # an INFORM arriving without `answer_text` has its rationale
            # promoted before this runs. Kept because every consumer renders
            # and asserts on `answer_text`, so the invariant has to be stated
            # where it is enforced, and it would come back into play the
            # moment that promotion is narrowed.
            if self.answer_text is None:
                raise ValueError(
                    "an INFORM decision requires answer_text — the answer she reads"
                )
            # Stricter than the general grounding rule below, deliberately: a
            # red flag is grounds to escalate, never grounds to explain, so
            # there is no red_flag_id route to satisfying this. An INFORM
            # reports what our sources say about a topic, so it has to name
            # the passages it read that in.
            if not self.citations:
                raise ValueError(
                    "an INFORM decision must cite at least one retrieved passage — "
                    "it reports what our sources say about a topic, so an uncited "
                    "one is indistinguishable from an invented one, and unlike an "
                    "ASK or a CONCLUDE it has no red_flag_id route to grounding"
                )
            forbidden = {
                "next_feature_id": self.next_feature_id,
                "question_text": self.question_text,
                # No urgency level, so an informational answer can never
                # double as reassurance.
                "action_code": self.action_code,
                # A noticed warning sign must escalate, not explain.
                "red_flag_id": self.red_flag_id,
                # Nothing was matched against her — she described no case.
                "matching_conditions": self.matching_conditions or None,
            }
            carried = sorted(name for name, value in forbidden.items() if value is not None)
            if carried:
                raise ValueError(
                    f"an INFORM decision must not carry {', '.join(carried)} — it "
                    "answers a question about a topic, assigns no urgency, and "
                    "asserts nothing about her own case"
                )
            return self

        if self.answer_text is not None:
            raise ValueError(
                "answer_text is only legal on an INFORM decision, not a "
                f"{self.type.value.upper()} — an ask carries question_text and a "
                "conclude carries rationale"
            )

        # A clarifying question is exempt (ADR 0018, 2026-10-12). It asserts
        # nothing about her, and its feature must be a real one from
        # features.yaml, which the closed-vocabulary check enforces. A
        # conclusion still has to be grounded: it is the reply that tells her
        # how urgently to seek care.
        if (
            self.type is not DecisionType.ASK
            and not self.citations
            and self.red_flag_id is None
        ):
            raise ValueError(
                "a decision must be grounded in at least one citation or a red_flag_id"
            )

        if self.type is DecisionType.ASK:
            if self.next_feature_id is None or self.question_text is None:
                raise ValueError(
                    "an ASK decision requires both next_feature_id and question_text"
                )
            if self.action_code is not None:
                raise ValueError("an ASK decision must not carry an action_code")
            if self.matching_conditions:
                raise ValueError("an ASK decision must not carry matching_conditions")
        elif self.type is DecisionType.CONCLUDE:
            if self.action_code is None:
                raise ValueError("a CONCLUDE decision requires action_code")
            if self.next_feature_id is not None or self.question_text is not None:
                raise ValueError(
                    "a CONCLUDE decision must not carry next_feature_id or question_text"
                )

        # ADR 0013: EMERGENCY alone. Widened to URGENT_SAME_DAY on 2026-09-17
        # and narrowed back on 2026-10-19, on the product owner's decision, so
        # the code again matches ADR 0013 and CLAUDE.md: a same-day warning
        # sign escalates on the symptom without naming what it may be, the
        # discipline that keeps cancer unnamed.
        #
        # At EMERGENCY this is still "may match patterns our sources
        # associate with…", never "you have…", and the closed vocabulary still
        # cannot produce a condition that is not in conditions.yaml.
        urgent_exception = self.action_code is ActionCode.EMERGENCY
        if self.red_flag_id is not None and self.matching_conditions and not urgent_exception:
            raise ValueError(
                "a red-flag-driven decision must not name matching_conditions — "
                "red flags escalate on a symptom pattern without asserting what "
                "it is, the same discipline CLAUDE.md already applies to cancer "
                "(EMERGENCY is the one deliberate exception to this — see the "
                "class docstring)"
            )
        return self
