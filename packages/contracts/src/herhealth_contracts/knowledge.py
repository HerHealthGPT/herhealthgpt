"""Schemas for the seven knowledge files.

These are the single definition. The YAML and CSV under ``knowledge/`` validate
against them, and where the two disagree the file is wrong.

Verification protocol
---------------------
This project has no clinician reviewer, which is a resource constraint rather
than an oversight, and it changes what the knowledge base is allowed to contain.
Every row must be a restatement of something a cited source says; no row may be
an independent clinical judgement. So every clinical row carries a ``source_id``
and a ``source_quote`` holding the sentence or clause it was derived from, and a
row that cannot be traced to a specific sentence is deleted rather than softened.

Source traceability is what stands in for review. There is deliberately no
``reviewed_by_clinician`` field, nor any flag resembling one, because such a
field could only ever hold a value we are not in a position to assert.

Safety invariants encoded here rather than left to convention:

* ``neutral`` is rejected on an evidence row — it means omit the row.
* A red-flag rule may only escalate; de-escalating rules are unconstructible.
* ``Weights`` enforces a strictly higher bar for concluding ``SELF_CARE`` than
  ``ROUTINE_APPOINTMENT``, because under-triage is the dominant failure mode.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

__all__ = [
    "ActionCode",
    "ActionDefinition",
    "Actions",
    "Clause",
    "ComparisonOp",
    "Condition",
    "ConditionsFile",
    "EvidenceRow",
    "EvidenceStrength",
    "Feature",
    "FeatureKind",
    "FeaturesFile",
    "KnowledgeBase",
    "RedFlagRule",
    "RedFlagsFile",
    "Source",
    "SourcesFile",
    "Weights",
]


# --------------------------------------------------------------------------
# Fixed vocabularies
# --------------------------------------------------------------------------


class EvidenceStrength(StrEnum):
    """The five-level ordinal scale, and nothing else.

    Deliberately not probabilities. No likelihood ratios, prevalence figures or
    confidence scores appear anywhere in the knowledge base.
    """

    STRONG_SUPPORT = "strong_support"
    WEAK_SUPPORT = "weak_support"
    NEUTRAL = "neutral"
    ARGUES_AGAINST = "argues_against"
    RULES_OUT = "rules_out"


class ActionCode(StrEnum):
    """The four urgency actions, and nothing else.

    Locale-specific instructions ("call 111", "see your GP") are never stored.
    Source content is UK and US; users are in Egypt. These codes are resolved
    per locale at response time, which is what lets one knowledge base serve
    more than one healthcare system.
    """

    SELF_CARE = "SELF_CARE"
    ROUTINE_APPOINTMENT = "ROUTINE_APPOINTMENT"
    URGENT_SAME_DAY = "URGENT_SAME_DAY"
    EMERGENCY = "EMERGENCY"


class FeatureKind(StrEnum):
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    NUMERIC = "numeric"


class ComparisonOp(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    GTE = "gte"
    LTE = "lte"


#: Increasing urgency. `next_question` and `should_stop` rely on this order.
CANONICAL_ACTION_ORDER: Final[tuple[ActionCode, ...]] = (
    ActionCode.SELF_CARE,
    ActionCode.ROUTINE_APPOINTMENT,
    ActionCode.URGENT_SAME_DAY,
    ActionCode.EMERGENCY,
)

#: Only a red flag may escalate to these; nothing else short-circuits the flow.
ESCALATING_ACTIONS: Final[frozenset[ActionCode]] = frozenset(
    {ActionCode.URGENT_SAME_DAY, ActionCode.EMERGENCY}
)

#: Reserved. Every feature implicitly accepts it, meaning "the user did not say".
#: It carries no weight, so it must never be listed in ``allowed_values``.
UNKNOWN_VALUE: Final[str] = "unknown"

#: Placeholder until the WHO ICD API resolves the real identifier. Codes recalled
#: from training data are unreliable and are never written by hand.
ICD_UNVERIFIED: Final[str] = "TODO_VERIFY"

#: The only probe language authored in the current phase.
DEFAULT_PROBE_LANGUAGE: Final[str] = "en"


# --------------------------------------------------------------------------
# Constrained primitives
# --------------------------------------------------------------------------

Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]*$"),
]

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

#: The sentence or clause the row was derived from. Required, and non-empty
#: after stripping, so whitespace cannot masquerade as provenance.
SourceQuote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

#: Feature values are lowercase tokens, not free text, so that membership in
#: ``allowed_values`` is checkable.
FeatureValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9][a-z0-9_]*$"),
]

#: Ordinal strength to log-odds contribution.
LogOdds = dict[EvidenceStrength, float]


class _KnowledgeModel(BaseModel):
    """Base config for every knowledge model.

    ``extra="forbid"`` turns a typo'd column in a hand-edited CSV into a load
    failure instead of a silently dropped field. ``frozen=True`` because the
    knowledge base is read-only once loaded.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


