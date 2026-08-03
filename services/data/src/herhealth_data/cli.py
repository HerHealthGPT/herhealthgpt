"""Command line entry point for the data service.

Three verbs, matching the Makefile targets:

    validate  check knowledge/ against the contracts schemas
    build     fetch -> clean -> chunk -> build/passages.parquet
    eval      run the triage controller over the benchmark cases

Only `validate` is implemented in phase 1, and only partially: the schemas it
will check against arrive in deliverable 2 and the checks themselves in
deliverable 8. Until then it reports what it found and says plainly that it
did not verify it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

# cli.py -> herhealth_data -> src -> data -> services -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_CASES_DIR = REPO_ROOT / "services" / "data" / "eval" / "cases"
DEFAULT_TARGETS_FILE = REPO_ROOT / "services" / "data" / "ingest_targets.yaml"
DEFAULT_LOCK_FILE = REPO_ROOT / "services" / "data" / "ingest.lock.jsonl"

KNOWLEDGE_GLOBS = ("*.yaml", "*.yml", "*.csv")


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _knowledge_files(knowledge_dir: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in KNOWLEDGE_GLOBS:
        found.extend(knowledge_dir.glob(pattern))
    return sorted(found)


def cmd_validate(args: argparse.Namespace) -> int:
    knowledge_dir: Path = args.knowledge
    if not knowledge_dir.is_dir():
        print(f"error: no such directory: {knowledge_dir}", file=sys.stderr)
        return 2

    files = _knowledge_files(knowledge_dir)
    if not files:
        print(f"{knowledge_dir}: no knowledge files yet, nothing to validate")
        return 0

    print(f"{knowledge_dir}: found {len(files)} knowledge file(s):")
    for path in files:
        print(f"  {path.name}")
    print()
    print("WARNING: these files were NOT validated. The schema checks land in")
    print("deliverable 8; a pass here currently means nothing.")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch source documents. Dry run unless --yes is given."""
    from herhealth_data.ingest.fetch import (
        FetchOutcome,
        fetch_all,
        http_get,
        load_plan,
        write_lock,
    )

    plan = load_plan(args.targets)
    dry_run = not args.yes

    records = fetch_all(
        plan,
        raw_dir=args.raw_dir,
        on_date=args.date,
        transport=http_get,
        dry_run=dry_run,
    )

    for r in records:
        size = f"{r.bytes:>8,}b" if r.bytes else " " * 9
        print(f"  {r.outcome:<15} {r.source_id:<12} {r.slug:<15} {size}  {r.url}")
        if r.detail:
            print(f"  {'':<15} {r.detail}")

    counts: dict[str, int] = {}
    for r in records:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1
    print("\n" + ", ".join(f"{n} {outcome}" for outcome, n in sorted(counts.items())))

    if dry_run:
        print("\nDry run — no requests were made. Re-run with --yes to fetch.")
        return 0

    write_lock(records, args.lock, args.date)
    print(f"lockfile written: {args.lock}")
    return 1 if counts.get(FetchOutcome.FAILED) else 0


def cmd_build(args: argparse.Namespace) -> int:
    print("build is not implemented yet — it lands in phase 4 (ingestion).", file=sys.stderr)
    return 2


def cmd_eval(args: argparse.Namespace) -> int:
    print("eval is not implemented yet — it lands in phase 3 (evaluation).", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="herhealth-data", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="check knowledge/ against the schemas")
    validate.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    validate.set_defaults(func=cmd_validate)

    fetch = subparsers.add_parser("fetch", help="fetch source documents into raw/")
    fetch.add_argument("--targets", type=Path, default=DEFAULT_TARGETS_FILE)
    fetch.add_argument("--raw-dir", type=Path, default=REPO_ROOT / "raw")
    fetch.add_argument("--lock", type=Path, default=DEFAULT_LOCK_FILE)
    fetch.add_argument("--date", default=_today(), help="YYYY-MM-DD, the dated raw/ directory")
    fetch.add_argument(
        "--yes",
        action="store_true",
        help="actually make network requests; without it this is a dry run",
    )
    fetch.set_defaults(func=cmd_fetch)

    build = subparsers.add_parser("build", help="build the retrieval corpus")
    build.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    build.set_defaults(func=cmd_build)

    evaluate = subparsers.add_parser("eval", help="run the benchmark cases")
    evaluate.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    evaluate.add_argument("--cases", type=Path, default=DEFAULT_CASES_DIR)
    evaluate.set_defaults(func=cmd_eval)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
