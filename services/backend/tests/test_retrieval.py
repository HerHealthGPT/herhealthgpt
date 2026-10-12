"""The backend retriever, offline. A tiny index is written with faiss and the
contract models, exactly as services/data would write it; the embedder and the
reranker are fakes, so no endpoint is involved."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import faiss
import httpx
import numpy as np
import pytest
from herhealth_contracts.retrieval import (
    INDEX_FILE,
    MANIFEST_FILE,
    PASSAGES_FILE,
    IndexedPassage,
    IndexManifest,
    PassageType,
)
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.embeddings import Embeddings

from herhealth_backend.triage.retrieval import (
    IndexRefused,
    LangChainRetrievalClient,
    RetrievalSettings,
    TriageRetriever,
    VllmReranker,
    load_vector_store,
)

DIM = 8
MODEL_ID = "test/embedder"


def _vector(axis: int, weight: float = 1.0) -> list[float]:
    """A unit vector mostly along one axis; ``weight`` controls how close it is
    to the pure axis, and therefore its cosine to a query on that axis."""
    vector = np.zeros(DIM, dtype=np.float32)
    vector[axis] = weight
    vector[(axis + 1) % DIM] = float(np.sqrt(max(0.0, 1.0 - weight * weight)))
    return vector.tolist()


class AxisEmbeddings(Embeddings):
    """Every query embeds to axis 0, so a passage's cosine is its weight on it."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("the retriever never embeds documents")

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return _vector(0)


def _passage(name: str, *, evidence: bool = False, ingestable: bool = True) -> IndexedPassage:
    return IndexedPassage(
        id=hashlib.sha256(name.encode()).hexdigest()[:16],
        passage_type=PassageType.EVIDENCE_STATEMENT if evidence else PassageType.SOURCE_PASSAGE,
        source_id="womenshealth",
        slug=name,
        text=f"placeholder text {name}",
        citation=f"womenshealth/{name}",
        url=f"https://example.org/{name}",
        may_be_ingested=ingestable,
        condition_id="alpha" if evidence else None,
        feature_id="beta" if evidence else None,
        value="yes" if evidence else None,
        strength="weak_support" if evidence else None,
    )


def _write_index(
    directory: Path,
    rows: Sequence[tuple[IndexedPassage, float]],
    *,
    model: str = MODEL_ID,
    contains_quote_only: bool = False,
) -> Path:
    """``rows`` is (passage, cosine to the query)."""
    vectors = np.asarray([_vector(0, weight) for _, weight in rows], dtype=np.float32)
    index = faiss.IndexFlatIP(DIM)
    index.add(vectors)
    directory.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(directory / INDEX_FILE))
    (directory / PASSAGES_FILE).write_text(
        "".join(passage.model_dump_json() + "\n" for passage, _ in rows), encoding="utf-8"
    )
    manifest = IndexManifest(
        embedding_model=model,
        dimensions=DIM,
        passages=len(rows),
        evidence_statements=sum(
            1 for p, _ in rows if p.passage_type is PassageType.EVIDENCE_STATEMENT
        ),
        contains_quote_only=contains_quote_only,
        built_at="2026-10-12T00:00:00+00:00",
    )
    (directory / MANIFEST_FILE).write_text(manifest.model_dump_json(), encoding="utf-8")
    return directory


class ScriptedReranker(BaseDocumentCompressor):
    """Scores each document from a table keyed by its slug."""

    scores: dict[str, float]

    def compress_documents(
        self, documents: Sequence[Document], query: str, callbacks: Callbacks | None = None
    ) -> Sequence[Document]:
        rescored = [
            Document(
                page_content=d.page_content,
                metadata={**d.metadata, "score": self.scores.get(d.metadata["slug"], 0.0)},
            )
            for d in documents
        ]
        return sorted(rescored, key=lambda d: -d.metadata["score"])


class BrokenReranker(BaseDocumentCompressor):
    def compress_documents(
        self, documents: Sequence[Document], query: str, callbacks: Callbacks | None = None
    ) -> Sequence[Document]:
        raise httpx.ConnectError("reranker unreachable")


def _client(
    directory: Path, reranker: BaseDocumentCompressor | None = None, **options: int
) -> tuple[LangChainRetrievalClient, AxisEmbeddings]:
    embeddings = AxisEmbeddings()
    store, _ = load_vector_store(directory, embeddings, expected_model=MODEL_ID)
    retriever = TriageRetriever(store=store, embeddings=embeddings, reranker=reranker, **options)
    return LangChainRetrievalClient(retriever), embeddings


SOURCES = [(_passage(f"s{i}"), 0.95 - i * 0.05) for i in range(8)]
EVIDENCE = [(_passage(f"e{i}", evidence=True), 0.30 - i * 0.05) for i in range(4)]


