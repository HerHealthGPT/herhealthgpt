"""Cross-language agreement on the action code, over full consultations.

The same scripted consultation, run to a conclusion in English, Arabic and
French, compared on the ACTION CODE it ends with, never on text (CLAUDE.md,
"Why it is built this way", rule 4). First turns could not measure this: no
item concluded on its first turn in every language (ADR 0018, 2026-10-15).

The scripts are ``decision_scripts.jsonl`` and its translations, matched by
``id``. The translations were written for this evaluation and have not been
reviewed by a native speaker; the result is only as good as they are.

Two things are reported, and the second matters more:

* **agreement** — scripts that concluded in all three languages with the same
  action code;
* **lower than English** — a language concluding at a lower urgency than
  English for the same script, which is under-triage by language.

Agreement alone is not a safety metric: a system that concluded routine for
everything would agree perfectly.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from herhealth_contracts.knowledge import CANONICAL_ACTION_ORDER, ActionCode

from herhealth_backend.evaluation.decision_eval import ScriptResult, load_scripts, run_script

__all__ = ["LANGUAGES", "compare", "main"]

#: Language code to script file.
LANGUAGES = {
    "en": Path("services/data/eval/decision_scripts.jsonl"),
    "ar": Path("services/data/eval/decision_scripts_ar.jsonl"),
    "fr": Path("services/data/eval/decision_scripts_fr.jsonl"),
}


def _severity(action: str | None) -> int | None:
    return None if action is None else CANONICAL_ACTION_ORDER.index(ActionCode(action))


def compare(results: dict[str, list[ScriptResult]]) -> dict[str, Any]:
    """Per-script actions and the agreement figures, from results per language."""
    by_id: dict[str, dict[str, ScriptResult]] = {}
    for language, rows in results.items():
        for row in rows:
            by_id.setdefault(row.id, {})[language] = row
    languages = list(results)
    items = []
    agree = all_concluded = 0
    lower: list[str] = []
    for script_id, runs in by_id.items():
        actions = {lang: runs[lang].action if lang in runs else None for lang in languages}
        concluded = all(runs.get(lang) is not None and runs[lang].concluded for lang in languages)
        all_concluded += concluded
        same = concluded and len(set(actions.values())) == 1
        agree += same
        english = _severity(actions.get("en"))
        for lang in languages:
            other = _severity(actions[lang])
            if lang != "en" and english is not None and other is not None and other < english:
                lower.append(f"{script_id} [{lang}] {actions[lang]} < en {actions['en']}")
        items.append({"id": script_id, "actions": actions, "agree": same})
    return {
        "scripts": len(by_id),
        "concluded_in_every_language": all_concluded,
        "agree_on_action": agree,
        "agreement": agree / all_concluded if all_concluded else None,
        "lower_than_english": lower,
        "concluded_by_language": {
            lang: sum(r.concluded for r in rows) for lang, rows in results.items()
        },
        "items": items,
    }


def main(argv: Sequence[str] | None = None) -> int:
    from herhealth_backend.app.main import _build_triage_agent

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("build/cross_language_eval.json"))
    args = parser.parse_args(argv)
    agent = _build_triage_agent()
    if agent is None:
        print("triage is not configured: set HERHEALTH_TRIAGE_MODE=vllm and build the index")
        return 2

    results: dict[str, list[ScriptResult]] = {}
    for language, path in LANGUAGES.items():
        results[language] = [run_script(agent, script) for script in load_scripts(path)]
        print(
            f"{language}: {sum(r.concluded for r in results[language])} of "
            f"{len(results[language])} concluded",
            flush=True,
        )

    summary = compare(results)
    print(
        f"\nconcluded in all three languages: {summary['concluded_in_every_language']} "
        f"of {summary['scripts']}"
    )
    agreement = summary["agreement"]
    print(
        "same action code in all three: "
        f"{summary['agree_on_action']} of {summary['concluded_in_every_language']}"
        + (f" ({agreement:.2f})" if agreement is not None else "")
    )
    print(f"lower urgency than English: {len(summary['lower_than_english'])}")
    for line in summary["lower_than_english"]:
        print(f"  {line}")
    for item in summary["items"]:
        actions = ", ".join(f"{k} {v or '-'}" for k, v in item["actions"].items())
        print(f"  {item['id']}: {actions}{'' if item['agree'] else '   <- differs'}")
    print(
        "\nAction codes compared, never text. Translations unreviewed by a native "
        "speaker; one run at temperature 0; silver-labelled source questions."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        **summary,
        "results": {
            lang: [
                {
                    "id": r.id,
                    "concluded": r.concluded,
                    "turns": r.turns,
                    "action": r.action,
                    "asked": list(r.asked),
                    "error": r.error,
                }
                for r in rows
            ]
            for lang, rows in results.items()
        },
    }
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
