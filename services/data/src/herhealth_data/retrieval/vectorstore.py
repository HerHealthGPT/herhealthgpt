"""The retrieval index: build it, save it, load it, search it.

Built from LangChain components (ADR 0017): an ``Embeddings`` object turns
text into vectors, and a ``FAISS`` vector store searches them. The embedding
model itself runs in vLLM and is reached over HTTP; no weights load here.

**Saved without pickle.** LangChain's own ``FAISS.save_local`` pickles its
document store, and unpickling executes code. An index is copied between
machines, so it is written as three plain files instead — the native FAISS
index, one JSON object per passage, and a manifest — and the LangChain store
is rebuilt from them at load. The file names and both record shapes live in
``herhealth_contracts.retrieval``, because the backend reads the same files
and may not import this module.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from herhealth_contracts.retrieval import (
    INDEX_FILE,
    MANIFEST_FILE,
    PASSAGES_FILE,
    IndexedPassage,
    IndexManifest,
    PassageType,
    format_query,
)
from langchain_core.embeddings import Embeddings

from herhealth_data.retrieval.embed import HashingEmbedder
from herhealth_data.retrieval.passages import Passage
from herhealth_data.retrieval.source_urls import SourceUrlIndex, resolve_url

__all__ = [
    "HASHING_MODEL",
    "HashingEmbeddings",
    "Hit",
    "PassageStore",
    "endpoint_embeddings",
    "read_manifest",
    "to_indexed",
]

#: What ``--model`` is set to for the offline stand-in.
HASHING_MODEL = "hashing"

QueryFormatter = Callable[[str], str]


class HashingEmbeddings(Embeddings):
    """``HashingEmbedder`` behind LangChain's interface. Tests only."""

    def __init__(self, dimensions: int = 256) -> None:
        self._embedder = HashingEmbedder(dimensions)
        self.name = self._embedder.name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = self._embedder.encode(texts).tolist()
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vector: list[float] = self._embedder.encode([text], is_query=True)[0].tolist()
        return vector


def endpoint_embeddings(*, url: str, model: str, api_key: str | None = None) -> Embeddings:
    """The served embedding model, through its OpenAI-compatible endpoint.

    ``check_embedding_ctx_length=False`` matters: with it on, the client
    tokenises locally with an OpenAI tokeniser and sends token ids, which a
    vLLM-served Qwen model would read as the wrong text.
    """
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=model,
        base_url=f"{url.rstrip('/')}/v1",
        api_key=api_key or "not-needed",
        check_embedding_ctx_length=False,
        chunk_size=64,
    )


def to_indexed(passage: Passage, urls: SourceUrlIndex) -> IndexedPassage:
    """A ``Passage`` as it is written to disk, with its citation url resolved."""
    return IndexedPassage(
        id=passage.id,
        passage_type=PassageType(passage.passage_type),
        source_id=passage.source_id,
        slug=passage.slug,
        heading=passage.heading,
        text=passage.text,
        citation=passage.citation,
        url=resolve_url(urls, passage.source_id, passage.slug, passage.condition_id),
        may_be_ingested=passage.may_be_ingested,
        condition_id=passage.condition_id,
        feature_id=passage.feature_id,
        value=passage.value,
        strength=passage.strength,
    )


def read_manifest(directory: Path) -> IndexManifest:
    return IndexManifest.model_validate_json(
        (directory / MANIFEST_FILE).read_text(encoding="utf-8")
    )


@dataclass(frozen=True, slots=True)
class Hit:
    passage: IndexedPassage
    score: float


