"""Does a turn complete, and does the system ask when it should?

Two measurements, both through the real ``TriageAgent`` (ADR 0018):

* **First turns.** Each question in ``decision_questions.jsonl`` is sent as
  the opening message of a consultation. Recorded: whether the reply passed
  every check, the kind of decision, and the time taken. A subset is flagged
  as describing her own symptoms; on those, an explanation in place of a
  question or an urgency level is the failure this project most wants to see
  less of.
* **Scripted consultations.** Each script in ``decision_scripts.jsonl`` has an
  opening message and her reply to each feature she may be asked about.
  Recorded: whether it reached a conclusion, and in how many turns.

Reported, never gated. "Valid" means a reply passed this system's own checks;
nothing here measures whether the urgency advice was right. The questions are
English and come from a benchmark whose labels are silver, not
clinician-adjudicated; the flags and the scripted replies were written for
this evaluation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from herhealth_contracts.decision import DecisionType, TriageDecision

from herhealth_backend.triage.agent import MaxTurnsExceeded, Message, TriageAgent

__all__ = [
    "Question",
    "Script",
    "ScriptResult",
    "TurnRecord",
    "load_questions",
    "load_scripts",
    "main",
    "run_first_turns",
    "run_script",
    "summarise_first_turns",
]

DEFAULT_QUESTIONS = Path("services/data/eval/decision_questions.jsonl")
DEFAULT_SCRIPTS = Path("services/data/eval/decision_scripts.jsonl")

#: Her reply to a question the script has no answer for.
DEFAULT_REPLY = "No."
#: Her reply after an explanation, which asked her nothing.
AFTER_INFORM_REPLY = "Thank you. Is this something I should get checked?"


@dataclass(frozen=True, slots=True)
class Question:
    id: int
    style: str
    question: str
    describes_own_symptoms: bool


@dataclass(frozen=True, slots=True)
class TurnRecord:
    question: Question
    ok: bool
    type: str | None
    action: str | None
    seconds: float
    error: str | None
    attempts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Script:
    id: str
    opening: str
    answers: dict[str, str]


@dataclass(frozen=True, slots=True)
class ScriptResult:
    id: str
    concluded: bool
    turns: int
    action: str | None
    asked: tuple[str, ...]
    error: str | None


def _rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_questions(path: Path) -> list[Question]:
    return [
        Question(
            id=int(str(row["id"])),
            style=str(row["style"]),
            question=str(row["question"]),
            describes_own_symptoms=bool(row["describes_own_symptoms"]),
        )
        for row in _rows(path)
    ]


def load_scripts(path: Path) -> list[Script]:
    scripts = []
    for row in _rows(path):
        answers = row["answers"]
        assert isinstance(answers, dict)
        scripts.append(
            Script(
                id=str(row["id"]),
                opening=str(row["opening"]),
                answers={str(k): str(v) for k, v in answers.items()},
            )
        )
    return scripts


def run_first_turns(agent: TriageAgent, questions: Sequence[Question]) -> list[TurnRecord]:
    records: list[TurnRecord] = []
    for question in questions:
        started = time.monotonic()
        try:
            turn = agent.run_turn([Message(role="user", content=question.question)])
        except Exception as error:  # every failure is a result here, not a crash
            records.append(
                TurnRecord(
                    question=question,
                    ok=False,
                    type=None,
                    action=None,
                    seconds=time.monotonic() - started,
                    error=f"{type(error).__name__}: {str(error)[:300]}",
                    attempts=(),
                )
            )
            continue
        decision = turn.decision
        records.append(
            TurnRecord(
                question=question,
                ok=True,
                type=decision.type.value,
                action=decision.action_code.value if decision.action_code else None,
                seconds=time.monotonic() - started,
                error=None,
                attempts=tuple(f"{a.client}:{a.outcome.value}" for a in turn.attempts),
            )
        )
    return records


def summarise_first_turns(records: Sequence[TurnRecord]) -> dict[str, object]:
    valid = [r for r in records if r.ok]
    own = [r for r in records if r.question.describes_own_symptoms]
    return {
        "questions": len(records),
        "valid": len(valid),
        "by_type": dict(sorted(Counter(r.type for r in valid if r.type).items())),
        "median_seconds": statistics.median(r.seconds for r in records) if records else 0.0,
        "max_seconds": max((r.seconds for r in records), default=0.0),
        "describing_own_symptoms": {
            "questions": len(own),
            "valid": sum(r.ok for r in own),
            "asked": sum(r.type == "ask" for r in own),
            "concluded": sum(r.type == "conclude" for r in own),
            "informed": sum(r.type == "inform" for r in own),
        },
    }


#: The agent's own limit. A shorter one here would count a long but
#: legitimate consultation as unfinished: the warning-sign screen for severe
#: pelvic pain alone takes about ten questions (ADR 0007).
SCRIPT_MAX_TURNS = 12


def run_script(
    agent: TriageAgent, script: Script, *, max_turns: int = SCRIPT_MAX_TURNS
) -> ScriptResult:
    """One scripted consultation, to a conclusion or until the turns run out."""
    asked: list[str] = []
    turns = 0

    def reply(decision: TriageDecision) -> str:
        nonlocal turns
        turns += 1
        if decision.type is DecisionType.ASK and decision.next_feature_id:
            asked.append(decision.next_feature_id)
            return script.answers.get(decision.next_feature_id, DEFAULT_REPLY)
        return AFTER_INFORM_REPLY

    try:
        transcript = replace(agent, max_turns=max_turns).run_consultation(script.opening, reply)
    except MaxTurnsExceeded:
        return ScriptResult(script.id, False, max_turns, None, tuple(asked), None)
    except AssertionError:
        # run_consultation expects a question, an answer or a conclusion; a
        # decline in mid-consultation gives it nothing to continue with.
        return ScriptResult(
            script.id,
            False,
            turns + 1,
            None,
            tuple(asked),
            "the model declined mid-consultation, so there was no question to answer",
        )
    except Exception as error:
        return ScriptResult(
            script.id,
            False,
            turns + 1,
            None,
            tuple(asked),
            f"{type(error).__name__}: {str(error)[:300]}",
        )
    final = transcript.final_decision
    return ScriptResult(
        script.id,
        True,
        transcript.turns_taken,
        final.action_code.value if final.action_code else None,
        tuple(asked),
        None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    from herhealth_backend.app.main import _build_triage_agent

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--scripts", type=Path, default=DEFAULT_SCRIPTS)
    parser.add_argument("--out", type=Path, default=Path("build/decision_eval.json"))
    parser.add_argument("--skip-scripts", action="store_true")
    parser.add_argument("--skip-first-turns", action="store_true")
    args = parser.parse_args(argv)

    agent = _build_triage_agent()
    if agent is None:
        print("triage is not configured: set HERHEALTH_TRIAGE_MODE=vllm and build the index")
        return 2

    questions = [] if args.skip_first_turns else load_questions(args.questions)
    records = run_first_turns(agent, questions)
    summary = summarise_first_turns(records)
    own = summary["describing_own_symptoms"]
    assert isinstance(own, dict)
    print(
        f"first turns: {summary['valid']} of {summary['questions']} valid; "
        f"by type {summary['by_type']}"
    )
    print(f"  median {summary['median_seconds']:.0f}s, slowest {summary['max_seconds']:.0f}s")
    print(
        f"  describing her own symptoms ({own['questions']}): {own['valid']} valid — "
        f"{own['asked']} asked, {own['concluded']} concluded, {own['informed']} informed"
    )
    for record in records:
        if not record.ok:
            print(f"  invalid q{record.question.id}: {record.error}")

    report: dict[str, object] = {
        "first_turns": summary,
        "turns": [
            {
                "id": r.question.id,
                "ok": r.ok,
                "type": r.type,
                "action": r.action,
                "seconds": round(r.seconds, 1),
                "error": r.error,
                "attempts": list(r.attempts),
            }
            for r in records
        ],
    }
    if not args.skip_scripts:
        results = [run_script(agent, script) for script in load_scripts(args.scripts)]
        concluded = [r for r in results if r.concluded]
        print(f"\nscripted consultations: {len(concluded)} of {len(results)} reached a conclusion")
        for r in results:
            outcome = (
                f"{r.action} in {r.turns} turn(s)"
                if r.concluded
                else (r.error or f"no conclusion in {r.turns} turns")
            )
            print(f"  {r.id}: {outcome}; asked {list(r.asked)}")
        report["scripts"] = [
            {
                "id": r.id,
                "concluded": r.concluded,
                "turns": r.turns,
                "action": r.action,
                "asked": list(r.asked),
                "error": r.error,
            }
            for r in results
        ]
    print(
        "\n'Valid' means a reply passed this system's own checks, not that the advice was right."
        "\nEnglish only; silver-labelled benchmark questions. Reported, not gated."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
