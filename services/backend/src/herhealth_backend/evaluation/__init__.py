"""Evaluation of the triage controller.

Lives in the backend rather than in ``services/data`` because it drives the
engine, and nothing outside ``packages/contracts`` may cross a service boundary.
The split is: ``services/data`` owns the benchmark *data* and the converter that
produces cases; this package owns the code that *runs* them. Same arrangement as
``knowledge/`` — the data service validates those files, the backend reasons
over them, and neither imports the other.
"""

from herhealth_backend.evaluation.metrics import CaseOutcome, Metrics, score
from herhealth_backend.evaluation.runner import (
    Evaluation,
    failing_cases,
    run_case,
    run_evaluation,
    stop_reason_counts,
)

__all__ = [
    "CaseOutcome",
    "Evaluation",
    "Metrics",
    "failing_cases",
    "run_case",
    "run_evaluation",
    "score",
    "stop_reason_counts",
]
