"""What each CLI verb does.

Kept out of ``cli.py`` so argument parsing and command behaviour are separately
testable. One function per verb, each returning a process exit code:

    0  did what was asked
    1  ran, but something in the data was wrong
    2  could not run — bad arguments, missing input, not implemented yet
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from herhealth_data.ingest import (
    FetchOutcome,
    FetchRecord,
    RawStore,
    fetch_all,
    http_get,
    load_plan,
    write_lock,
)

__all__ = ["run_build", "run_clean", "run_eval", "run_fetch", "run_validate"]

KNOWLEDGE_GLOBS = ("*.yaml", "*.yml", "*.csv")


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------


def run_fetch(args: argparse.Namespace) -> int:
    """Retrieve source documents into raw/. Dry run unless --yes.

    The protocol is "never fetch without asking"; the default being a no-op is
    how that is enforced for a program rather than for a person.
    """
    if not args.targets.is_file():
        print(f"error: no target list at {args.targets}")
        return 2

    plan = load_plan(args.targets)
    store = RawStore(args.raw_dir, args.date)
    dry_run = not args.yes

    records = fetch_all(plan, store, http_get, dry_run=dry_run)
    _report_fetch(records)

    if dry_run:
        print("\nDry run — no requests were made. Re-run with --yes to fetch.")
        return 0

    write_lock(records, args.lock, args.date)
    print(f"lockfile written: {args.lock}")
    return 1 if any(r.outcome is FetchOutcome.FAILED for r in records) else 0


def _report_fetch(records: list[FetchRecord]) -> None:
    for record in records:
        size = f"{record.bytes:>9,}b" if record.bytes else " " * 10
        print(f"  {record.outcome.value:<15} {record.source_id:<12} {record.slug:<28} {size}")
        print(f"  {'':<15} {record.url}")
        if record.detail:
            print(f"  {'':<15} -- {record.detail}")

    counts = Counter(r.outcome.value for r in records)
    print("\n" + ", ".join(f"{n} {outcome}" for outcome, n in sorted(counts.items())))


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------


def run_validate(args: argparse.Namespace) -> int:
    """Check knowledge/ against the schemas.

    Currently reports what it found and says plainly that it verified nothing.
    A validation step that silently approves everything is worse than none.
    """
    knowledge_dir: Path = args.knowledge
    if not knowledge_dir.is_dir():
        print(f"error: no such directory: {knowledge_dir}")
        return 2

    files: list[Path] = []
    for pattern in KNOWLEDGE_GLOBS:
        files.extend(knowledge_dir.glob(pattern))
    files.sort()

    if not files:
        print(f"{knowledge_dir}: no knowledge files yet, nothing to validate")
        return 0

    print(f"{knowledge_dir}: found {len(files)} knowledge file(s):")
    for path in files:
        print(f"  {path.name}")
    print()
    print("WARNING: these files were NOT validated. The schema and cross-file")
    print("checks are not wired up yet; a pass here currently means nothing.")
    return 0


# --------------------------------------------------------------------------
# clean
# --------------------------------------------------------------------------


def run_clean(args: argparse.Namespace) -> int:
    """Turn fetched HTML into sectioned, quotable text.

    Imports the cleaner lazily: it needs BeautifulSoup from the optional
    `ingest` extra, and `make validate` must work without that installed.
    """
    try:
        from herhealth_data.ingest.clean import clean_store, summarise
    except ImportError:
        print("error: the clean step needs the ingest extra.")
        print("  uv sync --extra ingest")
        return 2

    store = RawStore(args.raw_dir, args.date)
    if not any(store.documents()):
        print(f"nothing to clean in {args.raw_dir} for {args.date}; run `make fetch` first")
        return 2

    documents = clean_store(store, args.out_dir)
    print(f"cleaned {len(documents)} document(s) into {args.out_dir}\n")
    print(summarise(documents))

    candidates = sum(len(d.escalation_sentences) for d in documents)
    print(f"\n{candidates} escalation sentence(s) found — candidates for red_flags.yaml.")
    print("Candidates, not rules: each still needs a human to confirm it states")
    print("a condition specific enough to key an escalation rule on.")
    return 0


# --------------------------------------------------------------------------
# Not implemented yet — these exit non-zero rather than succeed vacuously
# --------------------------------------------------------------------------


def run_build(args: argparse.Namespace) -> int:
    print("build is not implemented yet — it lands in phase 4 (ingestion).")
    print("It will read raw/ through RawStore, strip boilerplate, section by")
    print("heading, replace locale-specific service references with action")
    print("codes, chunk, and write build/passages.parquet.")
    return 2


def run_eval(args: argparse.Namespace) -> int:
    print("eval is not implemented yet — it lands in phase 3 (evaluation).")
    print("It needs the phase 2 reasoning core, and will report under-triage,")
    print("over-triage, clarification recall and specificity, average questions")
    print("asked, and questions that changed nothing.")
    return 2
