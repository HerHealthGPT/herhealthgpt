"""The recall check, with a scripted retrieval client. The knowledge base is
the real tracked one; no index and no endpoint are involved."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from herhealth_contracts.knowledge import EvidenceRow, KnowledgeBase
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage

from herhealth_backend.evaluation.retrieval_eval import build_query, evaluate

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def base() -> KnowledgeBase:
    return load_knowledge_base(REPO / "knowledge")


def _hit(name: str, text: str, row: EvidenceRow | None = None) -> RetrievedPassage:
    return RetrievedPassage(
        id=hashlib.sha256(name.encode()).hexdigest()[:16],
        passage_type=PassageType.EVIDENCE_STATEMENT if row else PassageType.SOURCE_PASSAGE,
        source_id=row.source_id if row else "womenshealth",
        text=text,
        citation=name,
        score=0.5,
        condition_id=row.condition_id if row else None,
        feature_id=row.feature_id if row else None,
        value=str(row.value) if row else None,
        strength=row.strength.value if row else None,
    )


class Scripted:
    def __init__(self, answers: dict[str, list[RetrievedPassage]]) -> None:
        self._answers = answers

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return self._answers.get(query, [])[:k]


def _ingestable_rows(base: KnowledgeBase) -> list[EvidenceRow]:
    sources = base.sources_by_id
    return [row for row in base.evidence if sources[row.source_id].may_be_ingested]


def test_quote_only_rows_are_excluded_and_counted(base: KnowledgeBase) -> None:
    result = evaluate(base, Scripted({}))
    expected_excluded = len(base.evidence) - len(_ingestable_rows(base))
    assert result.excluded_quote_only == expected_excluded > 0
    assert len(result.rows) == len(_ingestable_rows(base))
    assert result.summary()["sentence"]["recall@8"] == 0.0


def test_ranks_are_found_for_both_targets(base: KnowledgeBase) -> None:
    row = _ingestable_rows(base)[0]
    answers = {
        build_query(base, row): [
            _hit("noise", "An unrelated placeholder sentence about something else."),
            _hit("sentence", row.source_quote),
            _hit("statement", "generated statement containing the quote", row),
        ]
    }
    result = evaluate(base, Scripted(answers))
    scored = next(r for r in result.rows if r.query == build_query(base, row))
    assert scored.sentence_rank == 2
    assert scored.statement_rank == 3


def test_the_statement_does_not_count_as_the_source_sentence(base: KnowledgeBase) -> None:
    # An evidence statement embeds the quote verbatim; it must not satisfy the
    # harder target on its own.
    row = _ingestable_rows(base)[0]
    answers = {build_query(base, row): [_hit("statement", f"wrapper {row.source_quote}", row)]}
    scored = next(
        r for r in evaluate(base, Scripted(answers)).rows if r.query == build_query(base, row)
    )
    assert scored.sentence_rank is None
    assert scored.statement_rank == 1


def test_summary_reports_recall_and_mrr(base: KnowledgeBase) -> None:
    rows = _ingestable_rows(base)
    answers = {build_query(base, rows[0]): [_hit("sentence", rows[0].source_quote)]}
    summary = evaluate(base, Scripted(answers)).summary()
    distinct_queries = len({build_query(base, row) for row in rows})
    assert summary["scored_rows"] == len(rows)
    assert summary["sentence"]["recall@1"] > 0.0
    assert summary["sentence"]["recall@1"] <= 1.0
    assert summary["sentence"]["mrr"] == pytest.approx(summary["sentence"]["recall@1"])
    assert distinct_queries >= 1
