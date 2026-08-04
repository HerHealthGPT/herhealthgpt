"""Load the seven knowledge files into a :class:`KnowledgeBase`.

Lives in contracts rather than in a service because both services need it: the
data service validates the files, and the backend reasons over them. The import
rule says a thing two services need belongs here, and this is that thing.

**Strict on purpose.** Anything wrong raises. That suits a runtime caller — a
controller must not start against a knowledge base it could not fully parse, and
a half-loaded differential is more dangerous than no differential.

``services/data`` keeps its own lenient loader for ``make validate``, which has
the opposite requirement: it must survive every fault in order to report them
all at once with file and row context. Two loaders, because "fail on the first
problem" and "collect every problem" are genuinely different jobs, and collapsing
them would make one of them worse.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml
from pydantic import BaseModel

from herhealth_contracts.knowledge import (
    Actions,
    ConditionsFile,
    EvidenceRow,
    FeaturesFile,
    KnowledgeBase,
    RedFlagsFile,
    SourcesFile,
    Weights,
)

__all__ = ["KNOWLEDGE_FILENAMES", "load_knowledge_base"]

KNOWLEDGE_FILENAMES: tuple[str, ...] = (
    "features.yaml",
    "conditions.yaml",
    "evidence.csv",
    "red_flags.yaml",
    "sources.yaml",
    "weights.yaml",
    "actions.yaml",
)


def _yaml[Model: BaseModel](path: Path, model: type[Model]) -> Model:
    """Parse one YAML file into its model.

    ``model_validate`` rather than ``Model(**payload)``: the payload is
    ``dict[str, object]`` until validation says otherwise, so splatting it
    cannot type-check, and mypy runs strict here.
    """
    if not path.is_file():
        raise FileNotFoundError(f"knowledge file missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} did not parse to a mapping")
    return model.model_validate(payload)


def _evidence(path: Path) -> tuple[EvidenceRow, ...]:
    """Parse the evidence grid.

    Empty cells are dropped rather than passed as ``""`` so that an optional
    column left blank falls back to its default instead of failing the
    non-empty-string constraints the schema puts on provenance.
    """
    if not path.is_file():
        raise FileNotFoundError(f"knowledge file missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return tuple(
            EvidenceRow.model_validate(
                {k: v for k, v in record.items() if v not in (None, "")}
            )
            for record in csv.DictReader(handle)
        )


def load_knowledge_base(directory: Path) -> KnowledgeBase:
    """Parse every file, or raise.

    Raises ``FileNotFoundError`` for a missing file, ``ValidationError`` for a
    schema fault, and ``ValueError`` for malformed YAML.
    """
    features = _yaml(directory / "features.yaml", FeaturesFile)
    conditions = _yaml(directory / "conditions.yaml", ConditionsFile)
    red_flags = _yaml(directory / "red_flags.yaml", RedFlagsFile)
    sources = _yaml(directory / "sources.yaml", SourcesFile)
    weights = _yaml(directory / "weights.yaml", Weights)
    actions = _yaml(directory / "actions.yaml", Actions)

    return KnowledgeBase(
        features=features.features,
        conditions=conditions.conditions,
        evidence=_evidence(directory / "evidence.csv"),
        red_flags=red_flags.red_flags,
        sources=sources.sources,
        weights=weights,
        actions=actions,
    )
