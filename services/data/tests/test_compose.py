"""Tests for the prose channel's source cap, widening and licence filter.

Uses ``HashingEmbedder`` throughout — these are tests of the selection
plumbing, not of retrieval quality, and that module's own docstring is
explicit that judging quality needs the real model and belongs in an
evaluation rather than a unit test.
"""

from __future__ import annotations

from herhealth_data.retrieval.compose import balanced_search
from herhealth_data.retrieval.embed import HashingEmbedder
from herhealth_data.retrieval.index import build_index
from herhealth_data.retrieval.passages import Passage


def passage(
    source_id: str,
    slug: str,
    text: str,
    *,
    may_be_ingested: bool = True,
    heading: str = "Symptoms",
) -> Passage:
    return Passage(
        source_id=source_id,
        slug=slug,
        heading=heading,
        section_type="other",
        text=text,
        may_be_ingested=may_be_ingested,
    )


def index_of(*passages: Passage):
    return build_index(passages, HashingEmbedder())


# -- per-source cap ---------------------------------------------------------


def test_no_source_may_exceed_the_cap() -> None:
    """The corpus is 64% one source; uncapped, top-k is mostly that source."""
    dominant = [
        passage("bigsource", f"page{i}", f"pelvic pain and bleeding number {i} here")
        for i in range(10)
    ]
    other = [passage("smallsource", "page0", "pelvic pain and bleeding elsewhere entirely")]
    hits = balanced_search(index_of(*dominant, *other), "pelvic pain bleeding",
                           HashingEmbedder(), k=4, per_source_cap=2)

    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit.passage.source_id] = counts.get(hit.passage.source_id, 0) + 1
    assert counts["bigsource"] == 2
    assert counts["smallsource"] == 1


def test_the_cap_is_applied_during_selection_so_k_is_still_filled() -> None:
    """Capping after ranking would return fewer than k; capping during does not."""
    passages = [
        passage("a", f"p{i}", f"pelvic pain bleeding variant {i}") for i in range(5)
    ] + [passage("b", f"p{i}", f"pelvic pain bleeding variant {i}") for i in range(5)]
    hits = balanced_search(index_of(*passages), "pelvic pain bleeding",
                           HashingEmbedder(), k=4, per_source_cap=2)
    assert len(hits) == 4


def test_an_uncapped_search_is_still_possible() -> None:
    passages = [passage("a", f"p{i}", f"pelvic pain bleeding {i}") for i in range(5)]
    hits = balanced_search(index_of(*passages), "pelvic pain bleeding",
                           HashingEmbedder(), k=3, per_source_cap=99)
    assert len(hits) == 3


# -- widening ---------------------------------------------------------------


def test_a_hit_is_widened_to_its_neighbours_in_the_same_document() -> None:
    passages = [
        passage("a", "doc", "First sentence about something else."),
        passage("a", "doc", "The pelvic pain sentence that matches the query."),
        passage("a", "doc", "Third sentence giving the context that follows."),
    ]
    (hit,) = balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=1)

    assert hit.passage.text == "The pelvic pain sentence that matches the query."
    assert hit.context_text.startswith("First sentence")
    assert hit.context_text.endswith("that follows.")


def test_widening_never_crosses_a_document_boundary() -> None:
    """A window that leaked across documents would attribute one source's
    sentence to another's citation."""
    passages = [
        passage("a", "doc_one", "Tail of the first document entirely unrelated."),
        passage("a", "doc_two", "The pelvic pain sentence that matches the query."),
        passage("b", "doc_three", "Head of a third document from another source."),
    ]
    (hit,) = balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=1)
    assert hit.context_text == "The pelvic pain sentence that matches the query."


def test_the_hit_text_is_never_altered_by_widening() -> None:
    """``context_text`` is for display; ``passage.text`` is what verifies
    verbatim against the cleaned document, so it must survive untouched."""
    original = "The pelvic pain sentence that matches the query."
    passages = [
        passage("a", "doc", "Preceding sentence."),
        passage("a", "doc", original),
        passage("a", "doc", "Following sentence."),
    ]
    (hit,) = balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=1)
    assert hit.passage.text == original
    assert original in hit.context_text


def test_window_zero_returns_the_sentence_alone() -> None:
    passages = [
        passage("a", "doc", "Preceding sentence."),
        passage("a", "doc", "The pelvic pain sentence."),
        passage("a", "doc", "Following sentence."),
    ]
    (hit,) = balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=1, window=0)
    assert hit.context_text == "The pelvic pain sentence."


# -- licence ----------------------------------------------------------------


def test_a_quote_only_passage_can_never_be_returned() -> None:
    """NHS is citable but not servable, and 707 of 4,454 indexed passages are
    NHS. The filter is restated here rather than left to the caller so a
    passage that may not be served cannot reach a result set by another path.
    """
    passages = [
        passage("nhs", "doc", "pelvic pain exactly matching the query", may_be_ingested=False),
        passage("wh", "doc", "pelvic pain also matching the query"),
    ]
    hits = balanced_search(index_of(*passages), "pelvic pain matching query",
                           HashingEmbedder(), k=8)
    assert [h.passage.source_id for h in hits] == ["wh"]


def test_an_index_of_only_quote_only_passages_returns_nothing() -> None:
    passages = [passage("nhs", "doc", "pelvic pain", may_be_ingested=False)]
    assert balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=8) == []


def test_a_quote_only_neighbour_is_not_pulled_in_by_widening() -> None:
    """Widening must not do what the filter forbids."""
    passages = [
        passage("nhs", "doc", "Crown copyright text that may not be served.",
                may_be_ingested=False),
        passage("wh", "doc", "The pelvic pain sentence that matches."),
    ]
    (hit,) = balanced_search(index_of(*passages), "pelvic pain", HashingEmbedder(), k=1)
    assert "Crown copyright" not in hit.context_text


# -- guards -----------------------------------------------------------------


def test_an_empty_index_returns_nothing() -> None:
    assert balanced_search(index_of(), "pelvic pain", HashingEmbedder(), k=8) == []


def test_searching_with_a_different_model_than_built_the_index_raises() -> None:
    index = build_index([passage("a", "doc", "pelvic pain")], HashingEmbedder(dimensions=64))
    try:
        balanced_search(index, "pelvic pain", HashingEmbedder(dimensions=128), k=1)
    except ValueError as error:
        assert "rebuild it" in str(error)
    else:  # pragma: no cover - the assertion above is the point
        raise AssertionError("a model mismatch must raise, not return wrong vectors")
