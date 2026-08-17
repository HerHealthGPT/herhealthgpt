"""Schemas for the evaluation set.

In contracts because both sides need them: ``services/data`` converts the
benchmark and validates the result, ``services/backend`` runs the cases through
the controller.

**The central design choice: a variant cannot carry a label.**

A canonical case holds the labels. A variant holds only text, a register style
and a language. There is no field on ``CaseVariant`` for an expected action, so
the six registers and three languages of one case cannot disagree about what the
right answer is — not because a test checks, but because there is nowhere to
write a second opinion.

That is deliberate and it is the fix for a specific past failure. Deriving risk
labels by running English keyword rules over translated text produced
language-asymmetric labels skewed toward routine — French and Arabic came out
systematically less urgent than the same case in English. Labels are derived
**once**, from the English source, and reached everywhere else through
``canonical_case_id``. Here that is structural rather than procedural.

Labels are **silver**: derived by reading the benchmark's own reference answer,
not adjudicated by a clinician. Say so wherever results are reported.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from herhealth_contracts.knowledge import (
    ActionCode,
    FeatureValue,
    Identifier,
    NonEmptyText,
)

__all__ = [
    "CanonicalCase",
    "CaseLabel",
    "CaseVariant",
    "EvaluationSet",
    "Language",
    "RegisterStyle",
]


class RegisterStyle(StrEnum):
    """How the same question is phrased.

    The benchmark carries six matched variants per case. ``AMBIGUOUS`` is the
    one with a job beyond robustness: it is the register where a good system
    should ask a clarifying question rather than answer, so it drives
    clarification recall.
    """

    CANONICAL = "canonical"
    CLINICAL = "clinical"
    LAYPERSON = "layperson"
    INDIRECT_CULTURAL = "indirect_cultural"
    AMBIGUOUS = "ambiguous"
    EMOTIONALLY_CONCERNED = "emotionally_concerned"


class Language(StrEnum):
    """``ar`` is Modern Standard; ``ar_eg`` is Egyptian, where the users are."""

    EN = "en"
    FR = "fr"
    AR = "ar"
    AR_EG = "ar_eg"


#: The sentence in the benchmark's reference answer that the label was read
#: from. Same role as ``source_quote`` on a clinical row: it makes the label a
#: restatement of something the source says rather than our own judgement, and
#: it is what a second reader checks.
LabelQuote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _EvaluationModel(BaseModel):
    """Same config as the knowledge models, for the same reasons — see
    ``knowledge._KnowledgeModel``."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CaseLabel(_EvaluationModel):
    """What the right answer is, and the sentence that says so."""

    expected_action: ActionCode

    #: True when the correct behaviour is to ask rather than conclude. Drives
    #: clarification recall, which collapsed to 0.000 under fine-tuning and is
    #: therefore gated.
    needs_clarification: bool = False

    #: Set when a specific rule must fire. Red-flag recall is checked against
    #: the named rule, not merely against "something escalated", so a rule
    #: firing for the wrong reason still counts as a miss.
    expected_red_flag_id: str = ""

    label_quote: LabelQuote

    note: str = ""

    @model_validator(mode="after")
    def _a_named_red_flag_must_escalate(self) -> Self:
        if self.expected_red_flag_id and self.expected_action is ActionCode.SELF_CARE:
            raise ValueError(
                f"{self.expected_red_flag_id!r} is expected to fire, but the "
                "expected action is SELF_CARE; a red flag only escalates"
            )
        return self


class CanonicalCase(_EvaluationModel):
    """One case, in the form the controller can actually consume.

    ``features`` is the annotation that makes a prose question runnable: the
    engine takes feature values, not sentences. Turning text into feature values
    is the model's job at serving time, and it is a human's job here — which is
    what lets the controller be evaluated before any model exists.
    """

    id: Identifier
    topic: NonEmptyText

    #: feature_id -> value. Validated against the knowledge base by the loader,
    #: which is where the feature vocabulary is known.
    features: dict[Identifier, FeatureValue] = Field(default_factory=dict)

    label: CaseLabel

    #: False when the case probes something deliberately not modelled —
    #: pregnancy-related bleeding, for instance, which has no usable sources.
    #: Excluded from scoring and **counted in the report**: a gap we chose is
    #: not the same as a gap we missed, and hiding it would misstate both.
    in_scope: bool = True
    out_of_scope_reason: str = ""

    @model_validator(mode="after")
    def _out_of_scope_needs_a_reason(self) -> Self:
        if not self.in_scope and not self.out_of_scope_reason.strip():
            raise ValueError(
                f"{self.id!r} is marked out of scope without a reason; say which "
                "modelling decision puts it there so the exclusion can be reviewed"
            )
        if self.in_scope and self.out_of_scope_reason.strip():
            raise ValueError(
                f"{self.id!r} is in scope but carries an out_of_scope_reason; "
                "remove it so it is not mistaken for an exclusion"
            )
        return self


class CaseVariant(_EvaluationModel):
    """One phrasing of one case, in one language.

    **There is deliberately no label field here.** See the module docstring: a
    variant that could carry its own expected action is a variant that could
    disagree with its canonical case, and that disagreement is exactly the bug
    this schema exists to make unrepresentable.
    """

    canonical_case_id: Identifier
    style: RegisterStyle
    language: Language
    text: NonEmptyText


class EvaluationSet(_EvaluationModel):
    """Every case and every variant, loaded together."""

    cases: tuple[CanonicalCase, ...]
    variants: tuple[CaseVariant, ...] = ()

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Self:
        ids = [case.id for case in self.cases]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate canonical case ids: {', '.join(duplicates)}")
        return self

    @model_validator(mode="after")
    def _every_variant_resolves(self) -> Self:
        known = {case.id for case in self.cases}
        orphans = sorted({v.canonical_case_id for v in self.variants} - known)
        if orphans:
            raise ValueError(
                "variants refer to unknown canonical cases: "
                f"{', '.join(orphans[:5])}. A variant with no case has no label, "
                "so it can never be scored"
            )
        return self

    @model_validator(mode="after")
    def _no_duplicate_variants(self) -> Self:
        keys = [(v.canonical_case_id, v.style, v.language) for v in self.variants]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            shown = "; ".join(f"({a}, {b}, {c})" for a, b, c in duplicates[:5])
            raise ValueError(f"duplicate (case, style, language) variants: {shown}")
        return self

    @property
    def cases_by_id(self) -> dict[str, CanonicalCase]:
        return {case.id: case for case in self.cases}

    @property
    def scored(self) -> tuple[CanonicalCase, ...]:
        """The in-scope cases. Everything else is reported, never silently cut."""
        return tuple(case for case in self.cases if case.in_scope)

    @property
    def languages(self) -> tuple[Language, ...]:
        return tuple(sorted({v.language for v in self.variants}))
