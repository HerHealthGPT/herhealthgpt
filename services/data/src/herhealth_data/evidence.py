"""Build ``knowledge/evidence.csv`` from reviewed batch files.

Rows are authored in YAML under ``services/data/evidence_batches/`` and the CSV
is generated. Two reasons, both practical:

**Review and machine input stay in sync by construction.** The batch file is
what a human reads and approves — one block per row, quote on its own lines,
readable. The CSV is what the loader parses. Generating one from the other means
they cannot drift.

**CSV is a hostile format to hand-edit.** Every ``source_quote`` is a sentence
containing commas, and often quotation marks. One stray character silently
changes a clinical claim or shifts every column right. Writing through
``csv.writer`` quotes and escapes correctly every time.

The build is deterministic: rows are sorted by
``(condition_id, feature_id, value)``, so re-running produces a byte-identical
file and a diff only ever shows real changes.

Every row is validated against ``EvidenceRow`` **before** anything is written,
so a bad batch fails without leaving a half-written CSV behind.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from herhealth_contracts.knowledge import EvidenceRow
from pydantic import ValidationError

__all__ = [
    "COLUMNS",
    "BatchError",
    "build_evidence_csv",
    "load_batches",
    "write_rows",
]

#: Column order in the generated CSV. Matches EvidenceRow's field order.
COLUMNS: Final[tuple[str, ...]] = (
    "condition_id",
    "feature_id",
    "value",
    "strength",
    "source_id",
    "source_quote",
    "note",
)


class BatchError(ValueError):
    """A batch file could not be turned into valid rows."""


@dataclass(frozen=True, slots=True)
class Batch:
    """One set of rows, as authored.

    ``approved`` is the review gate, enforced here rather than remembered. A
    batch that has not been read by a human contributes nothing to the CSV, so
    drafting rows is always safe: the worst case is a file nobody acted on.
    """

    path: Path
    rows: tuple[EvidenceRow, ...]
    approved: bool
    reviewed_on: str | None = None

    @property
    def name(self) -> str:
        return self.path.stem


def load_batches(directory: Path) -> list[Batch]:
    """Read and validate every batch file, in filename order.

    Filenames are numbered so the order is the order they were reviewed in,
    which makes the generated CSV's provenance legible.

    Unapproved batches are still parsed and validated — a draft with a bad row
    should fail loudly now, not on the morning someone approves it.
    """
    if not directory.is_dir():
        raise BatchError(f"no batch directory at {directory}")

    batches: list[Batch] = []
    for path in sorted(directory.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_rows = payload.get("rows") or []
        approved = bool(payload.get("approved", False))
        reviewed_on = payload.get("reviewed_on")

        rows: list[EvidenceRow] = []
        failures: list[str] = []
        for index, raw in enumerate(raw_rows, start=1):
            try:
                rows.append(EvidenceRow(**raw))
            except ValidationError as error:
                summary = "; ".join(
                    f"{'.'.join(str(p) for p in d['loc'])}: {d['msg']}" for d in error.errors()
                )
                failures.append(f"  row {index}: {summary}")
        if failures:
            raise BatchError(f"{path.name} has invalid rows:\n" + "\n".join(failures))

        batches.append(
            Batch(
                path=path,
                rows=tuple(rows),
                approved=approved,
                reviewed_on=str(reviewed_on) if reviewed_on else None,
            )
        )
    return batches


def _reject_duplicates(rows: Sequence[EvidenceRow]) -> None:
    """The same cell twice would make the outcome depend on row order."""
    cells = [(r.condition_id, r.feature_id, r.value) for r in rows]
    duplicates = sorted({c for c in cells if cells.count(c) > 1})
    if duplicates:
        shown = "; ".join(f"({a}, {b}, {c})" for a, b, c in duplicates)
        raise BatchError(f"the same (condition, feature, value) appears more than once: {shown}")


def write_rows(rows: Iterable[EvidenceRow], destination: Path) -> int:
    """Write the CSV, sorted. Returns the number of rows written."""
    ordered = sorted(rows, key=lambda r: (r.condition_id, r.feature_id, r.value))

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in ordered:
            writer.writerow(
                [
                    row.condition_id,
                    row.feature_id,
                    row.value,
                    row.strength.value,
                    row.source_id,
                    row.source_quote,
                    row.note,
                ]
            )
    return len(ordered)


def build_evidence_csv(batch_dir: Path, destination: Path) -> tuple[int, list[Batch]]:
    """Load every batch, check the approved ones together, and write the CSV.

    **Only approved batches contribute rows.** Drafts are parsed and validated
    so faults surface early, then excluded. This is what makes it safe to draft
    clinical rows ahead of review: an unread batch cannot reach the knowledge
    base, whatever anyone forgets.

    Nothing is written unless every row in every batch is valid, so a failed
    build leaves the previous CSV intact.
    """
    batches = load_batches(batch_dir)
    rows = [row for batch in batches if batch.approved for row in batch.rows]
    _reject_duplicates(rows)
    return write_rows(rows, destination), batches
