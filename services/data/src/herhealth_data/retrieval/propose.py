"""Propose candidate evidence rows by retrieval, for a human to approve.

The knowledge base has 89 rows drawn from 49 cleaned documents. Finding the rest
by reading every page again does not scale, and it is the reason elimination
barely works: eight of twelve conditions have no eliminating rows at all.

This module does the **finding**. A person still does the **judging**.

    for each (condition, feature, value) with no row yet:
        query the index
        write the top candidates into a DRAFT batch, approved: false

What this deliberately does NOT do
----------------------------------
**It does not assign a strength.** Deciding whether a sentence is
``strong_support`` or ``weak_support`` — or nothing at all — is the reading
comprehension the verification protocol exists to perform, and it is the one
step that must not be automated. Every proposal is written with a placeholder
that fails validation until a human replaces it, so a draft batch cannot be
approved by accident.

**It does not write to evidence.csv.** Output is a draft batch file with
``approved: false``, which contributes nothing until reviewed. The existing gate
is unchanged: retrieval widens the funnel, it does not open a side door.

**It does not judge relevance.** A similarity score says two pieces of text are
alike, not that one supports a clinical claim. Scores are printed so a reviewer
can triage, never to filter silently.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from herhealth_contracts.knowledge import Condition, Feature, KnowledgeBase

from herhealth_data.retrieval.embed import Embedder
from herhealth_data.retrieval.index import Hit, PassageIndex
from herhealth_data.retrieval.passages import Passage

__all__ = ["Gap", "Proposal", "find_gaps", "propose_rows", "render_batch"]

#: Written into every proposed row in place of a strength. It is not a member of
#: EvidenceStrength, so a batch still carrying it fails to load — which is the
#: point: the one judgement that must be human cannot be skipped silently.
NEEDS_REVIEW = "TODO_REVIEW"

#: Below this cosine score a hit is noise rather than a weak candidate. Chosen
#: by us, like every other threshold, and adjustable per run.
DEFAULT_MIN_SCORE = 0.30


@dataclass(frozen=True, slots=True)
class Gap:
    """A (condition, feature, value) cell with no evidence row."""

    condition: Condition
    feature: Feature
    value: str

    def query(self) -> str:
        """What to ask the index.

        Deliberately phrased the way a source would state it — "symptoms of X
        include Y" — because we are searching prose written for patients, not
        matching identifiers. The feature *label* is used rather than its id, so
        ``pelvic_pain_severity`` becomes "severity of pelvic pain".
        """
        return f"{self.condition.label}: {self.feature.label}, {self.value.replace('_', ' ')}"


@dataclass(frozen=True, slots=True)
class Proposal:
    gap: Gap
    passage: Passage
    score: float


def find_gaps(base: KnowledgeBase, condition_ids: Sequence[str] | None = None) -> list[Gap]:
    """Every cell a row could occupy but does not.

    Restricted to values that already appear somewhere in the evidence grid.
    A value no row anywhere uses is usually one the sources do not discuss, and
    proposing rows for all of them would bury the reviewer in cells that were
    empty for a good reason.
    """
    existing = {(row.condition_id, row.feature_id, row.value) for row in base.evidence}
    values_in_use: dict[str, set[str]] = {}
    for row in base.evidence:
        values_in_use.setdefault(row.feature_id, set()).add(row.value)

    wanted = set(condition_ids) if condition_ids else {c.id for c in base.conditions}
    features = base.features_by_id

    gaps: list[Gap] = []
    for condition in base.conditions:
        if condition.id not in wanted:
            continue
        for feature_id, values in values_in_use.items():
            feature = features.get(feature_id)
            if feature is None:
                continue
            for value in sorted(values):
                if (condition.id, feature_id, value) not in existing:
                    gaps.append(Gap(condition=condition, feature=feature, value=value))
    return gaps


def propose_rows(
    base: KnowledgeBase,
    index: PassageIndex,
    embedder: Embedder,
    *,
    condition_ids: Sequence[str] | None = None,
    per_gap: int = 2,
    min_score: float = DEFAULT_MIN_SCORE,
    limit: int = 10,
    cited_sources_only: bool = True,
) -> list[Proposal]:
    """Retrieve candidate sentences for the gaps in the grid.

    ``limit`` defaults to 10 because the review gate caps a batch at ten rows.
    Producing more than a reviewer has agreed to read is how unreviewed rows
    start to accumulate.

    ``cited_sources_only`` keeps candidates within the sources a condition
    already cites. A source that has never been used for a condition may simply
    not cover it, and a sentence pulled from an unrelated page is the most
    likely way a plausible-but-wrong row gets proposed.
    """
    proposals: list[Proposal] = []

    for gap in find_gaps(base, condition_ids):
        allowed = set(gap.condition.source_ids) if cited_sources_only else None

        def keep(passage: Passage, allowed: set[str] | None = allowed) -> bool:
            return allowed is None or passage.source_id in allowed

        hits: list[Hit] = index.search(
            gap.query(), embedder, k=per_gap, where=keep, min_score=min_score
        )
        proposals.extend(
            Proposal(gap=gap, passage=hit.passage, score=hit.score) for hit in hits
        )

    proposals.sort(key=lambda p: -p.score)
    return proposals[:limit]


def _wrap(text: str, width: int = 74, indent: str = "      ") -> Iterator[str]:
    words = text.split()
    line = ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            yield indent + line
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        yield indent + line


def render_batch(proposals: Sequence[Proposal], *, batch: str, model_name: str) -> str:
    """Write a DRAFT batch file, in the same shape as a hand-authored one."""
    lines = [
        f"# Batch {batch} — RETRIEVAL-PROPOSED DRAFT. Not reviewed, not approved.",
        "#",
        f"# Candidates found by semantic search over build/clean/ using {model_name}.",
        "# Retrieval found these sentences; it did NOT judge them. Every row below",
        "# needs a human to do three things before this batch can be approved:",
        "#",
        f"#   1. Replace {NEEDS_REVIEW} with a real strength, or delete the row.",
        "#      A batch still containing the placeholder will not load.",
        "#   2. Confirm the quote genuinely supports the claim as written. A high",
        "#      similarity score means the text is alike, not that it is evidence.",
        "#   3. Check the quote is the whole relevant sentence, and trim nothing",
        "#      from it — `make verify-quotes` requires it verbatim.",
        "#",
        "# Delete freely. A rejected proposal costs nothing; a wrong row costs a",
        "# user the right advice.",
        "",
        f"batch: '{batch}'",
        f"covers: [{', '.join(sorted({p.gap.condition.id for p in proposals}))}]",
        "",
        "approved: false",
        "",
        "rows:",
    ]

    for proposal in proposals:
        gap = proposal.gap
        lines += [
            f"  # {gap.condition.id} · {gap.feature.label.lower()} = {gap.value}",
            f"  #   retrieval score {proposal.score:.3f} · {proposal.passage.citation}",
            f"  - condition_id: {gap.condition.id}",
            f"    feature_id: {gap.feature.id}",
            f"    value: {gap.value}",
            f"    strength: {NEEDS_REVIEW}",
            f"    source_id: {proposal.passage.source_id}",
            "    source_quote: >-",
            *_wrap(proposal.passage.text),
            "",
        ]

    if not proposals:
        lines += ["  # Nothing cleared the score threshold. Try --min-score lower,", "  # or the gap is genuinely uncovered by the cited sources.", ""]

    return "\n".join(lines)


def write_batch(proposals: Sequence[Proposal], path: Path, *, model_name: str) -> None:
    batch = path.stem.replace("batch_", "").split("_")[0] or "draft"
    path.write_text(
        render_batch(proposals, batch=batch, model_name=model_name), encoding="utf-8"
    )
