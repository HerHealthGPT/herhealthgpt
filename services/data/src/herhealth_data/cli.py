"""Command line entry point.

Argument parsing only. Every verb's behaviour lives in
:mod:`herhealth_data.commands`, so this file stays a table of contents and the
commands stay testable without constructing a parser.

    herhealth-data fetch     retrieve source documents into raw/
    herhealth-data clean     turn fetched HTML into sectioned text
    herhealth-data evidence  generate evidence.csv from reviewed batches
    herhealth-data tables    render every knowledge file as a flat table
    herhealth-data validate  check knowledge/ against the schemas
    herhealth-data build     clean, chunk, write build/passages.parquet
    herhealth-data eval      run the controller over the benchmark cases

Exit codes: 0 succeeded, 1 ran but the data was wrong, 2 could not run.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from herhealth_data import commands, paths
from herhealth_data.ingest import utc_today

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

    tables_parser = subparsers.add_parser(
        "tables", help="render the knowledge base as flat CSV and Markdown tables"
    )
    tables_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    tables_parser.add_argument("--out", type=Path, default=paths.TABLES_DIR)
    tables_parser.set_defaults(func=commands.run_tables)

    clean_parser = subparsers.add_parser("clean", help="turn fetched HTML into sectioned text")
    clean_parser.add_argument("--raw-dir", type=Path, default=paths.RAW_DIR)
    clean_parser.add_argument("--out-dir", type=Path, default=paths.CLEAN_DIR)
    clean_parser.add_argument("--date", default=utc_today(), help="which dated snapshot to clean")
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code: int = args.func(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
