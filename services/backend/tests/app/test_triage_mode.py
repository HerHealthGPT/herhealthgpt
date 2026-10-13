"""``HERHEALTH_TRIAGE_MODE``: which values a deployment may run in."""

from __future__ import annotations

import pytest

from herhealth_backend.app import config


@pytest.mark.parametrize("mode", ["vllm", "demo", "off", "VLLM", " demo "])
def test_triage_mode_accepts_vllm_demo_off(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv(config.TRIAGE_MODE_ENV, mode)
    assert config.triage_mode() == mode.strip().lower()


def test_unset_mode_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.TRIAGE_MODE_ENV, raising=False)
    assert config.triage_mode() == "off"


def test_triage_mode_rejects_openrouter_naming_the_valid_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.TRIAGE_MODE_ENV, "openrouter")
    with pytest.raises(RuntimeError, match="vllm, demo, off"):
        config.triage_mode()


def test_the_decision_model_defaults_to_the_base_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.DECISION_MODEL_ENV, raising=False)
    assert config.decision_model() == "Qwen/Qwen3.5-9B"


def test_the_answer_model_defaults_to_the_adapter_and_can_be_switched_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(config.ANSWER_MODEL_ENV, raising=False)
    assert config.answer_model() == "herhealth"
    monkeypatch.setenv(config.ANSWER_MODEL_ENV, "")
    assert config.answer_model() is None