def test_without_a_reranker_results_follow_embedding_order(tmp_path: Path) -> None:
    client, embeddings = _client(_write_index(tmp_path, SOURCES), evidence_slots=0)
    hits = client.search("when does the library open?", k=3)
    assert [h.citation for h in hits] == ["womenshealth/s0", "womenshealth/s1", "womenshealth/s2"]
    assert hits[0].score == pytest.approx(0.95, abs=1e-3)
    assert hits[0].url == "https://example.org/s0"
    assert embeddings.queries[0].startswith("Instruct: ")
    assert embeddings.queries[0].endswith("Query:when does the library open?")


def test_evidence_statements_keep_their_reserved_slots(tmp_path: Path) -> None:
    # Eight source passages all outscore every evidence statement.
    client, _ = _client(_write_index(tmp_path, [*SOURCES, *EVIDENCE]))
    hits = client.search("query", k=8)
    kinds = [h.passage_type for h in hits]
    assert len(hits) == 8
    assert kinds.count(PassageType.EVIDENCE_STATEMENT) == 3
    assert [h.citation for h in hits if h.passage_type is PassageType.EVIDENCE_STATEMENT] == [
        "womenshealth/e0",
        "womenshealth/e1",
        "womenshealth/e2",
    ]
    assert hits[-1].feature_id == "beta"
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_the_reranker_decides_the_order(tmp_path: Path) -> None:
    reranker = ScriptedReranker(scores={"s7": 0.99, "s3": 0.80, "e3": 0.70})
    client, _ = _client(_write_index(tmp_path, [*SOURCES, *EVIDENCE]), reranker, evidence_slots=1)
    hits = client.search("query", k=3)
    assert [h.citation for h in hits] == ["womenshealth/s7", "womenshealth/s3", "womenshealth/e3"]
    assert hits[0].score == pytest.approx(0.99)


def test_a_passage_found_by_both_searches_appears_once(tmp_path: Path) -> None:
    # One evidence statement scores high enough to be in the general pool too.
    rows = [(_passage("e-top", evidence=True), 0.99), *SOURCES[:3]]
    client, _ = _client(_write_index(tmp_path, rows))
    hits = client.search("query", k=4)
    assert len({h.id for h in hits}) == len(hits) == 4


def test_fewer_evidence_statements_than_slots(tmp_path: Path) -> None:
    rows = [*SOURCES[:2], EVIDENCE[0]]
    client, _ = _client(_write_index(tmp_path, rows))
    hits = client.search("query", k=8)
    assert len(hits) == 3
    assert sum(h.passage_type is PassageType.EVIDENCE_STATEMENT for h in hits) == 1


def test_reranker_failure_falls_back_to_embedding_order(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client, _ = _client(_write_index(tmp_path, SOURCES), BrokenReranker(), evidence_slots=0)
    hits = client.search("query", k=2)
    assert [h.citation for h in hits] == ["womenshealth/s0", "womenshealth/s1"]
    assert "reranker" in caplog.text.lower()


def test_an_empty_query_calls_nothing(tmp_path: Path) -> None:
    client, embeddings = _client(_write_index(tmp_path, SOURCES))
    assert client.search("   ") == []
    assert embeddings.queries == []


def test_an_index_from_another_model_is_refused(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES, model="BAAI/bge-m3")
    with pytest.raises(IndexRefused, match=r"BAAI/bge-m3.*test/embedder"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_an_index_with_quote_only_text_is_refused(tmp_path: Path) -> None:
    # The manifest claims it is clean; one passage says otherwise.
    rows = [SOURCES[0], (_passage("nhs-row", ingestable=False), 0.5)]
    _write_index(tmp_path, rows, contains_quote_only=False)
    with pytest.raises(IndexRefused, match="quote-only"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_an_index_whose_manifest_admits_quote_only_text_is_refused(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES, contains_quote_only=True)
    with pytest.raises(IndexRefused, match="quote-only"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_a_missing_index_is_refused_with_the_path(tmp_path: Path) -> None:
    with pytest.raises(IndexRefused, match=str(tmp_path)):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_mismatched_counts_are_refused(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES)
    path = tmp_path / PASSAGES_FILE
    path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    with pytest.raises(IndexRefused, match="8 vectors but 1 passages"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def _reranker(handler: httpx.MockTransport, api_key: str | None = None) -> VllmReranker:
    return VllmReranker(
        url="http://rerank.test",
        model="herhealth-rerank",
        api_key=api_key,
        client=httpx.Client(transport=handler),
    )


DOCS = [
    Document(page_content="first", metadata={"slug": "a"}),
    Document(page_content="second", metadata={"slug": "b"}),
]


def test_reranker_request_and_score_mapping() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.1},
                ]
            },
        )

    out = _reranker(httpx.MockTransport(handler), api_key="secret").compress_documents(DOCS, "q")
    assert [d.metadata["slug"] for d in out] == ["b", "a"]
    assert [d.metadata["score"] for d in out] == [0.9, 0.1]
    assert seen["url"] == "http://rerank.test/v1/rerank"
    assert seen["auth"] == "Bearer secret"
    assert '"documents":["first","second"]' in str(seen["body"]).replace(" ", "")
    assert DOCS[0].metadata == {"slug": "a"}  # the inputs are not mutated


def test_reranker_http_error_raises() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        _reranker(transport).compress_documents(DOCS, "q")


def test_reranker_malformed_body_falls_back(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"error": "boom"}))
    client, _ = _client(_write_index(tmp_path, SOURCES), _reranker(transport), evidence_slots=0)
    hits = client.search("query", k=2)
    assert [h.citation for h in hits] == ["womenshealth/s0", "womenshealth/s1"]
    assert "reranker" in caplog.text.lower()