class PassageStore:
    """An index in memory: the passages, their vectors, and how to query them."""

    def __init__(
        self,
        passages: Sequence[IndexedPassage],
        index: Any,
        embeddings: Embeddings,
        manifest: IndexManifest,
        *,
        query_formatter: QueryFormatter = format_query,
    ) -> None:
        from langchain_community.docstore.in_memory import InMemoryDocstore
        from langchain_community.vectorstores import FAISS
        from langchain_community.vectorstores.utils import DistanceStrategy
        from langchain_core.documents import Document

        if index.ntotal != len(passages):
            raise ValueError(
                f"{index.ntotal} vectors but {len(passages)} passages; the index is "
                "corrupt and searching it would return the wrong text"
            )
        self.passages = tuple(passages)
        self.manifest = manifest
        self._by_id = {passage.id: passage for passage in self.passages}
        if len(self._by_id) != len(self.passages):
            seen: set[str] = set()
            for passage in self.passages:
                if passage.id in seen:
                    raise ValueError(f"duplicate passage id {passage.id} ({passage.citation})")
                seen.add(passage.id)
        self._index = index
        self._embeddings = embeddings
        self._format = query_formatter
        self._store = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore(
                {
                    passage.id: Document(page_content=passage.text, metadata={"id": passage.id})
                    for passage in self.passages
                }
            ),
            index_to_docstore_id={
                position: passage.id for position, passage in enumerate(self.passages)
            },
            # Unit vectors and inner product: the score IS cosine similarity.
            distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
        )

    @classmethod
    def build(
        cls,
        passages: Sequence[IndexedPassage],
        embeddings: Embeddings,
        *,
        embedding_model: str,
        embedding_revision: str | None = None,
        query_formatter: QueryFormatter = format_query,
    ) -> PassageStore:
        """Embed every passage. Nothing touches disk here, so a build that
        fails halfway leaves no index behind that looks complete."""
        import faiss

        if not passages:
            raise ValueError("no passages to index")
        vectors = np.asarray(
            embeddings.embed_documents([passage.text for passage in passages]),
            dtype=np.float32,
        )
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(int(vectors.shape[1]))
        index.add(vectors)
        manifest = IndexManifest(
            embedding_model=embedding_model,
            embedding_revision=embedding_revision,
            dimensions=int(vectors.shape[1]),
            passages=len(passages),
            evidence_statements=sum(
                1 for p in passages if p.passage_type is PassageType.EVIDENCE_STATEMENT
            ),
            contains_quote_only=any(not p.may_be_ingested for p in passages),
            built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        return cls(passages, index, embeddings, manifest, query_formatter=query_formatter)

    def save(self, directory: Path) -> None:
        import faiss

        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / INDEX_FILE))
        with (directory / PASSAGES_FILE).open("w", encoding="utf-8", newline="\n") as handle:
            for passage in self.passages:
                handle.write(passage.model_dump_json() + "\n")
        (directory / MANIFEST_FILE).write_text(
            self.manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(
        cls,
        directory: Path,
        embeddings: Embeddings,
        *,
        query_formatter: QueryFormatter = format_query,
    ) -> PassageStore:
        import faiss

        manifest = read_manifest(directory)
        with (directory / PASSAGES_FILE).open(encoding="utf-8") as handle:
            passages = [IndexedPassage.model_validate_json(line) for line in handle if line.strip()]
        index = faiss.read_index(str(directory / INDEX_FILE))
        return cls(passages, index, embeddings, manifest, query_formatter=query_formatter)

    def search(
        self,
        query: str,
        *,
        k: int = 8,
        where: Callable[[IndexedPassage], bool] | None = None,
        min_score: float = 0.0,
    ) -> list[Hit]:
        """The ``k`` most similar passages, most similar first.

        ``where`` filters *before* ranking, so asking for eight hits inside one
        source returns eight from that source rather than however many survive
        a filter applied afterwards.
        """
        vector = self._embeddings.embed_query(self._format(query))
        if where is None:
            found = self._store.similarity_search_with_score_by_vector(vector, k=k)
        else:
            by_id = self._by_id

            def keep(metadata: dict[str, Any]) -> bool:
                return where(by_id[metadata["id"]])

            found = self._store.similarity_search_with_score_by_vector(
                vector, k=k, filter=keep, fetch_k=len(self.passages)
            )
        return [
            Hit(passage=self._by_id[document.metadata["id"]], score=float(score))
            for document, score in found
            if float(score) >= min_score
        ]
