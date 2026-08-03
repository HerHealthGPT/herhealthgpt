"""Load and validate the knowledge base.

This is what `make validate` runs, and it is the reproducible form of every
check that would otherwise be done by hand.

Two stages, deliberately separate:

**Loading** parses each file against its schema in ``herhealth_contracts``.
Anything expressible in a single file is caught here — an unknown evidence
strength, a `neutral` row, a red flag that de-escalates, a `SELF_CARE` bar below
the routine bar, a missing `source_quote`.

**Checking** covers what no single file can see: every foreign key resolves,
every value appears in its feature's ``allowed_values``, no row cites a source we
are not licensed to quote, and no feature is dead weight.

Every problem is collected rather than raised, so one run reports everything
wrong instead of stopping at the first fault. Warnings do not fail the build;
errors do.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

import yaml
from herhealth_contracts.knowledge import (
    UNKNOWN_VALUE,
    Actions,
    ComparisonOp,
    ConditionsFile,
    EvidenceRow,
    FeaturesFile,
    KnowledgeBase,
    RedFlagsFile,
    SourcesFile,
    Weights,
)
from pydantic import ValidationError

__all__ = [
    "KNOWLEDGE_FILES",
    "Problem",
    "Severity",
    "check_knowledge_base",
    "load_knowledge_base",
    "validate_directory",
]


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Problem:
    """One thing wrong, located precisely enough to fix without searching."""

    severity: Severity
    file: str
    location: str
    message: str

    def __str__(self) -> str:
        where = f"{self.file}:{self.location}" if self.location else self.file
        return f"{self.severity.value.upper():<7} {where}\n        {self.message}"


#: The seven files, and the model each validates against.
KNOWLEDGE_FILES: Final[tuple[str, ...]] = (
    "features.yaml",
    "conditions.yaml",
    "evidence.csv",
    "red_flags.yaml",
    "sources.yaml",
    "weights.yaml",
    "actions.yaml",
)

#: Only English probes are authored in the current phase. This is phase policy
#: rather than a schema rule: the schema permits other languages so they can be
#: added later without a migration, and this check is what will be relaxed.
ALLOWED_PROBE_LANGUAGES: Final[frozenset[str]] = frozenset({"en"})


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_knowledge_base(directory: Path) -> tuple[KnowledgeBase | None, list[Problem]]:
    """Parse every file against its schema.

    Returns the knowledge base, or None if anything failed to parse, plus every
    problem found. A None return with an empty problem list is impossible.
    """
    problems: list[Problem] = []

    features = _load_yaml(directory / "features.yaml", FeaturesFile, problems)
    conditions = _load_yaml(directory / "conditions.yaml", ConditionsFile, problems)
    red_flags = _load_yaml(directory / "red_flags.yaml", RedFlagsFile, problems)
    sources = _load_yaml(directory / "sources.yaml", SourcesFile, problems)
    weights = _load_yaml(directory / "weights.yaml", Weights, problems)
    actions = _load_yaml(directory / "actions.yaml", Actions, problems)
    evidence = _load_evidence(directory / "evidence.csv", problems)

    if None in (features, conditions, red_flags, sources, weights, actions) or evidence is None:
        return None, problems

    assert features and conditions and red_flags and sources and weights and actions
    try:
        base = KnowledgeBase(
            features=features.features,
            conditions=conditions.conditions,
            evidence=tuple(evidence),
            red_flags=red_flags.red_flags,
            sources=sources.sources,
            weights=weights,
            actions=actions,
        )
    except ValidationError as error:
        problems.extend(_from_validation_error(error, "knowledge base"))
        return None, problems

    return base, problems


def _load_yaml(path: Path, model: type, problems: list[Problem]) -> object | None:
    if not path.is_file():
        problems.append(Problem(Severity.ERROR, path.name, "", "file is missing"))
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        problems.append(Problem(Severity.ERROR, path.name, "", f"not valid YAML: {error}"))
        return None
    if payload is None:
        problems.append(Problem(Severity.ERROR, path.name, "", "file is empty"))
        return None
    try:
        return model(**payload)
    except ValidationError as error:
        problems.extend(_from_validation_error(error, path.name))
        return None


def _load_evidence(path: Path, problems: list[Problem]) -> list[EvidenceRow] | None:
    """Parse evidence.csv. An empty file with only a header is valid."""
    if not path.is_file():
        problems.append(Problem(Severity.ERROR, path.name, "", "file is missing"))
        return None

    rows: list[EvidenceRow] = []
    failed = False
    with path.open(encoding="utf-8", newline="") as handle:
        for number, record in enumerate(csv.DictReader(handle), start=2):
            cleaned = {k: v for k, v in record.items() if v not in (None, "")}
            try:
                rows.append(EvidenceRow(**cleaned))
            except ValidationError as error:
                failed = True
                problems.extend(_from_validation_error(error, path.name, f"row {number}"))
    return None if failed else rows


def _from_validation_error(
    error: ValidationError, file: str, location: str = ""
) -> list[Problem]:
    problems = []
    for detail in error.errors():
        field = ".".join(str(part) for part in detail["loc"])
        where = f"{location} {field}".strip() if location else field
        problems.append(Problem(Severity.ERROR, file, where, detail["msg"]))
    return problems


# --------------------------------------------------------------------------
# Cross-file checks
# --------------------------------------------------------------------------


def check_knowledge_base(base: KnowledgeBase) -> list[Problem]:
    """Everything no single file can see."""
    problems: list[Problem] = []
    problems += _check_evidence(base)
    problems += _check_red_flags(base)
    problems += _check_conditions(base)
    problems += _check_probe_languages(base)
    problems += _check_nothing_is_dead_weight(base)
    return problems


def _check_evidence(base: KnowledgeBase) -> list[Problem]:
    problems: list[Problem] = []
    features, conditions, sources = base.features_by_id, base.conditions_by_id, base.sources_by_id

    for row in base.evidence:
        where = f"{row.condition_id}/{row.feature_id}={row.value}"

        if row.condition_id not in conditions:
            problems.append(_unknown("evidence.csv", where, "condition_id", row.condition_id))
        if row.source_id not in sources:
            problems.append(_unknown("evidence.csv", where, "source_id", row.source_id))
        elif not sources[row.source_id].may_be_cited:
            problems.append(
                Problem(
                    Severity.ERROR,
                    "evidence.csv",
                    where,
                    f"cites {row.source_id!r}, whose licence does not permit quoting "
                    f"(status: {sources[row.source_id].status.value})",
                )
            )

        feature = features.get(row.feature_id)
        if feature is None:
            problems.append(_unknown("evidence.csv", where, "feature_id", row.feature_id))
        else:
            problems += _check_value(feature, row.value, "evidence.csv", where)

    return problems


def _check_red_flags(base: KnowledgeBase) -> list[Problem]:
    problems: list[Problem] = []
    features, sources = base.features_by_id, base.sources_by_id

    for rule in base.red_flags:
        if rule.source_id not in sources:
            problems.append(_unknown("red_flags.yaml", rule.id, "source_id", rule.source_id))
        elif not sources[rule.source_id].may_be_cited:
            problems.append(
                Problem(
                    Severity.ERROR,
                    "red_flags.yaml",
                    rule.id,
                    f"cites {rule.source_id!r}, whose licence does not permit quoting",
                )
            )

        for clause in rule.all_of:
            feature = features.get(clause.feature_id)
            if feature is None:
                problems.append(
                    _unknown("red_flags.yaml", rule.id, "feature_id", clause.feature_id)
                )
                continue
            # Numeric comparisons are not membership tests.
            if clause.op in {ComparisonOp.GTE, ComparisonOp.LTE}:
                continue
            values = clause.value if isinstance(clause.value, tuple) else (clause.value,)
            for value in values:
                if isinstance(value, str):
                    problems += _check_value(feature, value, "red_flags.yaml", rule.id)

    return problems


def _check_conditions(base: KnowledgeBase) -> list[Problem]:
    problems: list[Problem] = []
    sources = base.sources_by_id

    for condition in base.conditions:
        for source_id in condition.source_ids:
            if source_id not in sources:
                problems.append(_unknown("conditions.yaml", condition.id, "source_id", source_id))
            elif not sources[source_id].may_be_cited:
                problems.append(
                    Problem(
                        Severity.ERROR,
                        "conditions.yaml",
                        condition.id,
                        f"cites {source_id!r}, whose licence does not permit quoting",
                    )
                )
    return problems


def _check_probe_languages(base: KnowledgeBase) -> list[Problem]:
    """Phase policy, not a schema rule — the schema allows other languages."""
    problems = []
    for feature in base.features:
        extra = sorted(set(feature.probe) - ALLOWED_PROBE_LANGUAGES)
        if extra:
            problems.append(
                Problem(
                    Severity.ERROR,
                    "features.yaml",
                    feature.id,
                    f"probe languages {extra} are not authored in this phase; "
                    "the serving model renders other languages at response time",
                )
            )
    return problems


def _check_nothing_is_dead_weight(base: KnowledgeBase) -> list[Problem]:
    """A question nobody can act on, or a condition nothing can suggest."""
    used_by_evidence = {row.feature_id for row in base.evidence}
    used_by_red_flags = {c.feature_id for rule in base.red_flags for c in rule.all_of}
    used = used_by_evidence | used_by_red_flags

    problems = [
        Problem(
            Severity.WARNING,
            "features.yaml",
            feature.id,
            "no evidence row and no red-flag clause uses this feature, so asking "
            "it can never change the outcome",
        )
        for feature in base.features
        if feature.id not in used
    ]

    suggested = {row.condition_id for row in base.evidence}
    problems += [
        Problem(
            Severity.WARNING,
            "conditions.yaml",
            condition.id,
            "no evidence row mentions this condition, so nothing can ever raise it",
        )
        for condition in base.conditions
        if condition.id not in suggested
    ]
    return problems


def _check_value(feature: object, value: str, file: str, where: str) -> list[Problem]:
    allowed = getattr(feature, "allowed_values", ())
    if value == UNKNOWN_VALUE:
        return [
            Problem(
                Severity.ERROR,
                file,
                where,
                f"{UNKNOWN_VALUE!r} is implicit on every feature and carries no weight; "
                "a row for it can never do anything",
            )
        ]
    if allowed and value not in allowed:
        return [
            Problem(
                Severity.ERROR,
                file,
                where,
                f"{value!r} is not in allowed_values for "
                f"{getattr(feature, 'id', '?')}: {list(allowed)}",
            )
        ]
    return []


def _unknown(file: str, where: str, field: str, value: str) -> Problem:
    return Problem(Severity.ERROR, file, where, f"{field} {value!r} does not resolve")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def validate_directory(directory: Path) -> list[Problem]:
    """Load and check. The whole of `make validate`."""
    base, problems = load_knowledge_base(directory)
    if base is not None:
        problems += check_knowledge_base(base)
    return problems


def errors(problems: Iterable[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity is Severity.ERROR]
