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

from herhealth_contracts.scoring import plausibility

from herhealth_data.ingest import (
    FetchOutcome,
    FetchRecord,
    RawStore,
    RobotsPolicy,
    fetch_all,
    http_get,
    load_plan,
    write_lock,
)
from herhealth_data.knowledge import Severity, load_knowledge_base, validate_directory
from herhealth_data.thresholds import (
    FRAGILE_MARGIN,
    analyse,
    eliminating_rows_needed,
    reachable_scores,
    rules_out_ceiling,
)

__all__ = [
    "run_build",
    "run_clean",
    "run_eval",
    "run_evidence",
    "run_icd",
    "run_tables",
    "run_fetch",
    "run_thresholds",
    "run_validate",
    "run_verify_quotes",
]



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

    records = fetch_all(
        plan, store, http_get, dry_run=dry_run, robots=RobotsPolicy(http_get)
    )
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
    """Check knowledge/ against the schemas and the cross-file rules.

    Reports every problem in one run rather than stopping at the first.
    Warnings are printed but do not fail; errors do.
    """
    knowledge_dir: Path = args.knowledge
    if not knowledge_dir.is_dir():
        print(f"error: no such directory: {knowledge_dir}")
        return 2

    problems = validate_directory(knowledge_dir)
    failures = [p for p in problems if p.severity is Severity.ERROR]
    warnings = [p for p in problems if p.severity is Severity.WARNING]

    for problem in failures:
        print(problem)
    if failures and warnings:
        print()
    for problem in warnings:
        print(problem)

    print()
    if failures:
        print(f"FAILED: {len(failures)} error(s), {len(warnings)} warning(s)")
        return 1

    base, _ = load_knowledge_base(knowledge_dir)
    if base is not None:
        print(
            f"OK: {len(base.features)} features, {len(base.conditions)} conditions, "
            f"{len(base.evidence)} evidence rows, {len(base.red_flags)} red flags, "
            f"{len(base.sources)} sources"
        )
    print(f"{len(warnings)} warning(s)")
    return 0


# --------------------------------------------------------------------------
# thresholds
# --------------------------------------------------------------------------


def run_thresholds(args: argparse.Namespace) -> int:
    """Show where each tunable threshold sits among reachable evidence scores.

    Exits 1 if any threshold is fragile — sitting so close to a score the
    evidence can actually produce that its meaning is an accident rather than a
    decision. Not wired into CI, because a fragile threshold is a design debt to
    discuss, not a build break.
    """
    knowledge_dir: Path = args.knowledge
    base, problems = load_knowledge_base(knowledge_dir)
    if base is None:
        for problem in problems:
            print(problem)
        return 2

    weights = base.weights
    combos = reachable_scores(weights)

    print("SCORES THE EVIDENCE CAN ACTUALLY REACH")
    print("  A threshold only means something relative to these.\n")
    for combo in combos:
        print(f"  {combo.score:+6.2f} log-odds = {plausibility(combo.score):.3f}   "
              f"{combo.describe()}")

    print("\nWHERE EACH THRESHOLD SITS")
    fragile = []
    for placement in analyse(weights):
        flag = "  ← FRAGILE" if placement.is_fragile else ""
        print(f"\n  {placement.name} = {placement.value}  ({placement.log_odds:+.3f} log-odds)")
        print(f"    means: {placement.meaning}")
        if placement.margin_below is not None and placement.below is not None:
            print(f"    room below ({placement.below.describe()}): "
                  f"{placement.margin_below:+.3f}{flag}")
        if placement.margin_above is not None and placement.above is not None:
            print(f"    room above ({placement.above.describe()}): {placement.margin_above:+.3f}")
        robust = placement.robust_value()
        if placement.is_fragile and robust is not None:
            print(f"    robust alternative, equal room either side: {robust:.3f}")
        if placement.is_fragile:
            fragile.append(placement)

    print("\nELIMINATION")
    print(f"  argues_against rows needed to reach the floor: "
          f"{eliminating_rows_needed(weights):.1f}")
    print(f"  rules_out overcomes prior support only below "
          f"{rules_out_ceiling(weights):+.2f} log-odds  (see docs/adr/0009)")

    print()
    if fragile:
        print(f"FRAGILE: {len(fragile)} threshold(s) within {FRAGILE_MARGIN} log-odds "
              f"of a reachable score — {', '.join(p.name for p in fragile)}")
        return 1
    print("OK: every threshold has clear room on both sides")
    return 0


# --------------------------------------------------------------------------
# evidence
# --------------------------------------------------------------------------


def run_evidence(args: argparse.Namespace) -> int:
    """Generate knowledge/evidence.csv from the reviewed batch files.

    Deterministic: rows are sorted, so re-running produces a byte-identical
    file and a diff only ever shows real changes.
    """
    from herhealth_data.evidence import BatchError, build_evidence_csv

    try:
        written, batches = build_evidence_csv(args.batches, args.out)
    except BatchError as error:
        print(f"error: {error}")
        return 1

    for batch in batches:
        state = f"approved {batch.reviewed_on}" if batch.approved else "DRAFT - not included"
        print(f"  {batch.name:<40} {len(batch.rows):>3} row(s)   {state}")

    drafts = [b for b in batches if not b.approved]
    if drafts:
        print(
            f"\n{len(drafts)} batch(es) awaiting review. "
            "Set `approved: true` in the file to include them."
        )
    print(f"\nwrote {written} row(s) to {args.out}")
    print("Run `make validate` to check them against the rest of the knowledge base.")
    return 0


