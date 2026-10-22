"""Trace consultations through every layer, call by call.

Builds the agent exactly as the API does (``app.main._build_triage_agent``),
then wraps each of its five model-facing parts in a recorder: retrieval, the
extract step, the decision model, the answer writer and the topic reader.
Every call is logged with what went in, what came out and how long it took.
After each turn the route's own post-processing runs on the result, by the
route's own functions (``app.triage.routes``): the invented-condition repair,
the closed-vocabulary check, the provenance cap, the cycle-data breakdown and
the payload the frontend receives.

What it does not exercise: HTTP, cookies and the database. History, carried
passages, recorded answers and asked questions are rebuilt between turns the
way ``routes._load_session`` rebuilds them from stored rows.

Writes ``build/trace/<case>.json`` per case, the system prompt of every model
call under ``build/trace/prompts/``, and ``build/trace/summary.md``.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.retrieval import RetrievedPassage

from herhealth_backend.triage.agent import Message, TriageAgent

__all__ = ["DEFAULT_CASES", "GATE_MARKERS", "load_cases", "main"]

DEFAULT_CASES = Path("services/data/eval/trace_cases.jsonl")
OUT_DIR = Path("build/trace")
MAX_TURNS = 8

#: The text each gate in ``TriageAgent.run_turn`` appends when it sends a
#: reply back, so a traced re-prompt can be named.
GATE_MARKERS = {
    "YOUR PREVIOUS ANSWER DECLINED AND WAS REJECTED": "unclear-decline gate",
    'YOUR PREVIOUS ANSWER WAS AN EXPLANATION (type "inform")': "inform-with-symptoms gate",
    "She asked about her own imported cycle data": "her-data gate",
    "YOU DID NOT TRIAGE AGAIN": "her-data gate (named question)",
    "YOUR PREVIOUS ANSWER CONCLUDED TOO EARLY": "premature-conclusion gate",
    "YOUR PREVIOUS QUESTION WAS REJECTED": "repeated-question gate",
    "YOU REPEATED THE QUESTION AGAIN": "repeated-question gate (named question)",
    "YOUR PREVIOUS ANSWER DID NOT ESCALATE": "red-flag gate",
}

#: The Cycle History table of an Apple Health PDF (the shape of a real one,
#: no name), for the case that asks about her imported data.
_APPLE_TABLE = """Cycle History
YEAR CYCLE DURATION CYCLE LENGTH PERIOD LENGTH
2026 Started 26 Sep 23 days 4 days
29 Aug – 25 Sep 28 days 1 day
1 – 28 Aug 28 days 4 days
5 – 31 Jul 27 days 4 days
8 Jun – 4 Jul 27 days 2 days
15 Apr – 7 Jun 54 days 4 days
18 Mar – 14 Apr 28 days 2 days
19 Feb – 17 Mar 27 days 3 days
21 Jan – 18 Feb 29 days 6 days
26 Dec 2025 – 20 Jan 2026 26 days 3 days
2025 22 Nov – 25 Dec 34 days 3 days
28 Oct – 21 Nov 25 days 3 days
Cycle Detail
"""


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _passages(passages: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": p.id,
            "source": p.source_id,
            "type": p.passage_type.value,
            "score": round(p.score, 3),
            "text": p.text[:140],
        }
        for p in (passages or [])
        if isinstance(p, RetrievedPassage)
    ]


def _decision(d: TriageDecision) -> dict[str, Any]:
    return {
        "type": d.type.value,
        "next_feature_id": d.next_feature_id,
        "action_code": d.action_code.value if d.action_code else None,
        "red_flag_id": d.red_flag_id,
        "matching_conditions": list(d.matching_conditions),
        "citations": list(d.citations),
        "observed": dict(d.observed),
        "text": (d.question_text or d.answer_text or d.rationale or "")[:400],
    }


class Recorder:
    """Stands in for one part of the agent and logs every call to it."""

    def __init__(
        self,
        inner: Any,
        layer: str,
        log: list[dict[str, Any]],
        save_prompt: Callable[[str], str],
    ) -> None:
        self._inner = inner
        self._layer = layer
        self._log = log
        self._save_prompt = save_prompt

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def call(*args: Any, **kwargs: Any) -> Any:
            entry: dict[str, Any] = {"layer": self._layer, "call": name}
            entry.update(self._inputs(name, args, kwargs))
            started = time.monotonic()
            try:
                result = attr(*args, **kwargs)
            except Exception as error:
                entry["error"] = f"{type(error).__name__}: {str(error)[:300]}"
                entry["seconds"] = round(time.monotonic() - started, 2)
                self._log.append(entry)
                raise
            entry["seconds"] = round(time.monotonic() - started, 2)
            entry.update(self._outputs(name, result))
            self._log.append(entry)
            return result

        return call

    def _inputs(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
        if name == "search":
            query = args[0] if args else kwargs.get("query")
            return {"query": str(query)[:300], "k": kwargs.get("k")}
        if name == "decide":
            prompt = str(kwargs.get("system_prompt", ""))
            gates = [label for marker, label in GATE_MARKERS.items() if marker in prompt]
            return {
                "prompt_chars": len(prompt),
                "prompt_file": self._save_prompt(prompt),
                "re_prompted_by": gates[-1] if gates else None,
                "context": [p.id for p in kwargs.get("context", ())],
                "history_messages": len(kwargs.get("history", ())),
            }
        if name == "extract":
            return {"pending_feature": kwargs.get("pending_feature")}
        if name == "mentioned":
            return {"question": str(args[0] if args else "")[:200]}
        return {}

    @staticmethod
    def _outputs(name: str, result: Any) -> dict[str, Any]:
        if name == "search":
            return {"results": _passages(result)}
        if name == "decide":
            return {
                "decision": _decision(result.decision),
                "attempts": [f"{a.client}:{a.outcome.value}" for a in result.attempts],
            }
        if name == "extract":
            return {"extracted": dict(result)}
        if name == "mentioned":
            return {"topics": list(result)}
        return {"result": repr(result)[:400]}


def _her_data(case: dict[str, Any], base: Any) -> tuple[str | None, dict[str, str], Any]:
    """Profile and cycle data, as ``routes._known_background`` renders them."""
    import datetime

    from herhealth_backend.app.accounts.cycle_import import _from_apple_health_pdf
    from herhealth_backend.triage.agent import render_known_background
    from herhealth_backend.triage.cycle_data import prefill, render_cycle_background, summarize

    profile = render_known_background(age_band=case.get("profile_age_band"), health_note=None)
    if case.get("cycle_data") != "apple_health_pdf_lookalike":
        return profile, {}, None
    summary = summarize(_from_apple_health_pdf(_APPLE_TABLE), today=datetime.date(2026, 10, 19))
    answers = prefill(summary, base)
    cycle = render_cycle_background(summary, answers)
    return "\n\n".join(b for b in (profile, cycle) if b), answers, summary


def run_case(agent: TriageAgent, case: dict[str, Any], prompt_dir: Path) -> dict[str, Any]:
    from herhealth_backend.app.triage.routes import (
        _breakdown_language,
        _decision_payload,
        _emergency_signs,
        _her_data_use,
        _passage_from_cited,
        _with_breakdown,
    )
    from herhealth_backend.triage.cycle_data import asks_about_cycle_data, render_cycle_breakdown
    from herhealth_backend.triage.provenance import drop_unknown_conditions, enforce_provenance_cap
    from herhealth_backend.triage.vocabulary import validate_against_knowledge_base

    background, cycle_answers, summary = _her_data(case, agent.base)
    history: list[Message] = []
    carried: dict[str, RetrievedPassage] = {}
    recorded: dict[str, str] = {}
    asked: list[str] = []
    turns: list[dict[str, Any]] = []
    message = case["opening"]
    profile = {"age_band": case["profile_age_band"]} if case.get("profile_age_band") else {}

    for number in range(1, MAX_TURNS + 1):
        log: list[dict[str, Any]] = []
        counter = [0]

        def save(prompt: str, number: int = number, counter: list[int] = counter) -> str:
            counter[0] += 1
            path = prompt_dir / f"{case['id']}-turn{number}-call{counter[0]}.txt"
            path.write_text(prompt, encoding="utf-8")
            return str(path)

        traced = replace(
            agent,
            retrieval=Recorder(agent.retrieval, "retrieval (embedding + FAISS)", log, save),
            reasoning=Recorder(agent.reasoning, "decision model (base, vLLM)", log, save),
            extractor=Recorder(agent.extractor, "extract step (base, vLLM)", log, save),
            answer_writer=Recorder(agent.answer_writer, "page writer (base, vLLM)", log, save),
            symptom_topics=Recorder(agent.symptom_topics, "topic reader (base, vLLM)", log, save),
        )
        history.append(Message(role="user", content=message))
        observed = {**profile, **cycle_answers, **recorded}
        breakdown = (
            render_cycle_breakdown(summary, _breakdown_language(history))
            if summary is not None and asks_about_cycle_data(message)
            else None
        )
        started = time.monotonic()
        record: dict[str, Any] = {
            "turn": number,
            "her_message": message,
            "state_in": {
                "recorded": dict(observed),
                "asked": list(asked),
                "carried": list(carried),
            },
            "about_her_data": breakdown is not None,
            "calls": log,
        }
        try:
            turn = traced.run_turn(
                history,
                carried_context=tuple(carried.values()),
                background=background,
                observed=observed,
                asked=asked,
                about_her_data=breakdown is not None,
            )
            decision = drop_unknown_conditions(turn.decision, agent.base)
            validate_against_knowledge_base(decision, agent.base, turn.retrieved)
            decision = enforce_provenance_cap(decision, turn.retrieved)
            if breakdown is not None:
                decision = _with_breakdown(decision, breakdown)
            payload = _decision_payload(
                decision,
                turn.retrieved,
                base=agent.base,
                observed=observed,
                question=message,
                mentioned=(*decision.observed, *turn.mentioned),
            )
            her = _her_data_use(
                summary,
                cycle_answers,
                breakdown=breakdown is not None,
                concluded=decision.type is DecisionType.CONCLUDE,
                first_turn=number == 1,
            )
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {str(error)[:400]}"
            record["seconds"] = round(time.monotonic() - started, 1)
            turns.append(record)
            break
        record["seconds"] = round(time.monotonic() - started, 1)
        record["agent_attempts"] = [f"{a.client}:{a.outcome.value}" for a in turn.attempts]
        record["final"] = _decision(decision)
        record["shown_to_her"] = {
            "text": decision.question_text or decision.answer_text or decision.rationale,
            "cited_sources": [
                {
                    "source": c.get("source_id"),
                    "type": c.get("passage_type"),
                    "text": str(c.get("text"))[:160],
                }
                for c in payload.get("cited_passages", [])
            ],
            "care_guidance": payload.get("care_guidance"),
            "emergency_signs": _emergency_signs(
                decision, agent.base, {**observed, **decision.observed}, asked
            ),
            "her_data": her,
        }
        turns.append(record)

        if decision.type in (DecisionType.CONCLUDE, DecisionType.DECLINE):
            break
        # As the route stores it and _load_session rebuilds it.
        content = decision.question_text or decision.answer_text or decision.rationale
        history.append(Message(role="assistant", content=content))
        for raw in payload.get("cited_passages", []):
            passage = _passage_from_cited(raw)
            if passage is not None:
                carried.setdefault(passage.id, passage)
        recorded.update(decision.observed)
        if decision.next_feature_id:
            asked.append(decision.next_feature_id)

        if decision.type is DecisionType.ASK and decision.next_feature_id:
            message = case["answers"].get(
                decision.next_feature_id, case.get("default_reply", "No.")
            )
        elif not case["answers"]:
            break  # an informational question with nothing more to say
        else:
            message = case.get(
                "after_inform_reply", "Thank you. Is this something I should get checked?"
            )

    final = turns[-1].get("final") or {}
    return {
        "id": case["id"],
        "kind": case["kind"],
        "turns": turns,
        "outcome": final.get("type") or "error",
        "action": final.get("action_code"),
        "seconds": round(sum(t.get("seconds", 0) for t in turns), 1),
    }


_CODE_GATES = ("red-flag-gate", "repeat-gate", "her-data-gate")


def _summary_md(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Traced consultations",
        "",
        "| case | kind | turns | outcome | urgency | gates that acted | seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        gates = {
            c["re_prompted_by"] for t in r["turns"] for c in t["calls"] if c.get("re_prompted_by")
        } | {
            a.split(":")[0] + " (in code)"
            for t in r["turns"]
            for a in t.get("agent_attempts", [])
            if a.split(":")[0] in _CODE_GATES
        }
        lines.append(
            f"| {r['id']} | {r['kind']} | {len(r['turns'])} | {r['outcome']} | "
            f"{r['action'] or '-'} | {', '.join(sorted(gates)) or '-'} | {r['seconds']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    from herhealth_backend.app.main import _build_triage_agent

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--only", help="run one case id")
    args = parser.parse_args(argv)
    agent = _build_triage_agent()
    if agent is None:
        print("triage is not configured: set HERHEALTH_TRIAGE_MODE=vllm and build the index")
        return 2
    prompt_dir = OUT_DIR / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for case in load_cases(args.cases):
        if args.only and case["id"] != args.only:
            continue
        result = run_case(agent, case, prompt_dir)
        (OUT_DIR / f"{case['id']}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"{result['id']}: {result['outcome']} {result['action'] or ''} "
            f"in {len(result['turns'])} turn(s), {result['seconds']}s",
            flush=True,
        )
    # Every case traced so far, not only this run's, so --only adds to it.
    everything = [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(OUT_DIR.glob("T*.json"))
    ]
    (OUT_DIR / "summary.md").write_text(_summary_md(everything), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
