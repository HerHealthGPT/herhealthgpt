"""Run a scripted consultation against the real knowledge base, no model in it.

    herhealth-triage --case services/backend/cases/sudden_severe_pain.yaml
    herhealth-triage --answer bleeding_heaviness=heavy --answer age_band=40_to_44
    herhealth-triage --interactive

This is the only way to watch the controller work end to end before the API
exists. It prints, per turn, which question was chosen, what the answer was
worth, how the differential moved, and finally which of the six stopping rules
ended it and why.

There is no model here and there will never be one. In production the model
extracts a feature value from what a user wrote and phrases the reply; both ends
are stubbed out, which is exactly what makes the run reproducible — the same
case file gives the same trace on any machine, and ``--json`` makes that
diffable in CI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml
from herhealth_contracts.knowledge import (
    UNKNOWN_VALUE,
    ActionCode,
    Feature,
    KnowledgeBase,
)
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.dialogue import (
    ScriptedAnswers,
    Transcript,
    Turn,
    run_consultation,
)
from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import StopReason

__all__ = ["main"]

#: Overrides the search for a knowledge directory. Set by the Makefile.
KNOWLEDGE_DIR_ENV = "HERHEALTH_KNOWLEDGE_DIR"

#: Printed on every conclusion. The system reports urgency; it does not identify
#: what is wrong, and the output must not be readable as though it did.
DISCLAIMER = "Urgency guidance only, from cited sources. Not a diagnosis."

#: Score movements below this are rounding, not evidence.
_MOVEMENT_EPSILON = 1e-9


# --------------------------------------------------------------------------
# Locating and loading
# --------------------------------------------------------------------------


def find_knowledge_dir(explicit: Path | None = None) -> Path:
    """``--knowledge``, then the environment, then ``./knowledge``.

    No walking up the tree looking for a repository root: that finds a different
    directory depending on where you happened to be standing, and a triage run
    that silently used the wrong knowledge base is worse than one that refused
    to start.
    """
    if explicit is not None:
        return explicit
    from_env = os.environ.get(KNOWLEDGE_DIR_ENV)
    if from_env:
        return Path(from_env)
    return Path.cwd() / "knowledge"


def _coerce(value: object, feature_id: str) -> str:
    """YAML's booleans, back to the tokens the knowledge base uses.

    ``heavy_bleeding: yes`` parses as ``True`` under YAML 1.1, not the string
    ``"yes"``. Left alone it would fail validation with a baffling message, so
    it is converted here and every other non-string type is refused rather than
    stringified — ``1.0`` becoming ``"1.0"`` would be a silent wrong answer.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    raise ValueError(
        f"{feature_id}: expected a value token, got {type(value).__name__} "
        f"({value!r}); quote it in the case file"
    )


