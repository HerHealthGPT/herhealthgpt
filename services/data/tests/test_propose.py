"""The evidence-proposal tool over the new store. It reads the real knowledge
base (tracked, offline) and a synthetic index, so no source text is needed."""

from __future__ import annotations

from herhealth_data import paths
from herhealth_data.knowledge import load_knowledge_base
from herhealth_data.retrieval.passages import Passage
from herhealth_data.retrieval.propose import find_gaps, propose_rows
from herhealth_data.retrieval.vectorstore import HashingEmbeddings, PassageStore, to_indexed


def _store_for(text: str, source_id: str) -> PassageStore:
    passage = Passage(source_id=source_id, slug="page", heading="", section_type="other", text=text)
    return PassageStore.build(
        [to_indexed(passage, {})],
        HashingEmbeddings(),
        embedding_model="hashing-256",
        query_formatter=lambda query: query,
    )


def _first_gap():  # type: ignore[no-untyped-def]
    base, problems = load_knowledge_base(paths.KNOWLEDGE_DIR)
    assert base is not None, problems
    condition = next(c for c in base.conditions if c.source_ids)
    gap = find_gaps(base, [condition.id])[0]
    return base, condition, gap


def test_a_matching_sentence_from_a_cited_source_is_proposed() -> None:
    base, condition, gap = _first_gap()
    # The gap's own query, which is built from labels: nothing clinical is written here.
    store = _store_for(gap.query() + " placeholder", condition.source_ids[0])
    proposals = propose_rows(base, store, condition_ids=[condition.id], limit=1)
    assert len(proposals) == 1
    assert proposals[0].gap == gap
    assert proposals[0].passage.source_id == condition.source_ids[0]


def test_a_sentence_from_an_uncited_source_is_not_proposed() -> None:
    base, condition, gap = _first_gap()
    outsider = next(s.id for s in base.sources if s.id not in condition.source_ids)
    store = _store_for(gap.query() + " placeholder", outsider)
    assert propose_rows(base, store, condition_ids=[condition.id], limit=1) == []
