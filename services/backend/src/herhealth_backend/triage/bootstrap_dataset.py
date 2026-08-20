"""Export multi-turn conversational training data from the outgoing controller.

Migration step 3 of docs/adr/0011-controller-free-triage.md, and the reason it
runs *before* engine.py is touched: the fine-tune's original training data
(services/data/eval/benchmark/gold_seeds_styled.csv) is 540 rows, every one a
complete answer, none a clarifying question — the documented cause of
clarification recall collapsing to 0.000 once a fine-tuned model was allowed
to decide anything. Retraining on data that actually contains a clarifying
question as a correct assistant turn is the fix, and the deterministic
controller is the only thing in this repo that has ever produced one, so this
runs it one last time before it is deleted.

**What this is not.** Every "user" turn here is a templated sentence built
from a feature's value, not something a person actually typed — this teaches
the *shape* ("a clarifying question is a legal assistant turn"), not real
sentence comprehension. Prose-to-feature extraction remains a separate,
unsolved problem (docs/research/0001, "prose-to-feature-value extraction, end
to end" — the largest unmeasured risk the note names).

**How personas are chosen.** One synthetic persona per condition, built from
that condition's own ``strong_support`` evidence rows — a mechanical readout
of already-reviewed rows, not a clinical judgement invented for this script.
A condition with no ``strong_support`` row is skipped rather than guessed at.

Output is one JSON object per line (JSONL), one line per persona, each a full
``{"messages": [...]}`` conversation — the shape TRL's conversational SFT
format expects, so ``assistant_only_loss=True`` can mask the loss to
assistant turns without any further reshaping.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from herhealth_contracts.knowledge import (
    ActionCode,
    ActionDefinition,
    EvidenceStrength,
    Feature,
    FeatureKind,
    KnowledgeBase,
    UNKNOWN_VALUE,
)
from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.agent import DEFAULT_SYSTEM_PROMPT
from herhealth_backend.triage.dialogue import ScriptedAnswers, Transcript, run_consultation
from herhealth_backend.triage.engine import TriageEngine
from herhealth_backend.triage.state import Decision, StopReason

__all__ = [
    "SYSTEM_PROMPT",
    "export_bootstrap_dataset",
    "main",
    "personas_from_knowledge_base",
    "transcript_to_conversation",
    "write_jsonl",
]

#: The same prompt TriageAgent defaults to (agent.DEFAULT_SYSTEM_PROMPT) —
#: imported rather than restated, so the bootstrap data and the served
#: prompt can never quietly drift apart.
SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT


def personas_from_knowledge_base(base: KnowledgeBase) -> dict[str, dict[str, str]]:
    """One persona per condition, from that condition's ``strong_support`` rows.

    A condition with no ``strong_support`` row is omitted — there is nothing
    to build a presenting-as-this-condition persona out of without inventing
    an answer the evidence grid does not actually claim.
    """
    personas: dict[str, dict[str, str]] = {}
    for condition in base.conditions:
        answers = {
            row.feature_id: row.value
            for row in base.evidence
            if row.condition_id == condition.id
            and row.strength is EvidenceStrength.STRONG_SUPPORT
        }
        if answers:
            personas[condition.id] = answers
    return personas


def _phrase_answer(feature: Feature, value: str) -> str:
    """A templated stand-in for what a user might type in reply to a probe."""
    if value == UNKNOWN_VALUE:
        return "I'm not sure."
    if feature.kind is FeatureKind.BOOLEAN:
        return "Yes." if value == "yes" else "No."
    return value.replace("_", " ")


def _phrase_conclusion(
    decision: Decision, base: KnowledgeBase, actions_by_code: Mapping[ActionCode, ActionDefinition]
) -> str:
    """Turn a concluding Decision into a sentence, with a citation.

    Two shapes, mirroring the rule enforced on ``TriageDecision`` in
    ``decision.py``: a red-flag-driven conclusion never names a condition —
    it cites the rule and nothing else. Every other conclusion may list the
    live differential's condition labels, the phrasing counterpart of
    ``TriageDecision.matching_conditions``.
    """
    assert decision.action is not None  # only called once should_stop is True
    action = actions_by_code[decision.action]
    # Same wording as agent.DEFAULT_SYSTEM_PROMPT's closing line and
    # triage.cli.DISCLAIMER — one sentence, never paraphrased three ways.
    disclaimer = "Urgency guidance only, from cited sources. Not a diagnosis."
    ai_notice = (
        "I'm an AI tool, not a clinician — this is based on your answers "
        "and cited sources, not a diagnosis."
    )

    if decision.reason is StopReason.RED_FLAG and decision.red_flag_id:
        rule = next(r for r in base.red_flags if r.id == decision.red_flag_id)
        return (
            f"Based on what you've told me, {action.description.lower()} "
            f'This matches a known warning sign: "{rule.source_quote}" '
            f"(source: {rule.source_id}). {ai_notice} {disclaimer}"
        )

    # Capped at 5, matching TriageDecision.matching_conditions — most of the
    # 18 authored conditions have no eliminating row (ADR 0007 finding 1), so
    # the live differential barely narrows on its own; naming all of it reads
    # as the condition roster, not a shortlist. decision.differential is
    # already sorted highest-plausibility first, so this keeps the closest.
    conditions_by_id = base.conditions_by_id
    matching_labels = [
        conditions_by_id[condition_id].label
        for condition_id, _ in decision.differential[:5]
        if condition_id in conditions_by_id
    ]
    matches = (
        f"What you've described matches patterns our sources associate with "
        f"{', '.join(matching_labels)}. "
        if matching_labels
        else ""
    )
    quote = next(
        (
            row.source_quote
            for row in base.evidence
            if decision.differential
            and row.condition_id == decision.differential[0][0]
            and row.strength is EvidenceStrength.STRONG_SUPPORT
        ),
        None,
    )
    citation = f'For example: "{quote}". ' if quote else ""
    return (
        f"Based on what you've told me, {action.description.lower()} "
        f"{matches}{citation}{ai_notice} {disclaimer}"
    )


def transcript_to_conversation(
    transcript: Transcript, base: KnowledgeBase, *, persona_id: str
) -> dict[str, object]:
    """One full multi-turn conversation, TRL conversational-SFT shape."""
    features = base.features_by_id
    actions_by_code = {a.code: a for a in base.actions.actions}
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for turn in transcript.turns:
        if turn.decision.should_stop:
            messages.append(
                {"role": "assistant", "content": _phrase_conclusion(turn.decision, base, actions_by_code)}
            )
        else:
            assert turn.decision.next_feature_id is not None
            assert turn.answer is not None
            feature = features[turn.decision.next_feature_id]
            messages.append({"role": "assistant", "content": feature.probe["en"]})
            messages.append({"role": "user", "content": _phrase_answer(feature, turn.answer.value)})

    return {"persona_id": persona_id, "messages": messages}


def export_bootstrap_dataset(base: KnowledgeBase) -> list[dict[str, object]]:
    """Run every persona through the real controller and convert the transcript."""
    engine = TriageEngine(base)
    personas = personas_from_knowledge_base(base)

    conversations = []
    for persona_id, answers in sorted(personas.items()):
        provider = ScriptedAnswers.validated(answers, base.features_by_id)
        transcript = run_consultation(engine, provider)
        conversations.append(transcript_to_conversation(transcript, base, persona_id=persona_id))
    return conversations


def write_jsonl(conversations: Sequence[Mapping[str, object]], path: Path) -> int:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for conversation in conversations:
            handle.write(json.dumps(conversation, ensure_ascii=False) + "\n")
    return len(conversations)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="herhealth-bootstrap-dataset",
        description=(
            "Run the outgoing deterministic controller over one synthetic "
            "persona per condition and export multi-turn conversational "
            "training data — see docs/adr/0011-controller-free-triage.md."
        ),
    )
    parser.add_argument("--knowledge", type=Path, default=Path("knowledge"))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("services/data/eval/benchmark/bootstrap_multi_turn.jsonl"),
    )
    args = parser.parse_args(argv)

    try:
        base = load_knowledge_base(args.knowledge)
    except (FileNotFoundError, ValueError) as error:
        print(f"could not load the knowledge base from {args.knowledge}: {error}", file=sys.stderr)
        return 2

    conversations = export_bootstrap_dataset(base)
    if not conversations:
        print("no persona had a strong_support row to build from; nothing written", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = write_jsonl(conversations, args.out)

    questions_per_persona = [
        sum(1 for m in c["messages"] if m["role"] == "assistant") - 1  # type: ignore[arg-type]
        for c in conversations
    ]
    print(f"{written} persona(s) -> {args.out}")
    print(
        f"clarifying questions per persona: min {min(questions_per_persona)}, "
        f"max {max(questions_per_persona)}, "
        f"mean {sum(questions_per_persona) / len(questions_per_persona):.1f}"
    )
    print(
        "\nBootstrap data only — every 'user' turn is templated from evidence.csv, "
        "not real prose. It teaches the ask/conclude SHAPE; it does not teach the "
        "model to read real sentences. See docs/adr/0011-controller-free-triage.md "
        "before treating this as sufficient retraining data on its own."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
