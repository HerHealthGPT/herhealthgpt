"""Render the knowledge base as flat tables.

Every knowledge file is conceptually a table, but three of them hold nested
fields — a feature's ``probe`` is a map and its ``allowed_values`` a list; a
red-flag rule holds a list of clauses. YAML is the storage format because it
represents that nesting natively. This module produces the *flat* view: one row
per entity, nesting collapsed into a single readable cell.

The exports are **generated and disposable**. They live in ``build/tables/``,
which is gitignored, and nothing reads them back. Editing one changes nothing —
edit the YAML and regenerate. Keeping them out of git is deliberate: two
representations of the same data in version control is two things to keep in
sync, and one of them would eventually be wrong.

What they are for: reading a whole file at a glance, reviewing a batch against
the features it references, diffing two builds, and pasting into a report.

Nested values are joined with ``NESTED_SEPARATOR`` rather than commas, so a CSV
cell never needs escaping to be read, and a value containing a comma stays
unambiguous.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from herhealth_contracts.knowledge import (
    ComparisonOp,
    Condition,
    EvidenceRow,
    Feature,
    KnowledgeBase,
    RedFlagRule,
    Source,
)

__all__ = ["NESTED_SEPARATOR", "Table", "build_tables", "write_csvs", "write_markdown"]

#: Joins list and map values inside one cell. Chosen over a comma so a CSV cell
#: is unambiguous, and over a newline so a row stays on one line.
NESTED_SEPARATOR: Final[str] = " | "

#: Cells longer than this are truncated in the Markdown view only. The CSV
#: always carries the full value — truncating a source_quote would make it
#: unusable as provenance.
MARKDOWN_CELL_LIMIT: Final[int] = 90


@dataclass(frozen=True, slots=True)
class Table:
    """One flat view of one knowledge file."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    caption: str = ""

    def __len__(self) -> int:
        return len(self.rows)


# --------------------------------------------------------------------------
# Per-entity flattening
# --------------------------------------------------------------------------


def _features_table(features: Sequence[Feature]) -> Table:
    return Table(
        name="features",
        columns=("id", "label", "kind", "allowed_values", "burden", "probe_en", "note"),
        rows=tuple(
            (
                f.id,
                f.label,
                f.kind.value,
                NESTED_SEPARATOR.join(f.allowed_values),
                str(f.burden),
                f.probe.get("en", ""),
                f.note,
            )
            for f in sorted(features, key=lambda f: f.id)
        ),
        caption="Everything the system may ask about. `unknown` is implicit on every row.",
    )


def _conditions_table(conditions: Sequence[Condition]) -> Table:
    return Table(
        name="conditions",
        columns=("id", "label", "icd11", "baseline_action", "source_ids", "note"),
        rows=tuple(
            (
                c.id,
                c.label,
                c.icd11,
                c.baseline_action.value,
                NESTED_SEPARATOR.join(c.source_ids),
                c.note,
            )
            for c in sorted(conditions, key=lambda c: c.id)
        ),
        caption="Everything the system may consider. Considering is not asserting.",
    )


def _render_clause(feature_id: str, op: ComparisonOp, value: object) -> str:
    if isinstance(value, tuple):
        rendered = "[" + ", ".join(str(v) for v in value) + "]"
    else:
        rendered = str(value)
    return f"{feature_id} {op.value} {rendered}"


def _red_flags_table(rules: Sequence[RedFlagRule]) -> Table:
    return Table(
        name="red_flags",
        columns=("id", "action", "label", "conditions", "source_id", "source_quote", "note"),
        rows=tuple(
            (
                r.id,
                r.action.value,
                r.label,
                " AND ".join(_render_clause(c.feature_id, c.op, c.value) for c in r.all_of),
                r.source_id,
                r.source_quote,
                r.note,
            )
            # Most urgent first: these are read to check escalation coverage.
            for r in sorted(rules, key=lambda r: (r.action.value != "EMERGENCY", r.id))
        ),
        caption="Deterministic escalation rules, evaluated before any model call.",
    )


