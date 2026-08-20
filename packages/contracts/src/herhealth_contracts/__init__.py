"""Shared contracts for HerHealthGPT.

Nothing outside this package may be imported across a service boundary. If a
service needs something from another service, it belongs here instead.
"""

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.evaluation import (
    CanonicalCase,
    CaseLabel,
    CaseVariant,
    EvaluationSet,
    Language,
    RegisterStyle,
)
from herhealth_contracts.knowledge import (
    ActionCode,
    ActionDefinition,
    Actions,
    Clause,
    ComparisonOp,
    Condition,
    ConditionsFile,
    EvidenceRow,
    EvidenceStrength,
    Feature,
    FeatureKind,
    FeaturesFile,
    KnowledgeBase,
    RedFlagRule,
    RedFlagsFile,
    Source,
    SourcesFile,
    SourceStatus,
    Weights,
)
from herhealth_contracts.loading import (
    KNOWLEDGE_FILENAMES,
    load_evaluation_set,
    load_knowledge_base,
)
from herhealth_contracts.retrieval import PassageId, PassageType, RetrievedPassage
from herhealth_contracts.scoring import log_odds_for, plausibility

__version__ = "0.1.0"

__all__ = [
    "ActionCode",
    "ActionDefinition",
    "Actions",
    "CanonicalCase",
    "CaseLabel",
    "CaseVariant",
    "Clause",
    "ComparisonOp",
    "Condition",
    "ConditionsFile",
    "DecisionType",
    "EvaluationSet",
    "EvidenceRow",
    "EvidenceStrength",
    "Feature",
    "FeatureKind",
    "FeaturesFile",
    "KNOWLEDGE_FILENAMES",
    "KnowledgeBase",
    "Language",
    "PassageId",
    "PassageType",
    "RegisterStyle",
    "RetrievedPassage",
    "TriageDecision",
    "load_evaluation_set",
    "load_knowledge_base",
    "log_odds_for",
    "plausibility",
    "RedFlagRule",
    "RedFlagsFile",
    "Source",
    "SourceStatus",
    "SourcesFile",
    "Weights",
]