def test_settings_defaults_point_at_the_local_endpoints() -> None:
    settings = RetrievalSettings.from_env({})
    assert settings.index_dir == Path("build/index")
    assert settings.embedding_url == "http://127.0.0.1:8003"
    assert settings.embedding_model == "herhealth-embed"
    assert settings.embedding_model_id == "Qwen/Qwen3-Embedding-4B"
    assert settings.reranker_url == "http://127.0.0.1:8004"
    assert settings.reranker_model == "herhealth-rerank"
    assert settings.api_key is None
    assert settings.evidence_slots == 3


def test_settings_read_the_environment() -> None:
    settings = RetrievalSettings.from_env(
        {
            "HERHEALTH_INDEX_DIR": "/data/index",
            "HERHEALTH_EMBEDDING_URL": "https://models.test/embed/",
            "HERHEALTH_MODELS_API_KEY": "k",
            "HERHEALTH_EVIDENCE_SLOTS": "2",
        }
    )
    assert settings.index_dir == Path("/data/index")
    assert settings.embedding_url == "https://models.test/embed"
    assert settings.api_key == "k"
    assert settings.evidence_slots == 2


def test_a_non_numeric_slot_count_names_the_variable() -> None:
    with pytest.raises(RuntimeError, match="HERHEALTH_EVIDENCE_SLOTS"):
        RetrievalSettings.from_env({"HERHEALTH_EVIDENCE_SLOTS": "three"})


def test_from_settings_refuses_a_missing_index(tmp_path: Path) -> None:
    settings = RetrievalSettings.from_env({"HERHEALTH_INDEX_DIR": str(tmp_path / "absent")})
    with pytest.raises(IndexRefused):
        LangChainRetrievalClient.from_settings(settings)


# --- failures of the embedding endpoint and of the index files ---------------


class DownEmbeddings(Embeddings):
    """Raises what the OpenAI client raises when the endpoint is unreachable."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("the retriever never embeds documents")

    def embed_query(self, text: str) -> list[float]:
        import openai

        raise openai.APIConnectionError(request=httpx.Request("POST", "http://embed.test/v1"))


def test_an_unreachable_embedding_endpoint_is_an_http_error(tmp_path: Path) -> None:
    # The turn route maps httpx.HTTPError to 502. The OpenAI client's own
    # exceptions are not httpx errors and would surface as a 500.
    _write_index(tmp_path, SOURCES)
    store, _ = load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)
    client = LangChainRetrievalClient(TriageRetriever(store=store, embeddings=DownEmbeddings()))
    with pytest.raises(httpx.HTTPError, match="embedding endpoint"):
        client.search("query")


def test_the_embedding_client_has_a_timeout() -> None:
    # Without one the client waits forever, and each hung turn strands a
    # worker thread for the life of the process.
    from herhealth_backend.triage.retrieval import build_embeddings

    embeddings = build_embeddings(RetrievalSettings.from_env({}))
    assert embeddings.request_timeout == 30.0
    assert embeddings.max_retries == 1


def test_a_truncated_index_file_is_refused_not_a_crash(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES)
    path = tmp_path / INDEX_FILE
    path.write_bytes(path.read_bytes()[:20])
    with pytest.raises(IndexRefused, match="cannot be read"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_an_undecodable_manifest_is_refused_not_a_crash(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES)
    (tmp_path / MANIFEST_FILE).write_bytes(b"\xff\xfe\x00not utf-8")
    with pytest.raises(IndexRefused):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)


def test_a_manifest_whose_width_disagrees_with_the_vectors_is_refused(tmp_path: Path) -> None:
    _write_index(tmp_path, SOURCES)
    path = tmp_path / MANIFEST_FILE
    path.write_text(path.read_text(encoding="utf-8").replace('"dimensions":8', '"dimensions":999'))
    with pytest.raises(IndexRefused, match="999.*8"):
        load_vector_store(tmp_path, AxisEmbeddings(), expected_model=MODEL_ID)
