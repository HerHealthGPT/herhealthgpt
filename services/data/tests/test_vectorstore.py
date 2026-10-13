"""The retrieval index, offline: the hashing stand-in replaces the embedding
model, so these test plumbing and never retrieval quality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from herhealth_contracts.retrieval import (
    INDEX_FILE,
    MANIFEST_FILE,
    PASSAGES_FILE,
    IndexedPassage,
    PassageType,
)
from langchain_core.embeddings import Embeddings

from herhealth_data.retrieval.passages import Passage
from herhealth_data.retrieval.vectorstore import (
    HashingEmbeddings,
    PassageStore,
    read_manifest,
    to_indexed,
)


def _identity(query: str) -> str:
    return query


def _passage(text: str, *, source: str = "womenshealth", ingestable: bool = True) -> Passage:
    return Passage(
        source_id=source,
        slug="page",
        heading="Heading",
        section_type="other",
        text=text,
        may_be_ingested=ingestable,
    )


def _evidence(text: str) -> Passage:
    return Passage(
        source_id="womenshealth",
        slug="evidence/alpha/beta/yes",
        heading="",
        section_type="evidence",
        text=text,
        passage_type=PassageType.EVIDENCE_STATEMENT.value,
        condition_id="alpha",
        feature_id="beta",
        value="yes",
        strength="weak_support",
    )


URLS = {("womenshealth", "page"): "https://example.org/page"}

LIBRARY = "The library opens at nine every morning without exception."
TOMATO = "Tomatoes grow best in warm weather with plenty of sunlight."
STATEMENT = "A placeholder statement about opening hours at the library."


def _store(*passages: Passage) -> PassageStore:
    indexed = [to_indexed(p, URLS) for p in passages]
    return PassageStore.build(
        indexed, HashingEmbeddings(), embedding_model="hashing-256", query_formatter=_identity
    )


def test_to_indexed_resolves_the_url_and_keeps_the_stable_id() -> None:
    passage = _passage(LIBRARY)
    indexed = to_indexed(passage, URLS)
    assert indexed.id == passage.id
    assert indexed.url == "https://example.org/page"
    assert indexed.citation == passage.citation


def test_search_returns_the_lexically_closest_passage_first() -> None:
    hits = _store(_passage(LIBRARY), _passage(TOMATO)).search("library opens morning", k=2)
    assert [hit.passage.text for hit in hits] == [LIBRARY, TOMATO]
    assert hits[0].score > hits[1].score


def test_where_filters_before_ranking() -> None:
    store = _store(_passage(LIBRARY), _passage(TOMATO), _evidence(STATEMENT))
    hits = store.search(
        "library opens morning",
        k=1,
        where=lambda p: p.passage_type is PassageType.EVIDENCE_STATEMENT,
    )
    assert [hit.passage.text for hit in hits] == [STATEMENT]


def test_min_score_drops_weak_hits() -> None:
    hits = _store(_passage(LIBRARY), _passage(TOMATO)).search(
        "library opens morning", k=2, min_score=0.2
    )
    assert [hit.passage.text for hit in hits] == [LIBRARY]


def test_an_index_round_trips_through_three_files_and_no_pickle(tmp_path: Path) -> None:
    store = _store(_passage(LIBRARY), _passage(TOMATO), _evidence(STATEMENT))
    store.save(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [INDEX_FILE, MANIFEST_FILE, PASSAGES_FILE]
    )
    loaded = PassageStore.load(tmp_path, HashingEmbeddings(), query_formatter=_identity)
    assert loaded.passages == store.passages
    assert loaded.search("library opens morning", k=1)[0].passage.text == LIBRARY


def test_the_manifest_describes_what_was_built(tmp_path: Path) -> None:
    store = _store(_passage(LIBRARY), _evidence(STATEMENT))
    store.save(tmp_path)
    manifest = read_manifest(tmp_path)
    assert manifest.embedding_model == "hashing-256"
    assert manifest.dimensions == 256
    assert manifest.passages == 2
    assert manifest.evidence_statements == 1
    assert manifest.contains_quote_only is False


def test_a_quote_only_passage_is_recorded_in_the_manifest() -> None:
    store = _store(_passage(LIBRARY), _passage(TOMATO, source="nhs", ingestable=False))
    assert store.manifest.contains_quote_only is True


def test_the_served_index_never_contains_quote_only_text(tmp_path: Path) -> None:
    passages = [_passage(LIBRARY), _passage(TOMATO, source="nhs", ingestable=False)]
    served = [p for p in passages if p.may_be_ingested]
    _store(*served).save(tmp_path)
    lines = (tmp_path / PASSAGES_FILE).read_text(encoding="utf-8").splitlines()
    rows = [IndexedPassage.model_validate_json(line) for line in lines]
    assert [row.source_id for row in rows] == ["womenshealth"]
    assert read_manifest(tmp_path).contains_quote_only is False


def test_duplicate_passage_ids_are_refused() -> None:
    with pytest.raises(ValueError, match="duplicate passage id"):
        _store(_passage(LIBRARY), _passage(LIBRARY))


def test_an_empty_corpus_is_refused() -> None:
    with pytest.raises(ValueError, match="no passages"):
        PassageStore.build([], HashingEmbeddings(), embedding_model="hashing-256")


def test_a_passage_count_that_disagrees_with_the_vectors_is_refused(tmp_path: Path) -> None:
    _store(_passage(LIBRARY), _passage(TOMATO)).save(tmp_path)
    path = tmp_path / PASSAGES_FILE
    path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="2 vectors but 1 passages"):
        PassageStore.load(tmp_path, HashingEmbeddings())


class _FailingEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("embedding endpoint unreachable")

    def embed_query(self, text: str) -> list[float]:
        raise ConnectionError("embedding endpoint unreachable")


def test_a_failed_build_writes_nothing(tmp_path: Path) -> None:
    indexed = [to_indexed(_passage(LIBRARY), URLS)]
    with pytest.raises(ConnectionError):
        PassageStore.build(indexed, _FailingEmbeddings(), embedding_model="x").save(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_passages_file_is_one_json_object_per_line(tmp_path: Path) -> None:
    _store(_passage(LIBRARY)).save(tmp_path)
    (line,) = (tmp_path / PASSAGES_FILE).read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["text"] == LIBRARY
