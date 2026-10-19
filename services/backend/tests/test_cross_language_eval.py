"""Cross-language agreement on the action code (CLAUDE.md, rule 4)."""

from __future__ import annotations

from pathlib import Path

from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.evaluation.cross_language_eval import LANGUAGES, compare
from herhealth_backend.evaluation.decision_eval import ScriptResult, load_scripts

REPO = Path(__file__).resolve().parents[3]


def _result(script_id: str, action: str | None) -> ScriptResult:
    return ScriptResult(script_id, action is not None, 3, action, (), None)


def test_agreement_is_on_the_action_code_over_scripts_that_concluded() -> None:
    summary = compare(
        {
            "en": [_result("a", "ROUTINE_APPOINTMENT"), _result("b", "URGENT_SAME_DAY")],
            "ar": [_result("a", "ROUTINE_APPOINTMENT"), _result("b", "ROUTINE_APPOINTMENT")],
            "fr": [_result("a", "ROUTINE_APPOINTMENT"), _result("b", None)],
        }
    )
    assert summary["concluded_in_every_language"] == 1
    assert summary["agree_on_action"] == 1
    assert summary["agreement"] == 1.0


def test_a_lower_urgency_than_english_is_reported() -> None:
    summary = compare(
        {
            "en": [_result("b", "URGENT_SAME_DAY")],
            "ar": [_result("b", "ROUTINE_APPOINTMENT")],
            "fr": [_result("b", "EMERGENCY")],
        }
    )
    assert summary["lower_than_english"] == ["b [ar] ROUTINE_APPOINTMENT < en URGENT_SAME_DAY"]
    assert summary["agree_on_action"] == 0


def test_the_translated_scripts_match_the_english_ones() -> None:
    features = set(load_knowledge_base(REPO / "knowledge").features_by_id)
    scripts = {lang: load_scripts(REPO / path) for lang, path in LANGUAGES.items()}
    english = scripts["en"]
    for lang in ("ar", "fr"):
        assert [s.id for s in scripts[lang]] == [s.id for s in english]
        for translated, original in zip(scripts[lang], english, strict=True):
            assert set(translated.answers) == set(original.answers)
            assert set(translated.answers) <= features
            assert translated.default_reply != original.default_reply
