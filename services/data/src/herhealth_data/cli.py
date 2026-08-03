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
from pathlib import Path

# cli.py -> herhealth_data -> src -> data -> services -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_CASES_DIR = REPO_ROOT / "services" / "data" / "eval" / "cases"

KNOWLEDGE_GLOBS = ("*.yaml", "*.yml", "*.csv")


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
