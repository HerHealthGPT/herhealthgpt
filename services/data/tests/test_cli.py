"""Tests for argument parsing and command wiring.

The CLI is a table of contents; these check that each verb reaches its command
module with the right defaults, not what the commands do.
"""

from __future__ import annotations

import json
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


def test_validate_on_empty_dir_reports_missing_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty directory is not a pass — every required file is absent."""
    assert main(["validate", "--knowledge", str(tmp_path)]) == 1
    assert "file is missing" in capsys.readouterr().out


def test_validate_on_missing_dir_cannot_run(tmp_path: Path) -> None:
    assert main(["validate", "--knowledge", str(tmp_path / "absent")]) == 2


def test_validate_passes_on_the_repository_knowledge_base(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate"]) == 0
    assert "OK:" in capsys.readouterr().out


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


# --------------------------------------------------------------------------
# index --exclude-quote-only, offline (hashing stand-in, no model download)
# --------------------------------------------------------------------------


def _write_clean_doc(clean_dir: Path, source_id: str, slug: str, sentence: str) -> None:
    document = {
        "source_id": source_id,
        "slug": slug,
        "sections": [{"heading": "Symptoms", "section_type": "symptoms", "paragraphs": [sentence]}],
    }
    (clean_dir / source_id).mkdir(parents=True, exist_ok=True)
    (clean_dir / source_id / f"{slug}.json").write_text(json.dumps(document), encoding="utf-8")


def _build_index(tmp_path: Path, *extra: str) -> list[dict[str, object]]:
    clean_dir = tmp_path / "clean"
    # Placeholder text, not clinical content: only the source id matters here.
    _write_clean_doc(clean_dir, "womenshealth", "page", "A placeholder sentence, public domain.")
    _write_clean_doc(clean_dir, "nhs", "page", "A placeholder sentence from a quote-only page.")
    index_dir = tmp_path / "index"
    code = main(
        [
            "index",
            *("--clean-dir", str(clean_dir), "--index-dir", str(index_dir)),
            *("--model", "hashing", *extra),
        ]
    )
    assert code == 0
    lines = (index_dir / "passages.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_index_without_the_flag_keeps_quote_only_text_in_the_files(tmp_path: Path) -> None:
    """The authoring index: NHS is present, flagged, and filtered only at query time."""
    passages = _build_index(tmp_path)
    assert any(p["source_id"] == "nhs" for p in passages)
    assert any(p["may_be_ingested"] is False for p in passages)


def test_exclude_quote_only_leaves_no_nhs_text_in_the_index_files(tmp_path: Path) -> None:
    """What scripts/publish-index.sh checks before anything reaches S3 or an image:
    every passage ingestable, none from nhs. Covers both source passages and the
    evidence statements built from knowledge/ (NHS backs many of those rows)."""
    passages = _build_index(tmp_path, "--exclude-quote-only")
    assert passages
    assert all(p["may_be_ingested"] is True for p in passages)
    assert not any(p["source_id"] == "nhs" for p in passages)
    assert any(p["passage_type"] == "evidence_statement" for p in passages)


def test_exclude_quote_only_defaults_off() -> None:
    assert build_parser().parse_args(["index"]).exclude_quote_only is False