# --------------------------------------------------------------------------
# verify-quotes
# --------------------------------------------------------------------------


def run_verify_quotes(args: argparse.Namespace) -> int:
    """Check every source_quote appears verbatim in the source it cites.

    Separate from `validate` because it needs build/clean, which is generated
    and gitignored — validate must work from a fresh clone with no corpus.
    """
    from herhealth_data.provenance import load_corpus, summarise, verify_quotes

    if not args.clean_dir.is_dir():
        print(f"error: no cleaned corpus at {args.clean_dir}")
        print("Run `make fetch` then `make clean` first.")
        return 2

    base, problems = load_knowledge_base(args.knowledge)
    if base is None:
        print("error: the knowledge base does not load; run `make validate` first")
        for problem in problems:
            print(problem)
        return 1

    quotes = [
        (f"evidence.csv  {r.condition_id}/{r.feature_id}={r.value}", r.source_id, r.source_quote)
        for r in base.evidence
    ] + [
        (f"red_flags.yaml  {rule.id}", rule.source_id, rule.source_quote)
        for rule in base.red_flags
    ]

    corpus = load_corpus(args.clean_dir)
    checks = verify_quotes(quotes, corpus)
    failures = [c for c in checks if c.is_problem]

    for check in checks:
        if check.is_problem or args.verbose:
            print(check.describe())

    print(f"\n{len(quotes)} quote(s) checked against {len(corpus.sources())} source(s)")
    print(summarise(checks))

    if failures:
        print(f"\nFAILED: {len(failures)} quote(s) could not be verified against their source")
        return 1
    print("\nEvery quote appears verbatim in the source it cites.")
    return 0


# --------------------------------------------------------------------------
# icd
# --------------------------------------------------------------------------


def run_icd(args: argparse.Namespace) -> int:
    """Propose ICD-11 codes for conditions still marked TODO_VERIFY.

    Prints proposals for review. Writes nothing unless --apply is given, and
    never writes a code it is not confident in: an unfilled field is honest,
    a wrong identifier looks authoritative and is not.
    """
    import yaml

    from herhealth_data.icd import IcdError, credentials_from_env, fetch_token, propose_codes

    payload = yaml.safe_load(args.conditions.read_text(encoding="utf-8"))
    pending = [
        (c["id"], str(c.get("search_term") or c["label"]).split(",")[0].strip())
        for c in payload["conditions"]
        if str(c.get("icd11", "")).strip() == "TODO_VERIFY"
    ]
    if not pending:
        print("no conditions are marked TODO_VERIFY; nothing to resolve")
        return 0

    try:
        client_id, secret = credentials_from_env()
        token = fetch_token(client_id, secret)
        proposals = propose_codes(pending, token)
    except IcdError as error:
        print(f"error: {error}")
        return 2

    print(f"{len(pending)} condition(s) to resolve:\n")
    for proposal in proposals:
        print(proposal.describe())

    confident = [p for p in proposals if p.is_confident]
    unresolved = len(proposals) - len(confident)
    print(f"\n{len(confident)} confident, {unresolved} left as TODO_VERIFY")

    if not args.apply:
        print("\nProposals only. Re-run with --apply to write them into conditions.yaml.")
        return 0

    text = args.conditions.read_text(encoding="utf-8")
    for proposal in confident:
        marker = f"  - id: {proposal.condition_id}"
        start = text.index(marker)
        todo = text.index("icd11: TODO_VERIFY", start)
        text = text[:todo] + f"icd11: {proposal.code}" + text[todo + len("icd11: TODO_VERIFY"):]
    args.conditions.write_text(text, encoding="utf-8")
    print(f"\nwrote {len(confident)} code(s) into {args.conditions}")
    return 0


# --------------------------------------------------------------------------
# tables
# --------------------------------------------------------------------------


def run_tables(args: argparse.Namespace) -> int:
    """Render every knowledge file as a flat table.

    Generated and disposable: nothing reads these back. They exist so a whole
    file can be read at a glance and pasted into a report.
    """
    from herhealth_data.tables import build_tables, write_csvs, write_markdown

    base, problems = load_knowledge_base(args.knowledge)
    if base is None:
        print("error: the knowledge base does not load; run `make validate` first")
        for problem in problems:
            print(problem)
        return 1

    tables = build_tables(base)
    written = write_csvs(tables, args.out)
    document = write_markdown(tables, args.out / "knowledge.md")

    for table in tables:
        print(f"  {table.name:<12} {len(table):>4} rows")
    print(f"\nwrote {len(written)} CSV(s) and {document}")
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
        from herhealth_data.ingest.clean import clean_store, summarise, write_content_lock
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

    write_content_lock(documents, args.content_lock, args.date)
    print(f"\ncontent lock written: {args.content_lock}")
    print("A changed text_hash there means the words moved — unlike the raw-byte")
    print("hash, which changes on markup churn every single fetch.")

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
