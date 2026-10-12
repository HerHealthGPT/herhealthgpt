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
from herhealth_data.commands import blocking_fetch_failures
from herhealth_data.ingest.store import FetchOutcome, FetchRecord

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


def test_fetch_dry_run_makes_no_request(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Uses the real target list but stays a dry run, so nothing is requested."""
    code = main(["fetch", "--raw-dir", str(tmp_path), "--date", "2099-01-01"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Dry run" in output
    assert not list(tmp_path.rglob("*.html"))


# --------------------------------------------------------------------------
# index, offline (hashing stand-in, no model, no endpoint)
# --------------------------------------------------------------------------


def _write_clean_doc(clean_dir: Path, source_id: str, slug: str, sentence: str) -> None:
    document = {
        "source_id": source_id,
        "slug": slug,
        "sections": [{"heading": "Symptoms", "section_type": "symptoms", "paragraphs": [sentence]}],
    }
    (clean_dir / source_id).mkdir(parents=True, exist_ok=True)
    (clean_dir / source_id / f"{slug}.json").write_text(json.dumps(document), encoding="utf-8")


def _build_index(tmp_path: Path, *extra: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    clean_dir = tmp_path / "clean"
    # Placeholder text, not clinical content: only the source id matters here.
    # Longer than MIN_SENTENCE_CHARS (40), or it is never indexed at all.
    _write_clean_doc(
        clean_dir,
        "womenshealth",
        "page",
        "A placeholder sentence from a page that is in the public domain.",
    )
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
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    return [json.loads(line) for line in lines], manifest


def test_the_served_index_has_no_quote_only_text(tmp_path: Path) -> None:
    """The default build is the one the backend serves and the one that may be
    copied to a server: every passage ingestable, none from nhs. Covers source
    passages and the evidence statements built from knowledge/ alike."""
    passages, manifest = _build_index(tmp_path)
    assert any(p["passage_type"] == "source_passage" for p in passages)
    assert all(p["may_be_ingested"] is True for p in passages)
    assert not any(p["source_id"] == "nhs" for p in passages)
    assert any(p["passage_type"] == "evidence_statement" for p in passages)
    assert manifest["contains_quote_only"] is False


def test_the_authoring_index_keeps_quote_only_text_and_says_so(tmp_path: Path) -> None:
    passages, manifest = _build_index(tmp_path, "--authoring")
    assert any(p["source_id"] == "nhs" for p in passages)
    assert manifest["contains_quote_only"] is True


def test_index_writes_no_pickle(tmp_path: Path) -> None:
    _build_index(tmp_path)
    assert sorted(p.name for p in (tmp_path / "index").iterdir()) == [
        "index.faiss",
        "manifest.json",
        "passages.jsonl",
    ]


def test_authoring_defaults_off_and_the_old_flag_is_gone() -> None:
    assert build_parser().parse_args(["index"]).authoring is False
    with pytest.raises(SystemExit):
        build_parser().parse_args(["index", "--exclude-quote-only"])


def test_search_finds_a_passage_in_a_built_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _build_index(tmp_path)
    # The passage's own words: with a bag-of-words stand-in that is the one
    # query guaranteed to rank it first among the real evidence statements.
    query = "A placeholder sentence from a page that is in the public domain."
    code = main(["search", query, "--index-dir", str(tmp_path / "index"), "-k", "1"])
    assert code == 0
    assert query in capsys.readouterr().out


# --------------------------------------------------------------------------
# fetch --tolerate-quote-only-failures
# --------------------------------------------------------------------------


def _failed(source_id: str) -> FetchRecord:
    return FetchRecord(
        source_id=source_id,
        slug="page",
        url="https://example.org/",
        licence="x",
        outcome=FetchOutcome.FAILED,
    )


def test_a_quote_only_failure_does_not_block_the_deployed_index() -> None:
    assert blocking_fetch_failures([_failed("nhs")], {"nhs": False}) == []


def test_an_ingestable_failure_still_blocks() -> None:
    failure = _failed("womenshealth")
    assert blocking_fetch_failures(
        [failure, _failed("nhs")], {"womenshealth": True, "nhs": False}
    ) == [failure]


def test_an_unknown_source_failure_blocks() -> None:
    assert len(blocking_fetch_failures([_failed("newsource")], {})) == 1


def test_tolerating_quote_only_failures_defaults_off() -> None:
    assert build_parser().parse_args(["fetch"]).tolerate_quote_only_failures is False