# --------------------------------------------------------------------------
# features.yaml
# --------------------------------------------------------------------------


class Feature(_KnowledgeModel):
    """Something the system may ask about."""

    id: Identifier
    label: NonEmptyText
    kind: FeatureKind
    allowed_values: tuple[FeatureValue, ...] = ()

    #: How intrusive or effortful the question is, 1 (trivial) to 5 (sensitive
    #: or burdensome). ``next_question`` ranks by separation per unit of burden,
    #: so this is what stops the system asking the most invasive question first.
    burden: int = Field(ge=1, le=5)

    #: Keyed by language code. Only ``en`` is authored in the current phase; the
    #: serving model renders other languages at response time. The mapping shape
    #: is what lets authored ``fr`` / ``ar_eg`` probes land later without a
    #: schema migration.
    probe: dict[str, NonEmptyText]

    note: str = ""

    @field_validator("probe")
    @classmethod
    def _require_english_probe(cls, value: dict[str, str]) -> dict[str, str]:
        if DEFAULT_PROBE_LANGUAGE not in value:
            raise ValueError(f"probe must include a {DEFAULT_PROBE_LANGUAGE!r} key")
        return value

    @model_validator(mode="after")
    def _check_allowed_values(self) -> Self:
        if UNKNOWN_VALUE in self.allowed_values:
            raise ValueError(
                f"{UNKNOWN_VALUE!r} is implicit on every feature and carries no "
                "weight; remove it from allowed_values"
            )
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("allowed_values contains duplicates")

        if self.kind is FeatureKind.NUMERIC:
            if self.allowed_values:
                raise ValueError("a numeric feature must not enumerate allowed_values")
        elif not self.allowed_values:
            raise ValueError(f"a {self.kind} feature must enumerate allowed_values")

        if self.kind is FeatureKind.BOOLEAN and set(self.allowed_values) != {"yes", "no"}:
            raise ValueError("a boolean feature must allow exactly 'yes' and 'no'")
        return self


class FeaturesFile(_KnowledgeModel):
    features: tuple[Feature, ...]

    @field_validator("features")
    @classmethod
    def _unique_ids(cls, value: tuple[Feature, ...]) -> tuple[Feature, ...]:
        _reject_duplicates([f.id for f in value], "feature id")
        return value


# --------------------------------------------------------------------------
# conditions.yaml
# --------------------------------------------------------------------------


class Condition(_KnowledgeModel):
    """Something the system may consider as an explanation.

    Considering a condition is not asserting one. The output is an urgency
    action and cited information, never a conclusion about what a user has.
    """

    id: Identifier
    label: NonEmptyText

    #: Left as ``TODO_VERIFY`` until resolved through the WHO ICD API.
    icd11: str = ICD_UNVERIFIED

    #: The action this condition implies on its own, before evidence moves it.
    baseline_action: ActionCode

    #: At least two, so no condition rests on a single document.
    source_ids: tuple[Identifier, ...] = Field(min_length=2)

    note: str = ""

    @field_validator("source_ids")
    @classmethod
    def _unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _reject_duplicates(list(value), "source_id")
        return value


class ConditionsFile(_KnowledgeModel):
    conditions: tuple[Condition, ...]

    @field_validator("conditions")
    @classmethod
    def _unique_ids(cls, value: tuple[Condition, ...]) -> tuple[Condition, ...]:
        _reject_duplicates([c.id for c in value], "condition id")
        return value


# --------------------------------------------------------------------------
# evidence.csv
# --------------------------------------------------------------------------


