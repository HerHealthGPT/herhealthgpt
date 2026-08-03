"""Tests for argument parsing and command wiring.

The CLI is a table of contents; these check that each verb reaches its command
module with the right defaults, not what the commands do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from herhealth_data import paths
from herhealth_data.cli import build_parser, main

# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


@pytest.mark.parametrize("verb", ["fetch", "validate", "build", "eval"])
def test_every_verb_is_wired_to_a_command(verb: str) -> None:
    args = build_parser().parse_args([verb])
    assert callable(args.func)


def test_a_verb_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_fetch_defaults_to_a_dry_run() -> None:
    assert build_parser().parse_args(["fetch"]).yes is False


def test_fetch_defaults_point_at_the_tracked_files() -> None:
    args = build_parser().parse_args(["fetch"])
    assert args.targets == paths.INGEST_TARGETS_FILE
    assert args.lock == paths.INGEST_LOCK_FILE
    assert args.raw_dir == paths.RAW_DIR


def test_fetch_date_defaults_to_an_iso_day() -> None:
    date = build_parser().parse_args(["fetch"]).date
    assert len(date) == 10 and date.count("-") == 2


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------


def test_validate_on_empty_dir_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "--knowledge", str(tmp_path)]) == 0
    assert "nothing to validate" in capsys.readouterr().out


def test_validate_on_missing_dir_cannot_run(tmp_path: Path) -> None:
    assert main(["validate", "--knowledge", str(tmp_path / "absent")]) == 2


def test_validate_says_plainly_that_it_checked_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "features.yaml").write_text("features: []\n", encoding="utf-8")
    assert main(["validate", "--knowledge", str(tmp_path)]) == 0
    assert "NOT validated" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Unimplemented verbs
# --------------------------------------------------------------------------


@pytest.mark.parametrize("verb", ["build", "eval"])
def test_unimplemented_verbs_exit_two(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([verb]) == 2
    assert "not implemented" in capsys.readouterr().out


# --------------------------------------------------------------------------
# fetch, without touching the network
# --------------------------------------------------------------------------


def test_fetch_with_a_missing_target_list_cannot_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["fetch", "--targets", str(tmp_path / "absent.yaml")])
    assert code == 2
    assert "no target list" in capsys.readouterr().out


def test_fetch_dry_run_makes_no_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uses the real target list but stays a dry run, so nothing is requested."""
    code = main(["fetch", "--raw-dir", str(tmp_path), "--date", "2099-01-01"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Dry run" in output
    assert not list(tmp_path.rglob("*.html"))
