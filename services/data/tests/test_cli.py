"""Smoke tests for the CLI scaffold. No network, no fixtures, no knowledge files."""

from __future__ import annotations

from pathlib import Path

import pytest

from herhealth_data.cli import main


def test_validate_on_empty_dir_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "--knowledge", str(tmp_path)]) == 0
    assert "nothing to validate" in capsys.readouterr().out


def test_validate_on_missing_dir_fails(tmp_path: Path) -> None:
    assert main(["validate", "--knowledge", str(tmp_path / "nope")]) == 2


def test_validate_warns_that_it_did_not_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "features.yaml").write_text("features: []\n", encoding="utf-8")
    assert main(["validate", "--knowledge", str(tmp_path)]) == 0
    assert "NOT validated" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["build", "eval"])
def test_unimplemented_commands_exit_nonzero(command: str) -> None:
    assert main([command]) == 2
