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

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from herhealth_contracts.knowledge import ActionCode, Identifier, NonEmptyText
from herhealth_contracts.retrieval import PassageId

__all__ = ["DecisionType", "TriageDecision"]


class DecisionType(StrEnum):
    """What the reasoning model chose to do this turn. Nothing else is legal."""

    ASK = "ask"
    CONCLUDE = "conclude"


class TriageDecision(BaseModel):
    """One turn's decision, emitted by the reasoning model as guided JSON.

    ``rationale`` is required on every decision, including an ``ask`` — a
    question still has to say why, from what has been seen so far, which is
    what makes the transcript auditable without a deterministic trace to fall
    back on. Every decision must also point at *something* it was grounded
    on — ``citations``, ``red_flag_id``, or both — for the same reason: a
    decision citing nothing is not distinguishable from one the model made up.

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
    But ``CLAUDE.md`` already carries one hard-won rule about naming
    conditions: cancer is deliberately unmodelled and *"served by red flags
    instead — postmenopausal bleeding routes to a GP without ever naming
    why."* Generalising that: **a decision driven by a red flag must never
    name a condition**, authored or not — the whole reason red flags exist
    is to escalate on a symptom pattern without asserting what it is. So
    ``matching_conditions`` is only legal when ``red_flag_id`` is ``None``.
    This is enforced below, not left to the prompt alone.

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

    #: Real conditions.yaml ids whose pattern the answers matched, for a
    #: CONCLUDE only, and only when red_flag_id is None — see the class
    #: docstring. Always rendered to the user as "matches patterns
    #: associated with", never as "you have". May be empty even on a
    #: qualifying CONCLUDE: naming conditions is offered, not mandatory.
    #: Capped at 5 — see the class docstring for why an uncapped list is
    #: actively unhelpful in this knowledge base, not just verbose.
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

    #: Why, in the model's own words. Logged verbatim alongside the decision.
    rationale: NonEmptyText

    @model_validator(mode="after")
    def _shape_matches_type(self) -> Self:
        if not self.citations and self.red_flag_id is None:
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
        else:
            if self.action_code is None:
                raise ValueError("a CONCLUDE decision requires action_code")
            if self.next_feature_id is not None or self.question_text is not None:
                raise ValueError(
                    "a CONCLUDE decision must not carry next_feature_id or question_text"
                )

        if self.red_flag_id is not None and self.matching_conditions:
            raise ValueError(
                "a red-flag-driven decision must not name matching_conditions — "
                "red flags escalate on a symptom pattern without asserting what "
                "it is, the same discipline CLAUDE.md already applies to cancer"
            )
        return self