def _sources_table(sources: Sequence[Source]) -> Table:
    return Table(
        name="sources",
        columns=("id", "precedence", "status", "may_cite", "may_ingest", "name", "licence"),
        rows=tuple(
            (
                s.id,
                str(s.precedence),
                s.status.value,
                "yes" if s.may_be_cited else "no",
                "yes" if s.may_be_ingested else "no",
                s.name,
                s.licence,
            )
            for s in sorted(sources, key=lambda s: (s.precedence, s.id))
        ),
        caption="Lower precedence wins on conflict. Status decides whether a source is usable.",
    )


def _evidence_table(rows: Sequence[EvidenceRow]) -> Table:
    return Table(
        name="evidence",
        columns=("condition_id", "feature_id", "value", "strength", "source_id", "source_quote"),
        rows=tuple(
            (r.condition_id, r.feature_id, r.value, r.strength.value, r.source_id, r.source_quote)
            for r in sorted(rows, key=lambda r: (r.condition_id, r.feature_id, r.value))
        ),
        caption="The sparse grid. A missing cell means neutral.",
    )


def _constants_table(base: KnowledgeBase) -> Table:
    """weights.yaml and actions.yaml as one key/value table.

    Neither is a list of entities, so a row-per-entity view makes no sense.
    Both are constants we chose, which is what this table records.
    """
    weights = base.weights
    rows: list[tuple[str, str, str]] = [
        ("weights", f"log_odds.{strength.value}", f"{value:+g}")
        for strength, value in weights.log_odds.items()
    ]
    rows += [
        ("weights", "plausibility_floor", str(weights.plausibility_floor)),
        ("weights", "stop_confidence", str(weights.stop_confidence)),
        ("weights", "self_care_stop_confidence", str(weights.self_care_stop_confidence)),
        ("weights", "stop_margin", str(weights.stop_margin)),
        ("weights", "max_questions", str(weights.max_questions)),
    ]
    rows += [
        ("actions", f"severity.{a.code.value}", str(a.severity))
        for a in sorted(base.actions.actions, key=lambda a: a.severity)
    ]
    return Table(
        name="constants",
        columns=("file", "key", "value"),
        rows=tuple(rows),
        caption="Set by us, not measured. Tune against the evaluation set.",
    )


def build_tables(base: KnowledgeBase) -> list[Table]:
    """Every knowledge file as a flat table, in reading order."""
    return [
        _conditions_table(base.conditions),
        _features_table(base.features),
        _evidence_table(base.evidence),
        _red_flags_table(base.red_flags),
        _sources_table(base.sources),
        _constants_table(base),
    ]


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def write_csvs(tables: Sequence[Table], directory: Path) -> list[Path]:
    """One CSV per table. Full values, never truncated."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for table in tables:
        path = directory / f"{table.name}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(table.columns)
            writer.writerows(table.rows)
        written.append(path)
    return written


def _escape_markdown(cell: str) -> str:
    """Pipes would break the table; newlines would break the row."""
    flattened = cell.replace("\n", " ").replace("|", "\\|")
    if len(flattened) > MARKDOWN_CELL_LIMIT:
        return flattened[: MARKDOWN_CELL_LIMIT - 1].rstrip() + "…"
    return flattened


def write_markdown(tables: Sequence[Table], path: Path) -> Path:
    """One document, all tables. For reading and for pasting into a report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Knowledge base",
        "",
        "Generated by `make tables`. Do not edit — edit the YAML and regenerate.",
        "",
        "Long cells are truncated here for readability. The CSV exports alongside",
        "this file carry the full values.",
        "",
    ]
    for table in tables:
        lines += [f"## {table.name} ({len(table)} rows)", ""]
        if table.caption:
            lines += [f"*{table.caption}*", ""]
        lines.append("| " + " | ".join(table.columns) + " |")
        lines.append("|" + "|".join("---" for _ in table.columns) + "|")
        lines += [
            "| " + " | ".join(_escape_markdown(cell) for cell in row) + " |" for row in table.rows
        ]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
