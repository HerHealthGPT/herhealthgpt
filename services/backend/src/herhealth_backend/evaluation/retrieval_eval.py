"""A recall check for retrieval, built from the knowledge base itself.

Every ``evidence.csv`` row pairs a condition and a feature value with the exact
source sentence that supports it. That gives a query (the condition and the
feature, in the labels the knowledge base uses) and two things retrieval
ought to return for it:

* the **source sentence** — a passage of source prose matching the row's
  ``source_quote``;
* the **evidence statement** — the passage generated from that row.

Reported, never gated, and with three limits that travel with every number:
the queries are built from the knowledge base's own labels, not from how
users write; the evidence-statement target is the easier one, because the
statement contains the query's words; and it is English only. The knowledge
base is source-traceable, not clinician-adjudicated. Rows from quote-only
sources (NHS) cannot be scored at all, because their text is not in the
served index; they are counted and reported as excluded.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from herhealth_contracts.knowledge import EvidenceRow, KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

__all__ = ["Evaluation", "RowResult", "build_query", "evaluate", "main"]

RECALL_AT = (1, 3, 8)


class _Retrieval(Protocol):
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]: ...


def build_query(base: KnowledgeBase, row: EvidenceRow) -> str:
    """The condition and the feature value, in the knowledge base's labels."""
    condition = base.conditions_by_id[row.condition_id]
    feature = base.features_by_id[row.feature_id]
    return f"{condition.label}: {feature.label}, {str(row.value).replace('_', ' ')}"


def _normalise(text: str) -> str:
    return " ".join(text.split()).lower()


def _is_source_sentence(passage: RetrievedPassage, quote: str) -> bool:
    if passage.passage_type is not PassageType.SOURCE_PASSAGE:
        return False
    text, wanted = _normalise(passage.text), _normalise(quote)
    return text in wanted or wanted in text


def _is_statement(passage: RetrievedPassage, row: EvidenceRow) -> bool:
    return (
        passage.passage_type is PassageType.EVIDENCE_STATEMENT
        and passage.condition_id == row.condition_id
        and passage.feature_id == row.feature_id
        and passage.value == str(row.value)
        and passage.source_id == row.source_id
    )


@dataclass(frozen=True, slots=True)
class RowResult:
    query: str
    condition_id: str
    feature_id: str
    source_id: str
    #: 1-based rank of the first match, or ``None`` if it was not returned.
    sentence_rank: int | None
    statement_rank: int | None


def _first(matches: Sequence[bool]) -> int | None:
    """1-based position of the first match, or ``None``."""
    return next((position for position, hit in enumerate(matches, start=1) if hit), None)


def _target_summary(ranks: Sequence[int | None]) -> dict[str, float]:
    total = len(ranks) or 1
    summary = {
        f"recall@{cutoff}": sum(1 for r in ranks if r is not None and r <= cutoff) / total
        for cutoff in RECALL_AT
    }
    summary["mrr"] = sum(1.0 / r for r in ranks if r is not None) / total
    return summary


@dataclass(frozen=True, slots=True)
class Evaluation:
    rows: tuple[RowResult, ...]
    excluded_quote_only: int

    def summary(self) -> dict[str, object]:
        return {
            "scored_rows": len(self.rows),
            "excluded_quote_only_rows": self.excluded_quote_only,
            "sentence": _target_summary([row.sentence_rank for row in self.rows]),
            "statement": _target_summary([row.statement_rank for row in self.rows]),
        }


def evaluate(base: KnowledgeBase, retrieval: _Retrieval, *, k: int = max(RECALL_AT)) -> Evaluation:
    sources = base.sources_by_id
    results: list[RowResult] = []
    excluded = 0
    for row in base.evidence:
        if not sources[row.source_id].may_be_ingested:
            excluded += 1
            continue
        query = build_query(base, row)
        hits = retrieval.search(query, k=k)
        results.append(
            RowResult(
                query=query,
                condition_id=row.condition_id,
                feature_id=row.feature_id,
                source_id=row.source_id,
                sentence_rank=_first([_is_source_sentence(h, row.source_quote) for h in hits]),
                statement_rank=_first([_is_statement(h, row) for h in hits]),
            )
        )
    return Evaluation(rows=tuple(results), excluded_quote_only=excluded)


def _print(label: str, summary: dict[str, object]) -> None:
    print(
        f"\n{label}: {summary['scored_rows']} rows scored, "
        f"{summary['excluded_quote_only_rows']} quote-only rows excluded"
    )
    for target in ("sentence", "statement"):
        numbers = summary[target]
        assert isinstance(numbers, dict)
        cells = "  ".join(f"{name}={value:.3f}" for name, value in numbers.items())
        print(f"  {target:<10} {cells}")


def main(argv: Sequence[str] | None = None) -> int:
    from herhealth_backend.triage.retrieval import LangChainRetrievalClient, RetrievalSettings

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--knowledge", type=Path, default=Path("knowledge"))
    parser.add_argument("--out", type=Path, default=Path("build/retrieval_eval.json"))
    parser.add_argument("-k", type=int, default=max(RECALL_AT))
    args = parser.parse_args(argv)

    base = load_knowledge_base(args.knowledge)
    settings = RetrievalSettings.from_env()
    report: dict[str, object] = {"index_dir": str(settings.index_dir), "k": args.k}
    for label, rerank in (("reranker_on", True), ("reranker_off", False)):
        client = LangChainRetrievalClient.from_settings(settings, rerank=rerank)
        summary = evaluate(base, client, k=args.k).summary()
        report[label] = summary
        _print(label, summary)

    print(
        "\nQueries are built from the knowledge base's own labels, in English only; "
        "the statement target is the easier one.\nThe knowledge base is "
        "source-traceable, not clinician-adjudicated. Reported, not gated."
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
