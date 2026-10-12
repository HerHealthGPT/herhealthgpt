"""Retrieval for the triage agent: embed, search, rerank.

Built from LangChain components (ADR 0017). Per query:

1. the query is embedded by ``Qwen3-Embedding-4B`` (an HTTP call to vLLM);
2. a FAISS index, held in this process, returns a wide candidate set, plus a
   separate pool of evidence statements;
3. ``Qwen3-Reranker-4B`` (another HTTP call) scores every candidate against
   the query;
4. the top ``k`` are returned, with slots reserved for evidence statements.

No model weights load here. The index is three plain files written by
``services/data``; this module may not import that service, so it reads them
through the shapes in ``herhealth_contracts.retrieval``.

**Why evidence statements get reserved slots.** They are about 3% of the
index and the only passages that carry a ``feature_id``. Ranked purely on
relevance they are crowded out, and the model is then asked to name a feature
it was never shown. Reserving slots keeps that failure from returning now that
a reranker orders everything else.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from herhealth_contracts.retrieval import (
    INDEX_FILE,
    MANIFEST_FILE,
    PASSAGES_FILE,
    IndexedPassage,
    IndexManifest,
    PassageType,
    RetrievedPassage,
    format_query,
)
from langchain_core.callbacks import CallbackManagerForRetrieverRun, Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, ValidationError

__all__ = [
    "IndexRefused",
    "LangChainRetrievalClient",
    "RetrievalSettings",
    "TriageRetriever",
    "VllmReranker",
    "load_vector_store",
]

logger = logging.getLogger(__name__)

_EVIDENCE = PassageType.EVIDENCE_STATEMENT.value


class IndexRefused(RuntimeError):
    """The index on disk cannot be served. The message says why."""


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Where the index and the two model endpoints are."""

    index_dir: Path
    embedding_url: str
    #: The name the embedding model is SERVED under (the request's ``model``).
    embedding_model: str
    #: The model's real id, which must equal the index manifest's.
    embedding_model_id: str
    reranker_url: str
    reranker_model: str
    api_key: str | None
    evidence_slots: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> RetrievalSettings:
        raw_slots = environ.get("HERHEALTH_EVIDENCE_SLOTS", "3")
        try:
            slots = int(raw_slots)
        except ValueError as error:
            raise RuntimeError(
                f"HERHEALTH_EVIDENCE_SLOTS={raw_slots!r} is not a whole number"
            ) from error
        return cls(
            index_dir=Path(environ.get("HERHEALTH_INDEX_DIR", "build/index")),
            embedding_url=environ.get("HERHEALTH_EMBEDDING_URL", "http://127.0.0.1:8003").rstrip(
                "/"
            ),
            embedding_model=environ.get("HERHEALTH_EMBEDDING_MODEL", "herhealth-embed"),
            embedding_model_id=environ.get(
                "HERHEALTH_EMBEDDING_MODEL_ID", "Qwen/Qwen3-Embedding-4B"
            ),
            reranker_url=environ.get("HERHEALTH_RERANKER_URL", "http://127.0.0.1:8004").rstrip("/"),
            reranker_model=environ.get("HERHEALTH_RERANKER_MODEL", "herhealth-rerank"),
            api_key=environ.get("HERHEALTH_MODELS_API_KEY") or None,
            evidence_slots=max(0, slots),
        )


def load_vector_store(
    directory: Path, embeddings: Embeddings, *, expected_model: str | None
) -> tuple[Any, IndexManifest]:
    """Read the three index files into a LangChain FAISS store.

    Refuses, with a reason, any index this deployment must not answer from: a
    missing one, one built by a different embedding model (its vectors would
    be meaningless against this model's queries), one whose files disagree
    with each other, and one that contains quote-only text.
    """
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores import FAISS
    from langchain_community.vectorstores.utils import DistanceStrategy

    for name in (MANIFEST_FILE, PASSAGES_FILE, INDEX_FILE):
        if not (directory / name).is_file():
            raise IndexRefused(f"no retrieval index at {directory} ({name} is missing)")

    try:
        manifest = IndexManifest.model_validate_json(
            (directory / MANIFEST_FILE).read_text(encoding="utf-8")
        )
        with (directory / PASSAGES_FILE).open(encoding="utf-8") as handle:
            passages = [IndexedPassage.model_validate_json(line) for line in handle if line.strip()]
    except ValidationError as error:
        raise IndexRefused(
            f"the index at {directory} is not in the expected format: {error}"
        ) from error

    if expected_model is not None and manifest.embedding_model != expected_model:
        raise IndexRefused(
            f"the index at {directory} was built with {manifest.embedding_model}, "
            f"but this deployment embeds queries with {expected_model}; rebuild the index"
        )
    if manifest.contains_quote_only or any(not p.may_be_ingested for p in passages):
        raise IndexRefused(
            f"the index at {directory} contains quote-only text, which may not be "
            "served; build it without --authoring"
        )

    index = faiss.read_index(str(directory / INDEX_FILE))
    if index.ntotal != len(passages):
        raise IndexRefused(
            f"the index at {directory} has {index.ntotal} vectors but {len(passages)} passages"
        )

    store = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(
            {
                passage.id: Document(
                    page_content=passage.text,
                    metadata=passage.model_dump(mode="json", exclude={"text"}),
                )
                for passage in passages
            }
        ),
        index_to_docstore_id={position: p.id for position, p in enumerate(passages)},
        # Unit vectors and inner product: the score is cosine similarity.
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )
    return store, manifest