def load_case(path: Path) -> tuple[str, dict[str, str]]:
    """Read a case file. Returns its name and the answers it holds."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} did not parse to a mapping")

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError(f"{path.name} has no 'answers' mapping")

    name = str(payload.get("name") or path.stem)
    return name, {str(k): _coerce(v, str(k)) for k, v in answers.items()}


def parse_inline(pairs: Sequence[str]) -> dict[str, str]:
    """``--answer feature=value``, repeated."""
    answers: dict[str, str] = {}
    for pair in pairs:
        feature_id, separator, value = pair.partition("=")
        if not separator or not feature_id.strip() or not value.strip():
            raise ValueError(f"expected feature=value, got {pair!r}")
        answers[feature_id.strip()] = value.strip()
    return answers


# --------------------------------------------------------------------------
# The interactive provider
# --------------------------------------------------------------------------


def ask_at_the_terminal(feature: Feature) -> str:
    """Prompt until the answer is one the knowledge base recognises."""
    allowed = (*feature.allowed_values, UNKNOWN_VALUE)
    print(f"\n  {feature.probe['en']}")
    print(f"  [{' / '.join(allowed)}]  (blank = unknown)")
    while True:
        raw = input("  > ").strip().lower()
        if not raw:
            return UNKNOWN_VALUE
        if not feature.allowed_values or raw in allowed:
            return raw
        print(f"  not one of: {', '.join(allowed)}")


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def movements(turn: Turn, base: KnowledgeBase) -> list[str]:
    """What the answer on this turn was worth, per condition.

    Read off the evidence rows rather than by differencing states, so the output
    can name the strength that applied — "strong_support" explains a jump in a
    way "+1.50" does not.
    """
    if turn.answer is None or not turn.answer.is_known:
        return []
    moved = [
        f"{row.condition_id} {row.strength.value} "
        f"({base.weights.log_odds[row.strength]:+g})"
        for row in base.evidence
        if row.feature_id == turn.answer.feature_id and row.value == turn.answer.value
        if abs(base.weights.log_odds[row.strength]) > _MOVEMENT_EPSILON
    ]
    return sorted(moved)


def render_turn(turn: Turn, base: KnowledgeBase) -> list[str]:
    features = base.features_by_id
    lines: list[str] = []

    if turn.answer is not None:
        feature = features[turn.answer.feature_id]
        lines.append(
            f"Turn {turn.number} — ask {feature.id} (burden {feature.burden})"
        )
        lines.append(f'  "{feature.probe["en"]}"')
        lines.append(f"  answer: {turn.answer.value}")
        lines.append(f"  chosen because: {turn.decision.explanation}")
        moved = movements(turn, base)
        lines.append(f"  moves: {', '.join(moved) if moved else 'nothing'}")
    return lines


def render_differential(
    differential: Sequence[tuple[str, float]], base: KnowledgeBase, limit: int = 6
) -> list[str]:
    if not differential:
        return ["  differential: nothing above the plausibility floor"]
    conditions = base.conditions_by_id
    lines = ["  differential:"]
    for condition_id, score in differential[:limit]:
        action = conditions[condition_id].baseline_action.value
        lines.append(f"    {score:.2f}  {condition_id:<28} {action}")
    if len(differential) > limit:
        lines.append(f"    … and {len(differential) - limit} more above the floor")
    return lines


def render_conclusion(transcript: Transcript, base: KnowledgeBase) -> list[str]:
    decision = transcript.final_decision
    lines = ["", f"STOP — {decision.reason.value}"]
    lines.append(f"  action: {decision.action.value if decision.action else '—'}")
    lines.append(f"  why: {decision.explanation}")

    if decision.reason is StopReason.RED_FLAG and decision.red_flag_id:
        rule = next(r for r in base.red_flags if r.id == decision.red_flag_id)
        lines.append(f"  rule: {rule.label}")
        lines.append(f"  source: {rule.source_id} — “{rule.source_quote}”")

    lines.extend(render_differential(decision.differential, base))
    lines.append(f"  questions asked: {transcript.questions_asked}")
    lines.append("")
    lines.append(f"  {DISCLAIMER}")
    return lines


def render(transcript: Transcript, base: KnowledgeBase, name: str) -> str:
    lines = [f"case: {name}", ""]
    for turn in transcript.turns:
        rendered = render_turn(turn, base)
        if rendered:
            lines.extend([*rendered, ""])
    lines.extend(render_conclusion(transcript, base))
    return "\n".join(lines)


def as_json(transcript: Transcript, name: str) -> Mapping[str, object]:
    """A stable shape for diffing runs in CI and for the evaluation harness."""
    decision = transcript.final_decision
    return {
        "case": name,
        "turns": [
            {
                "number": turn.number,
                "feature_id": turn.answer.feature_id if turn.answer else None,
                "value": turn.answer.value if turn.answer else None,
                "reason": turn.decision.reason.value,
            }
            for turn in transcript.turns
        ],
        "questions_asked": transcript.questions_asked,
        "stop_reason": decision.reason.value,
        "action": decision.action.value if decision.action else None,
        "red_flag_id": decision.red_flag_id,
        "explanation": decision.explanation,
        "differential": [
            {"condition_id": c, "plausibility": round(p, 4)}
            for c, p in decision.differential
        ],
        "disclaimer": DISCLAIMER,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="herhealth-triage",
        description="Run a scripted consultation through the triage controller.",
    )
    parser.add_argument("--knowledge", type=Path, help="the knowledge directory")
    parser.add_argument("--case", type=Path, help="a YAML case file")
    parser.add_argument(
        "--answer",
        action="append",
        default=[],
        metavar="FEATURE=VALUE",
        help="an answer, repeatable; merged over --case",
    )
    parser.add_argument(
        "--interactive", action="store_true", help="type the answers instead"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def _force_utf8_output() -> None:
    """Windows consoles default to cp1252, which cannot encode our own text.

    Probe text and source quotes contain em-dashes and curly quotes — real
    characters from real sources, not corruption to be stripped. Left alone,
    the console renders them as ``?`` and a reader cannot tell a display
    artefact from a quote that was actually mangled during ingestion. Since
    verifying quotes against sources by eye is the review protocol, output that
    lies about its own characters is not acceptable.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)

    directory = find_knowledge_dir(args.knowledge)
    try:
        base = load_knowledge_base(directory)
    except (FileNotFoundError, ValueError) as error:
        print(f"could not load the knowledge base from {directory}: {error}", file=sys.stderr)
        return 2

    engine = TriageEngine(base)

    if args.interactive:
        transcript = run_consultation(engine, ask_at_the_terminal)
        name = "interactive"
    else:
        name = "inline"
        answers: dict[str, str] = {}
        try:
            if args.case:
                name, answers = load_case(args.case)
            answers.update(parse_inline(args.answer))
            provider = ScriptedAnswers.validated(answers, base.features_by_id)
        except (OSError, ValueError) as error:
            print(f"bad case: {error}", file=sys.stderr)
            return 2
        transcript = run_consultation(engine, provider)

    if args.json:
        print(json.dumps(as_json(transcript, name), indent=2))
    else:
        print(render(transcript, base, name))

    # Non-zero on an emergency, so a shell script or CI job can key on it.
    return 1 if transcript.final_decision.action is ActionCode.EMERGENCY else 0


if __name__ == "__main__":
    raise SystemExit(main())
