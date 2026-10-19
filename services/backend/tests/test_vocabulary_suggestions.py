"""An invented feature id is rejected with the nearest real ids named.

The invented ids are verbatim from live runs: ``difficulty_becoming_pregnant``
(2026-10-19, twice in one consultation) and ``days_between_periods``
(2026-10-12). Both are a feature's label written as an id.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.vocabulary import (
    ClosedVocabularyViolation,
    closest_features,
    validate_against_knowledge_base,
)

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def base() -> KnowledgeBase:
    return load_knowledge_base(REPO / "knowledge")


@pytest.mark.parametrize(
    ("invented", "real"),
    [
        ("difficulty_becoming_pregnant", "difficulty_conceiving"),
        ("days_between_periods", "cycle_length"),
    ],
)
def test_the_nearest_real_feature_comes_first(
    base: KnowledgeBase, invented: str, real: str
) -> None:
    assert closest_features(base, invented)[0] == real


def test_the_rejection_names_the_nearest_real_ids(base: KnowledgeBase) -> None:
    decision = TriageDecision(
        type=DecisionType.ASK,
        next_feature_id="difficulty_becoming_pregnant",
        question_text="Have you been trying to get pregnant?",
        rationale="One more detail would change the advice.",
    )
    with pytest.raises(
        ClosedVocabularyViolation, match="closest real ids are difficulty_conceiving"
    ):
        validate_against_knowledge_base(decision, base, [])
