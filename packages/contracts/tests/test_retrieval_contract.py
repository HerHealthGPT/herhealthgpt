"""The on-disk index contract shared by the builder (services/data) and the
reader (services/backend), which may not import each other."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from herhealth_contracts.retrieval import (
    INDEX_FILE,
    MANIFEST_FILE,
    PASSAGES_FILE,
    IndexedPassage,
    IndexManifest,
    PassageType,
    format_query,
)


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "format_version": 1,
        "embedding_model": "Qwen/Qwen3-Embedding-4B",
        "embedding_revision": "5cf2132abc99cad020ac570b19d031efec650f2b",
        "dimensions": 2560,
        "passages": 10,
        "evidence_statements": 2,
        "contains_quote_only": False,
        "built_at": "2026-10-12T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_file_names_are_fixed() -> None:
    assert (INDEX_FILE, PASSAGES_FILE, MANIFEST_FILE) == (
        "index.faiss",
        "passages.jsonl",
        "manifest.json",
    )


def test_manifest_round_trips_through_json() -> None:
    manifest = IndexManifest.model_validate(_manifest())
    assert IndexManifest.model_validate_json(manifest.model_dump_json()) == manifest


@pytest.mark.parametrize(
    "overrides",
    [{"format_version": 2}, {"dimensions": 0}, {"embedding_model": ""}, {"surprise": 1}],
)
def test_manifest_rejects_what_a_reader_could_not_trust(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        IndexManifest.model_validate(_manifest(**overrides))


def test_query_instruction_format_is_the_one_the_embedder_expects() -> None:
    formatted = format_query("when does the library open?")
    assert formatted.startswith("Instruct: ")
    assert formatted.endswith("\nQuery:when does the library open?")


def test_indexed_passage_carries_evidence_fields() -> None:
    passage = IndexedPassage(
        id="0123456789abcdef",
        passage_type=PassageType.EVIDENCE_STATEMENT,
        source_id="womenshealth",
        slug="evidence/pcos/cycle_regularity/irregular",
        text="placeholder statement",
        citation="womenshealth/evidence",
        may_be_ingested=True,
        condition_id="pcos",
        feature_id="cycle_regularity",
        value="irregular",
        strength="weak_support",
    )
    assert IndexedPassage.model_validate_json(passage.model_dump_json()) == passage


def test_indexed_passage_rejects_a_malformed_id() -> None:
    with pytest.raises(ValidationError):
        IndexedPassage(
            id="not-a-hash",
            passage_type=PassageType.SOURCE_PASSAGE,
            source_id="womenshealth",
            slug="page",
            text="placeholder",
            citation="womenshealth/page",
            may_be_ingested=True,
        )
