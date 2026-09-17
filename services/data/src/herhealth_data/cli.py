"""Command line entry point.

Argument parsing only. Every verb's behaviour lives in
:mod:`herhealth_data.commands`, so this file stays a table of contents and the
commands stay testable without constructing a parser.

    herhealth-data fetch     retrieve source documents into raw/
    herhealth-data clean     turn fetched HTML into sectioned text
    herhealth-data evidence  generate evidence.csv from reviewed batches
    herhealth-data tables    render every knowledge file as a flat table
    herhealth-data icd       propose ICD-11 codes from the WHO API
    herhealth-data verify-quotes  check quotes against their cited source
    herhealth-data validate  check knowledge/ against the schemas
    herhealth-data build     clean, chunk, write build/passages.parquet
    herhealth-data eval      run the controller over the benchmark cases

Exit codes: 0 succeeded, 1 ran but the data was wrong, 2 could not run.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from herhealth_data import commands, paths
from herhealth_data.ingest import utc_today

# Nothing here imports herhealth_data.retrieval. That package pulls in numpy,
# which lives in the optional `retrieval` extra, and importing it at module
# scope would make every command — `validate` included — need an extra that only
# the authoring commands use. The retrieval commands import it inside their own
# functions instead, so `--model` defaults to None and is resolved there.

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="herhealth-data",
        description="Ingestion, knowledge validation and evaluation for HerHealthGPT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="fetch source documents into raw/")
    fetch_parser.add_argument("--targets", type=Path, default=paths.INGEST_TARGETS_FILE)
    fetch_parser.add_argument("--raw-dir", type=Path, default=paths.RAW_DIR)
    fetch_parser.add_argument("--lock", type=Path, default=paths.INGEST_LOCK_FILE)
    fetch_parser.add_argument(
        "--date",
        default=utc_today(),
        help="YYYY-MM-DD; which dated snapshot to write into (default: today, UTC)",
    )
    fetch_parser.add_argument(
        "--yes",
        action="store_true",
        help="actually make network requests; without it this is a dry run",
    )
    fetch_parser.set_defaults(func=commands.run_fetch)

    validate_parser = subparsers.add_parser(
        "validate", help="check knowledge/ against the schemas"
    )
    validate_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    validate_parser.set_defaults(func=commands.run_validate)

    evidence_parser = subparsers.add_parser(
        "evidence", help="generate knowledge/evidence.csv from reviewed batches"
    )
    evidence_parser.add_argument("--batches", type=Path, default=paths.EVIDENCE_BATCH_DIR)
    evidence_parser.add_argument("--out", type=Path, default=paths.KNOWLEDGE_DIR / "evidence.csv")
    evidence_parser.set_defaults(func=commands.run_evidence)

    verify_parser = subparsers.add_parser(
        "verify-quotes",
        help="check every source_quote appears verbatim in the source it cites",
    )
    verify_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    verify_parser.add_argument("--clean-dir", type=Path, default=paths.CLEAN_DIR)
    verify_parser.add_argument(
        "--verbose", action="store_true", help="list every quote, not only the failures"
    )
    verify_parser.set_defaults(func=commands.run_verify_quotes)

    icd_parser = subparsers.add_parser(
        "icd", help="propose ICD-11 codes for conditions marked TODO_VERIFY"
    )
    icd_parser.add_argument(
        "--conditions", type=Path, default=paths.KNOWLEDGE_DIR / "conditions.yaml"
    )
    icd_parser.add_argument(
        "--apply", action="store_true", help="write confident codes into conditions.yaml"
    )
    icd_parser.set_defaults(func=commands.run_icd)

    index_parser = subparsers.add_parser(
        "index", help="embed build/clean/ into a searchable passage index"
    )
    index_parser.add_argument("--clean-dir", type=Path, default=paths.CLEAN_DIR)
    index_parser.add_argument("--index-dir", type=Path, default=paths.INDEX_DIR)
    index_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    index_parser.add_argument(
        "--model", default=None, help="defaults to bge-m3; 'hashing' for the offline stand-in"
    )
    index_parser.set_defaults(func=commands.run_index)

    search_parser = subparsers.add_parser("search", help="query the passage index by hand")
    search_parser.add_argument("query")
    search_parser.add_argument("--index-dir", type=Path, default=paths.INDEX_DIR)
    search_parser.add_argument("--model", default=None, help="defaults to the index's own model")
    search_parser.add_argument("-k", type=int, default=8)
    search_parser.set_defaults(func=commands.run_search)

    propose_parser = subparsers.add_parser(
        "propose", help="propose candidate evidence rows into a DRAFT batch"
    )
    propose_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    propose_parser.add_argument("--index-dir", type=Path, default=paths.INDEX_DIR)
    propose_parser.add_argument("--model", default=None)
    propose_parser.add_argument(
        "--condition", action="append", default=[], help="restrict to a condition, repeatable"
    )
    propose_parser.add_argument("--per-gap", type=int, default=2)
    propose_parser.add_argument("--min-score", type=float, default=0.30)
    propose_parser.add_argument(
        "--limit", type=int, default=10, help="the review gate caps a batch at 10 rows"
    )
    propose_parser.add_argument(
        "--out", type=Path, default=paths.BUILD_DIR / "proposed_batch.yaml"
    )
    propose_parser.set_defaults(func=commands.run_propose)

    thresholds_parser = subparsers.add_parser(
        "thresholds", help="show where each tunable threshold sits, and whether it is fragile"
    )
    thresholds_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    thresholds_parser.set_defaults(func=commands.run_thresholds)

    tables_parser = subparsers.add_parser(
        "tables", help="render the knowledge base as flat CSV and Markdown tables"
    )
    tables_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    tables_parser.add_argument("--out", type=Path, default=paths.TABLES_DIR)
    tables_parser.set_defaults(func=commands.run_tables)

    cards_parser = subparsers.add_parser(
        "cards",
        help="render the evidence grid as readable per-condition and per-answer cards",
    )
    cards_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    cards_parser.add_argument("--out", type=Path, default=paths.CARDS_DIR)
    cards_parser.set_defaults(func=commands.run_cards)

    clean_parser = subparsers.add_parser("clean", help="turn fetched HTML into sectioned text")
    clean_parser.add_argument("--raw-dir", type=Path, default=paths.RAW_DIR)
    clean_parser.add_argument("--out-dir", type=Path, default=paths.CLEAN_DIR)
    clean_parser.add_argument("--date", default=utc_today(), help="which dated snapshot to clean")
    clean_parser.add_argument("--content-lock", type=Path, default=paths.CONTENT_LOCK_FILE)
    clean_parser.set_defaults(func=commands.run_clean)

    build_parser_ = subparsers.add_parser("build", help="build the retrieval corpus")
    build_parser_.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    build_parser_.add_argument("--raw-dir", type=Path, default=paths.RAW_DIR)
    build_parser_.add_argument("--build-dir", type=Path, default=paths.BUILD_DIR)
    build_parser_.set_defaults(func=commands.run_build)

    eval_parser = subparsers.add_parser("eval", help="run the benchmark cases")
    eval_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    eval_parser.add_argument("--cases", type=Path, default=paths.CASES_DIR)
    eval_parser.set_defaults(func=commands.run_eval)

    return parser


def _force_utf8_output() -> None:
    """Windows consoles default to a codepage that cannot encode our own text.

    Source quotes carry em-dashes and curly quotes, and the reports here use
    arrows and multiplication signs. Under cp1252 or cp1256 those either render
    as ``?`` or raise UnicodeEncodeError mid-report, which has now happened
    twice. Verifying quotes against sources by eye is the review protocol, so
    output that cannot render its own characters is not acceptable.

    The same three lines exist in the backend CLIs. Duplicated rather than
    shared: it is a terminal concern, not a contract, and moving it into
    ``packages/contracts`` would put I/O behaviour in the schema package.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)
    exit_code: int = args.func(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
