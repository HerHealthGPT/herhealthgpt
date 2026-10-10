"""Readable views of the evidence grid, one card per condition and per feature.

``tables.py`` flattens each knowledge file into one row per entity. That answers
"what is in ``features.yaml``" and does not answer the two questions anyone
authoring or reviewing the grid actually has:

* **What do we believe about this condition, and on whose authority?** Today
  that means finding a condition's rows among 140 and reading its quotes.
* **What does each ANSWER to this question point at?** That one has no view at
  all, and it is the question that matters most, because it is where the grid's
  ability to tell conditions apart lives or dies.

The feature card exists to make one specific weakness visible. A feature
authored at a single value — ``abnormal_discharge = yes`` and nothing else —
raises every condition that has a row and lowers none, so asking it costs a
turn and narrows nothing. A feature authored across its values
(``discharge_smell``: ``fishy`` points one way, ``none`` the other) does real
work. Measured 2026-09-11: **10 of 32 authored features discriminate by value,
22 are presence-only.** The cards put that number in front of whoever is
deciding what to author next, instead of leaving it to be re-derived.

Generated and disposable, exactly like ``tables.py``: they live under
``build/``, nothing reads them back, and editing one changes nothing.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from herhealth_contracts.knowledge import (
    EvidenceRow,
    EvidenceStrength,
    KnowledgeBase,
)

__all__ = [
    "FeatureReport",
    "feature_reports",
    "render_condition_cards",
    "render_feature_cards",
    "write_cards",
]

#: Strengths that raise a condition. The rest lower it.
_SUPPORTING = {EvidenceStrength.STRONG_SUPPORT, EvidenceStrength.WEAK_SUPPORT}


@dataclass(frozen=True, slots=True)
class FeatureReport:
    """What one feature's answers point at, and whether that separates anything."""

    feature_id: str
    label: str
    burden: int
    #: value -> the rows authored at that value
    by_value: dict[str, list[EvidenceRow]]
    #: Values in ``allowed_values`` with no row at all.
    unauthored_values: tuple[str, ...]

    @property
    def discriminates(self) -> bool:
        """True when different answers point at different conditions.

        Two distinct authored values is the bar. One value means every answer
        that matches raises the same set and no answer lowers anything.
        """
        return len(self.by_value) > 1

    @property
    def conditions_touched(self) -> int:
        return len({row.condition_id for rows in self.by_value.values() for row in rows})


def feature_reports(base: KnowledgeBase) -> list[FeatureReport]:
    """One report per feature that carries at least one evidence row.

    Features with no rows are left out rather than shown empty: seven of them
    are red-flag-only by design (see CLAUDE.md) and listing them as gaps would
    invite someone to "fill them in", which is exactly wrong.
    """
    rows_by_feature: dict[str, list[EvidenceRow]] = defaultdict(list)
    for row in base.evidence:
        rows_by_feature[row.feature_id].append(row)

    reports: list[FeatureReport] = []
    for feature_id, rows in rows_by_feature.items():
        feature = base.features_by_id.get(feature_id)
        if feature is None:
            continue
        by_value: dict[str, list[EvidenceRow]] = defaultdict(list)
        for row in rows:
            by_value[row.value].append(row)
        reports.append(
            FeatureReport(
                feature_id=feature_id,
                label=feature.label,
                burden=feature.burden,
                by_value={v: sorted(r, key=lambda x: x.condition_id) for v, r in by_value.items()},
                unauthored_values=tuple(
                    v for v in feature.allowed_values if v not in by_value
                ),
            )
        )
    # Presence-only first: that is the work list.
    return sorted(reports, key=lambda r: (r.discriminates, -r.conditions_touched, r.feature_id))


def _arrow(row: EvidenceRow) -> str:
    return "raises" if row.strength in _SUPPORTING else "lowers"


def render_feature_cards(base: KnowledgeBase) -> str:
    """One card per feature: what each answer points at."""
    reports = feature_reports(base)
    discriminating = [r for r in reports if r.discriminates]
    presence_only = [r for r in reports if not r.discriminates]

    lines = [
        "# What each answer points at",
        "",
        "Generated from `knowledge/evidence.csv`. Nothing reads this back.",
        "",
        f"**{len(discriminating)} of {len(reports)} authored features separate conditions "
        f"by answer. {len(presence_only)} are presence-only.**",
        "",
        "A presence-only feature is authored at a single value, so every answer that "
        "matches raises the same conditions and no answer lowers anything. Asking it "
        "costs a turn and narrows nothing. These are the rows worth authoring next — "
        "and the other values are usually stated plainly by a source already fetched, "
        "so they need no new source and no negative inference.",
        "",
    ]

    for heading, group in (
        ("## Presence-only — the work list", presence_only),
        ("## Already separating", discriminating),
    ):
        lines.append(heading)
        lines.append("")
        for report in group:
            lines.append(
                f"### `{report.feature_id}` — {report.label}  "
                f"_(burden {report.burden}, {report.conditions_touched} conditions)_"
            )
            for value, rows in sorted(report.by_value.items()):
                lines.append(f"- **{value}**")
                for row in rows:
                    lines.append(
                        f"    - {_arrow(row)} `{row.condition_id}` "
                        f"({row.strength.value}, {row.source_id}) — "
                        f'"{row.source_quote}"'
                    )
            if report.unauthored_values:
                lines.append(
                    f"- _no rows authored for:_ {', '.join(report.unauthored_values)}"
                )
            lines.append("")
    return "\n".join(lines)


def render_condition_cards(base: KnowledgeBase) -> str:
    """One card per condition: everything believed about it, and on whose authority."""
    rows_by_condition: dict[str, list[EvidenceRow]] = defaultdict(list)
    for row in base.evidence:
        rows_by_condition[row.condition_id].append(row)

    lines = [
        "# What we believe about each condition",
        "",
        "Generated from `knowledge/evidence.csv`. Nothing reads this back.",
        "",
    ]
    for condition in sorted(base.conditions, key=lambda c: c.id):
        rows = sorted(rows_by_condition.get(condition.id, []), key=lambda r: r.feature_id)
        supporting = [r for r in rows if r.strength in _SUPPORTING]
        against = [r for r in rows if r.strength not in _SUPPORTING]
        sources = ", ".join(sorted({r.source_id for r in rows})) or "—"

        lines.append(f"## `{condition.id}` — {condition.label}")
        lines.append("")
        lines.append(
            f"Baseline urgency **{condition.baseline_action.value}** · "
            f"{len(rows)} row(s) · sources: {sources}"
        )
        if condition.single_source_reason:
            lines.append("")
            lines.append(f"> Single-source exception: {condition.single_source_reason}")
        lines.append("")
        if not rows:
            lines.append("_No evidence rows._")
            lines.append("")
            continue
        for title, group in (("Points towards", supporting), ("Points away", against)):
            if not group:
                continue
            lines.append(f"**{title}**")
            for row in group:
                lines.append(
                    f"- `{row.feature_id}` = **{row.value}** "
                    f"({row.strength.value}, {row.source_id}) — "
                    f'"{row.source_quote}"'
                )
            lines.append("")
    return "\n".join(lines)


def write_cards(base: KnowledgeBase, directory: Path) -> list[Path]:
    """Write both card sets. Returns the paths written."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (
        ("by-answer.md", render_feature_cards(base)),
        ("by-condition.md", render_condition_cards(base)),
    ):
        path = directory / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written