class VllmReranker(BaseDocumentCompressor):
    """Scores documents against a query through vLLM's ``/v1/rerank``.

    Returns copies ordered best-first, each with ``metadata["score"]`` set to
    the model's relevance score. Raises on any HTTP error and on a body it
    cannot read; the retriever decides what to do about that.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str
    model: str
    api_key: str | None = None
    client: Any

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = self.client.post(
            f"{self.url.rstrip('/')}/v1/rerank",
            json={
                "model": self.model,
                "query": query,
                "documents": [document.page_content for document in documents],
            },
            headers=headers,
        )
        response.raise_for_status()
        try:
            scored = [
                Document(
                    page_content=documents[int(row["index"])].page_content,
                    metadata={
                        **documents[int(row["index"])].metadata,
                        "score": float(row["relevance_score"]),
                    },
                )
                for row in response.json()["results"]
            ]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError(f"unreadable rerank response: {error!r}") from error
        return sorted(scored, key=lambda document: -document.metadata["score"])


class TriageRetriever(BaseRetriever):
    """Embed, search, rerank, and keep slots for evidence statements."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    store: Any
    embeddings: Any
    reranker: BaseDocumentCompressor | None = None
    k: int = 8
    #: How many candidates the general search hands the reranker.
    candidates: int = 40
    #: How many evidence statements join them, searched separately because
    #: they would rarely make the general top 40 on their own.
    evidence_candidates: int = 12
    evidence_slots: int = 3

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        k: int | None = None,
    ) -> list[Document]:
        if not query.strip():
            return []
        limit = k or self.k
        vector = self.embeddings.embed_query(format_query(query))

        general = self.store.similarity_search_with_score_by_vector(
            vector, k=max(self.candidates, limit)
        )
        evidence = (
            self.store.similarity_search_with_score_by_vector(
                vector,
                k=self.evidence_candidates,
                filter={"passage_type": _EVIDENCE},
                fetch_k=self.store.index.ntotal,
            )
            if self.evidence_slots > 0
            else []
        )

        pool: dict[str, Document] = {}
        for document, score in [*evidence, *general]:
            pool.setdefault(
                document.metadata["id"],
                Document(
                    page_content=document.page_content,
                    metadata={**document.metadata, "score": float(score)},
                ),
            )
        ranked = self._rank(query, list(pool.values()))

        reserved = [d for d in ranked if d.metadata["passage_type"] == _EVIDENCE][
            : min(self.evidence_slots, limit)
        ]
        reserved_ids = {d.metadata["id"] for d in reserved}
        rest = [d for d in ranked if d.metadata["id"] not in reserved_ids][: limit - len(reserved)]
        return sorted([*reserved, *rest], key=lambda d: -d.metadata["score"])

    def _rank(self, query: str, candidates: list[Document]) -> list[Document]:
        by_embedding = sorted(candidates, key=lambda d: -d.metadata["score"])
        if self.reranker is None or not candidates:
            return by_embedding
        try:
            return list(self.reranker.compress_documents(candidates, query))
        except (httpx.HTTPError, ValueError) as error:
            # Retrieval degrades to embedding order; it does not fail the turn.
            logger.warning("reranker unavailable, using embedding order: %s", error)
            return by_embedding


def _to_retrieved(document: Document) -> RetrievedPassage:
    meta = document.metadata
    return RetrievedPassage(
        id=meta["id"],
        passage_type=PassageType(meta["passage_type"]),
        source_id=meta["source_id"],
        text=document.page_content,
        citation=meta["citation"],
        score=max(-1.0, min(1.0, float(meta["score"]))),
        url=meta.get("url"),
        condition_id=meta.get("condition_id"),
        feature_id=meta.get("feature_id"),
        value=meta.get("value"),
        strength=meta.get("strength"),
    )


class LangChainRetrievalClient:
    """Implements ``herhealth_backend.triage.agent.RetrievalClient``."""

    def __init__(self, retriever: TriageRetriever) -> None:
        self._retriever = retriever

    @classmethod
    def from_settings(
        cls, settings: RetrievalSettings, *, rerank: bool = True
    ) -> LangChainRetrievalClient:
        """Raises :class:`IndexRefused` if there is no usable index."""
        from langchain_openai import OpenAIEmbeddings

        # check_embedding_ctx_length=False: send text, not locally produced
        # token ids, which a vLLM-served Qwen model would misread.
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            base_url=f"{settings.embedding_url}/v1",
            api_key=settings.api_key or "not-needed",
            check_embedding_ctx_length=False,
        )
        store, manifest = load_vector_store(
            settings.index_dir, embeddings, expected_model=settings.embedding_model_id
        )
        logger.info(
            "retrieval index loaded: %d passages, %s, %dd",
            manifest.passages,
            manifest.embedding_model,
            manifest.dimensions,
        )
        reranker = (
            VllmReranker(
                url=settings.reranker_url,
                model=settings.reranker_model,
                api_key=settings.api_key,
                client=httpx.Client(timeout=30.0),
            )
            if rerank
            else None
        )
        return cls(
            TriageRetriever(
                store=store,
                embeddings=embeddings,
                reranker=reranker,
                evidence_slots=settings.evidence_slots,
            )
        )

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [_to_retrieved(document) for document in self._retriever.invoke(query, k=k)]