class EvidenceRow(_KnowledgeModel):
    """One cell of the sparse grid connecting a feature value to a condition."""

    condition_id: Identifier
    feature_id: Identifier
    value: FeatureValue
    strength: EvidenceStrength

    source_id: Identifier

    #: The sentence the row restates. Required and non-empty: a row that cannot
    #: be traced to specific source text is deleted, not softened.
    source_quote: SourceQuote

    #: Why, when the row is not self-explanatory. Where a judgement traded false
    #: alarms against missed escalations, record the choice here.
    note: str = ""

    @field_validator("strength")
    @classmethod
    def _reject_neutral(cls, value: EvidenceStrength) -> EvidenceStrength:
        if value is EvidenceStrength.NEUTRAL:
            raise ValueError(
                "'neutral' is expressed by omitting the row; evidence.csv is sparse"
            )
        return value


# --------------------------------------------------------------------------
# red_flags.yaml
# --------------------------------------------------------------------------


class Clause(_KnowledgeModel):
    """One condition in a red-flag rule. Deterministic, no model involvement."""

    feature_id: Identifier
    op: ComparisonOp
    value: str | tuple[str, ...] | float

    @model_validator(mode="after")
    def _check_value_shape(self) -> Self:
        if self.op is ComparisonOp.IN:
            if not isinstance(self.value, tuple) or not self.value:
                raise ValueError("op 'in' requires a non-empty list of values")
        elif self.op in {ComparisonOp.GTE, ComparisonOp.LTE}:
            if not isinstance(self.value, float | int):
                raise ValueError(f"op {self.op!r} requires a numeric value")
        elif not isinstance(self.value, str):
            raise ValueError(f"op {self.op!r} requires a single string value")
        return self


class RedFlagRule(_KnowledgeModel):
    """A deterministic escalation rule, evaluated before any model call.

    Derived only from explicit escalation language in a source — "seek immediate
    care", "call 999", "go to the emergency room". Never inferred, because an
    inferred escalation rule is an independent clinical judgement and this
    project is not in a position to make one.
    """

    id: Identifier
    label: NonEmptyText

    #: All clauses must match for the rule to fire. Conjunction only: an "or"
    #: is two rules, which keeps each rule traceable to its own source quote.
    all_of: tuple[Clause, ...] = Field(min_length=1)

    #: Escalation only. A red flag that de-escalates is unconstructible.
    action: ActionCode

    source_id: Identifier
    source_quote: SourceQuote
    note: str = ""

    @field_validator("action")
    @classmethod
    def _must_escalate(cls, value: ActionCode) -> ActionCode:
        if value not in ESCALATING_ACTIONS:
            allowed = ", ".join(sorted(a.value for a in ESCALATING_ACTIONS))
            raise ValueError(f"a red flag may only escalate; action must be one of: {allowed}")
        return value


class RedFlagsFile(_KnowledgeModel):
    red_flags: tuple[RedFlagRule, ...]

    @field_validator("red_flags")
    @classmethod
    def _unique_ids(cls, value: tuple[RedFlagRule, ...]) -> tuple[RedFlagRule, ...]:
        _reject_duplicates([r.id for r in value], "red flag id")
        return value


# --------------------------------------------------------------------------
# sources.yaml
# --------------------------------------------------------------------------


class Source(_KnowledgeModel):
    """A document set that rows may cite."""

    id: Identifier
    name: NonEmptyText
    url: HttpUrl

    #: Lower wins on conflict. Never resolve a conflict silently — the losing
    #: claim is appended to build/conflicts.jsonl.
    precedence: int = Field(ge=1)

    #: Recorded per source. UMLS stores concept identifiers only, never strings.
    licence: NonEmptyText

    #: How the content is obtained: bulk XML, page ingestion, REST, and so on.
    access: NonEmptyText

    note: str = ""


class SourcesFile(_KnowledgeModel):
    sources: tuple[Source, ...]

    @field_validator("sources")
    @classmethod
    def _unique_ids(cls, value: tuple[Source, ...]) -> tuple[Source, ...]:
        _reject_duplicates([s.id for s in value], "source id")
        return value


# --------------------------------------------------------------------------
# weights.yaml
# --------------------------------------------------------------------------


