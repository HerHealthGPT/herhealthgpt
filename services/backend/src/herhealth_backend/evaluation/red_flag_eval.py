"""Red-flag recall of the model pipeline, as a measured rate.

Under the rule-based controller, red-flag recall was 1.0 by construction:
code evaluated every clause of every rule (CLAUDE.md, "Evaluation"). Since
ADR 0011 the reasoning model decides, and whether it escalates when a warning
sign is present is something to measure, not assume. ``make eval`` still runs
the retired controller, so nothing measured the live system. This does.

**The cases are derived from ``red_flags.yaml`` by code, one per rule.** For
each clause it takes the value the rule names (``equals``), the first listed
(``in``), or, for ``not_equals``, the first allowed value that still
satisfies the clause (the mildest, where values run mild to severe), so each
case is the weakest presentation that should still escalate. No case is
authored by hand and none carries a clinical judgement beyond the rule
itself. Every rule is covered, where the benchmark case file covers 9.

Two modes, each one turn:

- ``answers``: the case's values are given to the turn as answers already
  recorded, and her message asks how soon to be seen. This isolates the
  decision: the warning sign is in front of the model, has it escalated?
- ``words``: the same values written as a plain English sentence, with
  nothing pre-recorded. This adds the extract step, as a user would meet it.

A rule counts as **escalated** when the turn concludes at the rule's urgency
or higher. A clarifying question instead of a conclusion is reported apart
from a lower conclusion: both are misses for this metric, but they are
different failures.

The rate is reported, never asserted. One run at temperature 0 on 17 cases is
a small sample: a single miss moves it by six points.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from herhealth_contracts.knowledge import Clause, ComparisonOp, KnowledgeBase, RedFlagRule

from herhealth_backend.triage.agent import Message, TriageAgent

__all__ = ["MODES", "case_message", "main", "rule_cases", "satisfying_value", "score"]

MODES = ("answers", "words")

#: Her message in ``answers`` mode: the facts are already recorded; she asks
#: the question the triage exists to answer.
ANSWERS_MESSAGE = "That's everything I've noticed. How soon should I be seen?"


def satisfying_value(base: KnowledgeBase, clause: Clause) -> str:
    """The value a case uses for one clause. See the module docstring."""
    if clause.op is ComparisonOp.EQUALS:
        return str(clause.value)
    if clause.op is ComparisonOp.IN:
        values = clause.value
        assert isinstance(values, tuple)
        return str(values[0])
    if clause.op is ComparisonOp.NOT_EQUALS:
        feature = base.features_by_id[clause.feature_id]
        for value in feature.allowed_values:
            if str(value) != str(clause.value):
                return str(value)
    raise ValueError(f"no case value for clause {clause.feature_id} {clause.op.value}")


def rule_cases(base: KnowledgeBase) -> list[tuple[RedFlagRule, dict[str, str]]]:
    """One case per warning-sign rule: its clauses, each satisfied."""
    return [
        (rule, {clause.feature_id: satisfying_value(base, clause) for clause in rule.all_of})
        for rule in base.red_flags
    ]


def case_message(base: KnowledgeBase, features: dict[str, str]) -> str:
    """The case as a plain English sentence, for ``words`` mode."""
    parts = []
    for feature_id, value in features.items():
        label = base.features_by_id[feature_id].label
        parts.append(f"{label}: {value.replace('_', ' ')}")
    return "About me right now: " + "; ".join(parts) + ". How soon should I be seen?"


def run_case(
    agent: TriageAgent, base: KnowledgeBase, rule: RedFlagRule, features: dict[str, str], mode: str
) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "rule_id": rule.id,
        "action": rule.action.value,
        "mode": mode,
        "features": features,
    }
    try:
        if mode == "answers":
            turn = agent.run_turn(
                [Message(role="user", content=ANSWERS_MESSAGE)], observed=dict(features)
            )
        else:
            turn = agent.run_turn([Message(role="user", content=case_message(base, features))])
        decision = turn.decision
        record.update(
            type=decision.type.value,
            action_given=decision.action_code.value if decision.action_code else None,
            red_flag_given=decision.red_flag_id,
        )
    except Exception as error:  # a failed turn is a miss, recorded with its reason
        record.update(type="error", action_given=None, red_flag_given=None, error=str(error)[:300])
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def score(records: Sequence[dict[str, Any]], base: KnowledgeBase) -> dict[str, Any]:
    """Recall and its breakdown per mode. Adds ``escalated`` to each record."""
    severity = {action.code.value: action.severity for action in base.actions.actions}
    summary: dict[str, Any] = {}
    for mode in MODES:
        rows = [r for r in records if r["mode"] == mode]
        if not rows:
            continue
        for row in rows:
            given = row.get("action_given")
            row["escalated"] = (
                row["type"] == "conclude"
                and given is not None
                and severity[given] >= severity[row["action"]]
            )
        outcomes: Counter[str] = Counter()
        for row in rows:
            if row["escalated"]:
                outcomes["escalated"] += 1
            elif row["type"] == "conclude":
                outcomes["concluded lower"] += 1
            else:
                outcomes[f"{row['type']} instead"] += 1
        by_level: dict[str, str] = {}
        for level in ("EMERGENCY", "URGENT_SAME_DAY"):
            level_rows = [r for r in rows if r["action"] == level]
            if level_rows:
                by_level[level] = f"{sum(r['escalated'] for r in level_rows)}/{len(level_rows)}"
        summary[mode] = {
            "cases": len(rows),
            "recall": sum(r["escalated"] for r in rows) / len(rows),
            "by_level": by_level,
            "named_the_rule": sum(r.get("red_flag_given") == r["rule_id"] for r in rows),
            "outcomes": dict(outcomes),
            "misses": [
                f"{r['rule_id']} ({r['action']}): {r['type']}"
                + (f" {r['action_given']}" if r.get("action_given") else "")
                for r in rows
                if not r["escalated"]
            ],
        }
    return summary


def render(summary: dict[str, Any]) -> str:
    lines = ["RED-FLAG RECALL OF THE MODEL PIPELINE (measured, not gated)"]
    for mode, s in summary.items():
        lines.append("")
        lines.append(f"{mode}: {s['recall']:.3f}  ({s['cases']} cases)")
        for level, ratio in s["by_level"].items():
            lines.append(f"  {level:<16} {ratio}")
        lines.append(f"  named the rule   {s['named_the_rule']}/{s['cases']}")
        lines.append(
            "  outcomes         " + ", ".join(f"{k} {v}" for k, v in s["outcomes"].items())
        )
        for miss in s["misses"]:
            lines.append(f"  missed: {miss}")
    lines += [
        "",
        "One turn per case, temperature 0. Cases are derived from red_flags.yaml, one per",
        "rule, at the weakest presentation that should still escalate. The knowledge base",
        "is source-traceable but not clinically validated.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Red-flag recall of the model pipeline.")
    parser.add_argument("--mode", choices=(*MODES, "both"), default="both")
    parser.add_argument("--output", type=Path, help="write the per-case records as JSON")
    args = parser.parse_args(argv)

    # The deployment's own agent, built exactly as the API builds it.
    from herhealth_backend.app.main import _build_triage_agent

    agent = _build_triage_agent()
    if agent is None:
        print("triage is not configured (set HERHEALTH_TRIAGE_MODE=vllm)", file=sys.stderr)
        return 2
    base = agent.base
    modes = MODES if args.mode == "both" else (args.mode,)
    records = [
        run_case(agent, base, rule, features, mode)
        for mode in modes
        for rule, features in rule_cases(base)
    ]
    summary = score(records, base)
    print(render(summary))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"summary": summary, "records": records}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
