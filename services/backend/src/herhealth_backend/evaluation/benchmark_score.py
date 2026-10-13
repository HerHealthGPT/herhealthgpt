"""Score first-turn outcomes against the benchmark's silver labels.

Reads the JSON-lines file a benchmark run writes (one first turn per
question) and compares each outcome with the question's ``gold_risk_level``
(``routine``, ``see-doctor`` or ``urgent``) and ``requires_clarification``.

The scoring was agreed with the repo owner on 2026-10-12. The paper's models
gave one answer per question; this system is a conversation, and only a
conclusion carries an urgency level. So:

* **Strict under-triage**: of the questions labelled ``see-doctor`` or
  ``urgent``, the share where the system gave a lower level *or no level at
  all*. An informational answer counts against it. A clarifying question
  does not, because no answer has been given yet; an invalid reply is
  reported separately.
* The same questions are also broken down, because one number hides
  whether a miss was an explanation or a lower level.

Two cautions belong beside every number from here. A first turn is not the
system's final answer: a question asked on turn one may still lead to the
right level, and this cannot see that. And many ``see-doctor`` labels sit on
purely informational questions, which the system explains; the strict measure
counts those against it. The labels are silver, not clinician-adjudicated.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

__all__ = ["main", "outcome", "score"]

_LEVEL = {"routine": 0, "see-doctor": 1, "urgent": 2}
_ACTION_LEVEL = {
    "SELF_CARE": "routine",
    "ROUTINE_APPOINTMENT": "see-doctor",
    "URGENT_SAME_DAY": "urgent",
    "EMERGENCY": "urgent",
}


def outcome(row: Mapping[str, object]) -> str:
    """One of routine, see-doctor, urgent, asked, no-level, declined, invalid."""
    if not row.get("ok"):
        return "invalid"
    kind = row.get("type")
    if kind == "conclude":
        return _ACTION_LEVEL.get(str(row.get("action")), "invalid")
    return {"ask": "asked", "inform": "no-level", "decline": "declined"}.get(str(kind), "invalid")


def _bucket(gold: str, result: str) -> str:
    if result in ("asked", "no-level", "declined", "invalid"):
        return result
    return "met or exceeded" if _LEVEL[result] >= _LEVEL[gold] else "lower level"


def score(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    need = [r for r in rows if r["gold_risk_level"] in ("see-doctor", "urgent")]
    breakdown = Counter(_bucket(str(r["gold_risk_level"]), outcome(r)) for r in need)
    under = breakdown["no-level"] + breakdown["lower level"]

    clarify = [r for r in rows if r["requires_clarification"] == "yes"]
    asked = sum(outcome(r) == "asked" for r in clarify)

    routine = [r for r in rows if r["gold_risk_level"] == "routine"]
    over = sum(outcome(r) in ("see-doctor", "urgent") for r in routine)

    by_seed: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_seed[str(r["seed_id"])].add(outcome(r))

    return {
        "questions": len(rows),
        "outcomes": dict(sorted(Counter(outcome(r) for r in rows).items())),
        "needing_a_doctor": {
            "questions": len(need),
            "under_triaged": under,
            "under_triage_rate": under / len(need) if need else 0.0,
            "breakdown": {
                key: breakdown[key]
                for key in (
                    "met or exceeded",
                    "asked",
                    "no-level",
                    "lower level",
                    "declined",
                    "invalid",
                )
            },
        },
        "clarification": {
            "questions": len(clarify),
            "asked": asked,
            "recall": asked / len(clarify) if clarify else 0.0,
        },
        "routine": {
            "questions": len(routine),
            "over_triaged": over,
            "outcomes": dict(sorted(Counter(outcome(r) for r in routine).items())),
        },
        "consistency": {
            "seeds": len(by_seed),
            "all_rewordings_same_outcome": sum(len(found) == 1 for found in by_seed.values()),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("results", type=Path, help="the JSON-lines file a benchmark run wrote")
    args = parser.parse_args(argv)
    rows = [
        json.loads(line)
        for line in args.results.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(json.dumps(score(rows), indent=2))
    print(
        "\nFirst turns only; a question asked is not a final answer. Silver labels, "
        "not clinician-adjudicated. English."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