class Weights(_KnowledgeModel):
    """Tunable constants. Set by us, tuned against the evaluation set.

    None of these are measured quantities. They are the knobs that convert the
    ordinal evidence scale into something a controller can add up, and they are
    expected to move once there are evaluation numbers to move them against.
    """

    #: Ordinal strength to log-odds. All five keys required; neutral pinned to 0.
    log_odds: LogOdds

    #: Below this, a condition is no longer live and stops driving questions.
    plausibility_floor: float

    #: Stopping bar for ROUTINE_APPOINTMENT, URGENT_SAME_DAY and EMERGENCY.
    stop_confidence: float

    #: Stopping bar for SELF_CARE. Strictly higher, enforced below. Concluding
    #: "nothing to do" is the conclusion most costly to get wrong.
    self_care_stop_confidence: float

    #: How far clear of the runner-up the top condition must be.
    stop_margin: float = Field(ge=0.0)

    #: Hard ceiling on questions asked before stopping with the differential.
    max_questions: int = Field(default=6, ge=1)

    note: str = ""

    @field_validator("log_odds")
    @classmethod
    def _all_five_present(cls, value: LogOdds) -> LogOdds:
        missing = set(EvidenceStrength) - set(value)
        if missing:
            names = ", ".join(sorted(s.value for s in missing))
            raise ValueError(f"log_odds is missing: {names}")
        if value[EvidenceStrength.NEUTRAL] != 0.0:
            raise ValueError("neutral must map to 0.0; it is the absence of evidence")
        return value

    @model_validator(mode="after")
    def _check_ordering(self) -> Self:
        w = self.log_odds
        ordered = (
            w[EvidenceStrength.STRONG_SUPPORT]
            > w[EvidenceStrength.WEAK_SUPPORT]
            > 0.0
            > w[EvidenceStrength.ARGUES_AGAINST]
            > w[EvidenceStrength.RULES_OUT]
        )
        if not ordered:
            raise ValueError(
                "log_odds must be monotonic: strong_support > weak_support > 0 "
                "> argues_against > rules_out"
            )
        if self.self_care_stop_confidence <= self.stop_confidence:
            raise ValueError(
                "self_care_stop_confidence must be strictly greater than "
                "stop_confidence; under-triage is the dominant failure mode"
            )
        return self


# --------------------------------------------------------------------------
# actions.yaml
# --------------------------------------------------------------------------


class ActionDefinition(_KnowledgeModel):
    code: ActionCode

    #: Increasing urgency. Cross-language comparison is on this, never on text.
    severity: int = Field(ge=0)

    description: NonEmptyText


class Actions(_KnowledgeModel):
    actions: tuple[ActionDefinition, ...]

    @model_validator(mode="after")
    def _check_complete_and_ordered(self) -> Self:
        seen = [a.code for a in self.actions]
        _reject_duplicates([c.value for c in seen], "action code")
        if set(seen) != set(ActionCode):
            missing = ", ".join(sorted(c.value for c in set(ActionCode) - set(seen)))
            raise ValueError(f"all four action codes must be defined; missing: {missing}")

        by_code = {a.code: a.severity for a in self.actions}
        severities = [by_code[code] for code in CANONICAL_ACTION_ORDER]
        if severities != sorted(set(severities)):
            order = " < ".join(c.value for c in CANONICAL_ACTION_ORDER)
            raise ValueError(f"severity must strictly increase in the order: {order}")
        return self


# --------------------------------------------------------------------------
# The loaded whole
# --------------------------------------------------------------------------


class KnowledgeBase(_KnowledgeModel):
    """Every knowledge file, loaded together.

    Within-model invariants are enforced here. Cross-file checks — every foreign
    key resolves, every value appears in the feature's ``allowed_values``, every
    condition cites at least two known sources — live in the validator, which
    reports all failures at once with file and row context rather than raising
    on the first.
    """

    features: tuple[Feature, ...]
    conditions: tuple[Condition, ...]
    evidence: tuple[EvidenceRow, ...]
    red_flags: tuple[RedFlagRule, ...]
    sources: tuple[Source, ...]
    weights: Weights
    actions: Actions

    @model_validator(mode="after")
    def _no_duplicate_cells(self) -> Self:
        cells = [(r.condition_id, r.feature_id, r.value) for r in self.evidence]
        duplicates = sorted({c for c in cells if cells.count(c) > 1})
        if duplicates:
            shown = "; ".join(f"({a}, {b}, {c})" for a, b, c in duplicates[:5])
            raise ValueError(f"duplicate (condition_id, feature_id, value) rows: {shown}")
        return self

    @property
    def features_by_id(self) -> dict[str, Feature]:
        return {f.id: f for f in self.features}

    @property
    def conditions_by_id(self) -> dict[str, Condition]:
        return {c.id: c for c in self.conditions}

    @property
    def sources_by_id(self) -> dict[str, Source]:
        return {s.id: s for s in self.sources}


def _reject_duplicates(values: list[str], what: str) -> None:
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise ValueError(f"duplicate {what}: {', '.join(duplicates)}")
