"""Run the evaluation and print the result.

    herhealth-eval --knowledge knowledge --cases services/data/eval/cases

Exit codes: 0 every gate passed, 1 a gate failed, 2 the run never started.
``make eval`` is this.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from herhealth_contracts.loading import load_evaluation_set, load_knowledge_base

from herhealth_backend.evaluation.runner import (
    Evaluation,
    failing_cases,
    run_evaluation,
    stop_reason_counts,
)
from herhealth_backend.triage.cli import find_knowledge_dir
from herhealth_backend.triage.engine import TriageEngine

__all__ = ["main"]

DEFAULT_CASES = Path("services/data/eval/cases")

#: Attached to every report. The labels are read off the benchmark's own
#: reference answers, not adjudicated by a clinician, and no number here should
#: be quoted without it.
CAVEAT = (
    "Silver labels, derived from the benchmark's reference answers and not "
    "clinician-adjudicated. The knowledge base is source-traceable but not "
    "clinically validated."
)


def _line(label: str, value: float | None, width: int = 34) -> str:
    """``unmeasured`` never prints as a number.

    A rate over an empty denominator is not zero. Red-flag recall shown as
    1.000 when no red-flag case exists would be the most dangerous line this
    program could print.
    """
    shown = "unmeasured" if value is None else f"{value:.3f}"
    return f"  {label:<{width}} {shown}"


def render(evaluation: Evaluation) -> str:
    metrics = evaluation.metrics
    lines = [
        f"cases scored: {metrics.cases_scored}"
        + (
            f"   (out of scope, not scored: {metrics.cases_out_of_scope})"
            if metrics.cases_out_of_scope
            else ""
        ),
        "",
        "This measures the RETIRED rule-based controller, not the live model pipeline;",
        "the live red-flag recall is `make eval-red-flags` (ADR 0011).",
        "",
        "GATED",
        _line(f"red-flag recall ({metrics.red_flag_cases} cases)", metrics.red_flag_recall),
        _line("under-triage rate", metrics.under_triage_rate),
    ]
    for language, rate in sorted(metrics.under_triage_by_language.items()):
        lines.append(_line(f"  under-triage [{language.value}]", rate))
    lines.append(
        _line(
            f"clarification recall ({metrics.clarification_cases} cases)",
            metrics.clarification_recall,
        )
    )
    lines.append(
        _line(
            f"cross-language agreement ({metrics.languages_compared} langs)",
            metrics.cross_language_action_agreement,
        )
    )
    if metrics.clarification_recall == 1.0:
        # A true number about a question that was never hard. Printed with the
        # reason so nobody quotes it as evidence the controller clarifies well.
        lines.append(
            "    note: the controller cannot conclude before asking, so "
            "clarification recall is near-vacuous until the end-to-end run"
        )

    lines += [
        "",
        "REPORTED, NOT GATED",
        _line("over-triage rate", metrics.over_triage_rate),
        _line("exact action agreement", metrics.exact_action_agreement),
        _line("mean questions asked", metrics.mean_questions_asked),
        _line("register agreement", metrics.register_action_agreement),
        "",
        "HOW CONSULTATIONS ENDED",
    ]
    for reason, count in sorted(stop_reason_counts(evaluation).items(), key=lambda item: -item[1]):
        lines.append(f"  {reason.value:<34} {count}")

    failures = failing_cases(evaluation)
    if failures:
        lines += ["", f"UNDER-TRIAGED OR MISSED ({len(failures)})"]
        for outcome in failures[:20]:
            detail = (
                f"expected red flag {outcome.expected_red_flag_id!r}, "
                f"got {outcome.fired_red_flag_id!r}"
                if outcome.expected_red_flag_id
                else f"{outcome.expected_action.value} -> {outcome.predicted_action.value}"
            )
            lines.append(f"  {outcome.canonical_case_id:<38} {detail}")
        if len(failures) > 20:
            lines.append(f"  … and {len(failures) - 20} more")

    gated = metrics.gated_failures()
    lines += ["", "FAILED GATES" if gated else "ALL GATES PASSED"]
    lines += [f"  {failure}" for failure in gated]
    lines += ["", f"  {CAVEAT}"]
    return "\n".join(lines)


def as_json(evaluation: Evaluation) -> dict[str, object]:
    metrics = evaluation.metrics
    return {
        "cases_scored": metrics.cases_scored,
        "cases_out_of_scope": metrics.cases_out_of_scope,
        "gated": {
            "red_flag_recall": metrics.red_flag_recall,
            "red_flag_cases": metrics.red_flag_cases,
            "under_triage_rate": metrics.under_triage_rate,
            "under_triage_by_language": {
                language.value: rate for language, rate in metrics.under_triage_by_language.items()
            },
            "clarification_recall": metrics.clarification_recall,
            "cross_language_action_agreement": metrics.cross_language_action_agreement,
        },
        "reported": {
            "over_triage_rate": metrics.over_triage_rate,
            "exact_action_agreement": metrics.exact_action_agreement,
            "mean_questions_asked": metrics.mean_questions_asked,
            "register_action_agreement": metrics.register_action_agreement,
        },
        "stop_reasons": {r.value: n for r, n in stop_reason_counts(evaluation).items()},
        "failed_gates": metrics.gated_failures(),
        "passed": evaluation.passed,
        "caveat": CAVEAT,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="herhealth-eval",
        description="Run the benchmark cases through the triage controller.",
    )
    parser.add_argument("--knowledge", type=Path, help="the knowledge directory")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    args = build_parser().parse_args(argv)
    knowledge = find_knowledge_dir(args.knowledge)

    try:
        base = load_knowledge_base(knowledge)
    except (FileNotFoundError, ValueError) as error:
        print(f"could not load the knowledge base from {knowledge}: {error}", file=sys.stderr)
        return 2

    if not args.cases.is_dir():
        print(f"no case directory at {args.cases}", file=sys.stderr)
        return 2

    try:
        evaluation_set = load_evaluation_set(args.cases, base)
    except (OSError, ValueError) as error:
        print(f"could not load cases from {args.cases}: {error}", file=sys.stderr)
        return 2

    if not evaluation_set.cases:
        # Not a pass. An evaluation over nothing has demonstrated nothing, and
        # exiting 0 here would let an empty directory look like a green build.
        print(f"no cases found in {args.cases}", file=sys.stderr)
        return 2

    evaluation = run_evaluation(TriageEngine(base), evaluation_set)

    if args.json:
        print(json.dumps(as_json(evaluation), indent=2))
    else:
        print(render(evaluation))

    return 0 if evaluation.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
