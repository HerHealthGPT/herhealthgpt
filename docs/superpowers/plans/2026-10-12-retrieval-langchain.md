# Retrieval on LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `bge-m3` retrieval service with a LangChain pipeline that embeds with `Qwen3-Embedding-4B`, searches a FAISS index, and reranks with `Qwen3-Reranker-4B`, running inside the backend and calling the model endpoints over HTTP.

**Architecture:** `services/data` builds a pickle-free index (native FAISS file, `passages.jsonl`, manifest). The backend loads those three files into a LangChain FAISS store and serves retrieval through a `BaseRetriever` subclass behind the existing `RetrievalClient` protocol. The two services share only the on-disk format and models in `herhealth_contracts`. `services/model` and everything tied to `bge-m3` is deleted.

**Tech Stack:** Python 3.12, LangChain (`langchain-core`, `langchain-community`, `langchain-openai`), `faiss-cpu`, httpx, pydantic, pytest, uv, vLLM endpoints from step 1.

**Spec:** `docs/superpowers/specs/2026-10-12-retrieval-langchain-design.md`

## Global Constraints

- Embedding endpoint `http://127.0.0.1:8003`, served name `herhealth-embed`, model id `Qwen/Qwen3-Embedding-4B`, width 2560. Reranker endpoint `http://127.0.0.1:8004`, served name `herhealth-rerank`. All read from `infra/model/serve.conf` or environment, never hard-coded in logic.
- Index files: `index.faiss`, `passages.jsonl`, `manifest.json`. **No pickle anywhere.** Never call `FAISS.save_local` or `FAISS.load_local`.
- The served index (`build/index`) never contains a passage with `may_be_ingested` false. The authoring index (`build/index-authoring`) may.
- Evidence statements keep 3 reserved slots of 8.
- The backend imports nothing from `herhealth_data`. `services/data` imports nothing from `herhealth_backend`.
- No model weights load in the backend process.
- Tests never hit the network and need no GPU: use `HashingEmbeddings`, fake rerankers and `httpx.MockTransport`.
- No file, comment, string or commit message may describe the system as diagnosing.
- The API calls below were checked on 2026-10-12 against `langchain-core 1.6.9`, `langchain-community 0.4.2`, `langchain-openai 1.7.0`, `faiss-cpu 1.15.1` and the live endpoints. `uv lock` decides the versions actually installed.
- Run before any `uv` command, in every shell:

  ```bash
  export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
  ```

- **Go-aheads already given by the repo owner (2026-10-12):** installing from PyPI, and fetching the source corpus. **Not given:** commits. Ask once before Task 1 whether to commit per task on `Mazen-Branch`; if not, skip every "Commit" step.
- Disk: `/home/jovyan` has about 2.6 GB free. Check `df -h /home/jovyan` before Task 9 and stop if under 1 GB.

## Review Focus

1. **The embedding endpoint fails partway through an index build**: no index files may be left behind looking complete. Task 3, `test_a_failed_build_writes_nothing`.
2. **An index built by a different embedding model is loaded**: the backend must refuse at start-up with the two model names in the message, not return nonsense scores. Task 6, `test_an_index_from_another_model_is_refused`.
3. **The reranker is down or answers with an unexpected body**: retrieval must still return passages in embedding order. Task 6, `test_reranker_failure_falls_back_to_embedding_order` and `test_reranker_malformed_body_falls_back`.
4. **Fewer evidence statements match than there are reserved slots, or `k` exceeds the candidates**: return what exists without error and without duplicates. Task 6, `test_fewer_evidence_statements_than_slots`.
5. **A quote-only passage reaches the served index by any route**: the builder drops it, and the backend refuses an index that contains one even if the manifest claims otherwise. Task 3, `test_the_served_index_never_contains_quote_only_text`; Task 6, `test_an_index_with_quote_only_text_is_refused`.

## File Structure

| File | Responsibility |
|---|---|
| `packages/contracts/src/herhealth_contracts/retrieval.py` (modify) | Index file names, `IndexedPassage`, `IndexManifest`, the query instruction |
| `services/data/src/herhealth_data/retrieval/source_urls.py` (moved from `services/model`) | Citation URL lookup |
| `services/data/src/herhealth_data/retrieval/vectorstore.py` (create) | Build, save, load and search the index |
| `services/data/src/herhealth_data/retrieval/embed.py` (rewrite) | `HashingEmbedder` only |
| `services/data/src/herhealth_data/retrieval/propose.py` (modify) | Evidence proposals over the new store |
| `services/data/src/herhealth_data/retrieval/index.py`, `compose.py` (delete) | Old numpy index |
| `services/data/src/herhealth_data/commands.py`, `cli.py`, `paths.py` (modify) | `index`, `search`, `propose` commands |
| `services/backend/src/herhealth_backend/triage/retrieval.py` (create) | Settings, index loading, reranker, retriever, `LangChainRetrievalClient` |
| `services/backend/src/herhealth_backend/evaluation/retrieval_eval.py` (create) | The recall check and its CLI |
| `services/backend/src/herhealth_backend/app/main.py`, `app/config.py`, `triage/clients.py` (modify) | Wiring; `HttpRetrievalClient` removed |
| `services/model/` (delete) | The `bge-m3` retrieval service |
| CI, compose, Docker, Makefile, pyproject files (modify) | Remove the retrieval image and `bge-m3` |
| `docs/adr/0017-qwen3-embedding-and-reranker-on-langchain.md` (create) and docs (modify) | Record the change |

---

### Task 1: Shared contract for the index

**Files:**
- Modify: `packages/contracts/src/herhealth_contracts/retrieval.py`
- Create: `packages/contracts/tests/test_retrieval.py`

**Interfaces:**
- Produces, all importable from `herhealth_contracts.retrieval`: `INDEX_FILE = "index.faiss"`, `PASSAGES_FILE = "passages.jsonl"`, `MANIFEST_FILE = "manifest.json"`, `QUERY_INSTRUCTION: str`, `format_query(query: str) -> str`, `IndexedPassage`, `IndexManifest`.

- [ ] **Step 1: Write the failing test**

`packages/contracts/tests/test_retrieval.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_retrieval.py -q`
Expected: collection error, `ImportError: cannot import name 'INDEX_FILE'`.

- [ ] **Step 3: Add the contract**

In `packages/contracts/src/herhealth_contracts/retrieval.py`:

Change the import line `from typing import Annotated` to `from typing import Annotated, Literal`.

Replace the `__all__` line with:

```python
__all__ = [
    "INDEX_FILE",
    "MANIFEST_FILE",
    "PASSAGES_FILE",
    "QUERY_INSTRUCTION",
    "IndexManifest",
    "IndexedPassage",
    "PassageId",
    "PassageType",
    "RetrievedPassage",
    "format_query",
]

#: The three files that make up a retrieval index on disk. The builder
#: (services/data) writes them and the backend reads them; neither imports the
#: other, so these names and the two models below ARE the interface. There is
#: deliberately no pickle among them: unpickling executes code, and an index is
#: copied between machines.
INDEX_FILE = "index.faiss"
PASSAGES_FILE = "passages.jsonl"
MANIFEST_FILE = "manifest.json"

#: Qwen3-Embedding is instruction-aware on the QUERY side only: documents are
#: embedded as plain text, queries as "Instruct: <task>\nQuery:<text>". The
#: builder and every searcher must agree on this, which is why it lives here.
QUERY_INSTRUCTION = (
    "Given a question about women's reproductive health, "
    "retrieve passages that answer it"
)


def format_query(query: str) -> str:
    """A query in the form the embedding model was trained to read."""
    return f"Instruct: {QUERY_INSTRUCTION}\nQuery:{query}"
```

Append to the end of the file:

```python
class IndexedPassage(BaseModel):
    """One line of ``passages.jsonl``: a passage and everything needed to cite
    it. Line N describes vector N of ``index.faiss``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: PassageId
    passage_type: PassageType
    source_id: Identifier
    slug: str
    heading: str = ""
    text: str
    citation: str
    url: str | None = None
    #: False for a quote-only source (NHS). Such a passage may sit in the
    #: authoring index and must never be in a served one.
    may_be_ingested: bool
    condition_id: Identifier | None = None
    feature_id: Identifier | None = None
    value: str | None = None
    strength: str | None = None


class IndexManifest(BaseModel):
    """``manifest.json``: what built this index, so a reader can refuse one it
    cannot use before answering a single query from it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal[1] = 1
    #: The embedding model's real id, not the name it is served under.
    embedding_model: str = Field(min_length=1)
    embedding_revision: str | None = None
    dimensions: int = Field(gt=0)
    passages: int = Field(ge=0)
    evidence_statements: int = Field(ge=0)
    contains_quote_only: bool
    built_at: str
```

In the same file, replace the comment above `RetrievedPassage.score`:

```python
    #: How well the text matched the query: the reranker's relevance score
    #: when it ran, otherwise cosine similarity. Not a probability of anything
    #: clinical and not evidence strength.
```

- [ ] **Step 4: Run the tests and the type check**

Run: `uv run pytest packages/contracts/tests -q && uv run mypy --config-file packages/contracts/pyproject.toml packages/contracts/src`
Expected: all tests pass; mypy reports `Success`.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts
git commit -m "feat(contracts): define the on-disk retrieval index format"
```

---

### Task 2: Move the citation URL lookup into the data service

**Files:**
- Move: `services/model/src/herhealth_model/source_urls.py` → `services/data/src/herhealth_data/retrieval/source_urls.py`
- Move: `services/model/tests/test_source_urls.py` → `services/data/tests/test_source_urls.py`

**Interfaces:**
- Produces: `herhealth_data.retrieval.source_urls.load_source_urls(lock_path: Path) -> SourceUrlIndex`, `resolve_url(index, source_id, slug, condition_id=None) -> str | None`, `SourceUrlIndex = dict[tuple[str, str], str]`. Behaviour unchanged.

- [ ] **Step 1: Move the test and point it at the new module, then watch it fail**

```bash
git mv services/model/tests/test_source_urls.py services/data/tests/test_source_urls.py
sed -i 's/from herhealth_model.source_urls import/from herhealth_data.retrieval.source_urls import/' services/data/tests/test_source_urls.py
uv run --extra ingest pytest services/data/tests/test_source_urls.py -q
```

Expected: collection error, `ModuleNotFoundError: No module named 'herhealth_data.retrieval.source_urls'`.

- [ ] **Step 2: Move the module**

```bash
git mv services/model/src/herhealth_model/source_urls.py services/data/src/herhealth_data/retrieval/source_urls.py
```

In the moved file, replace the docstring's last paragraph (the one beginning `Read once at start-up.`) with:

```
Read once per index build. The url is written into each passage's record in
``passages.jsonl``, so nothing downstream needs the lock file.
```

- [ ] **Step 3: Run the test**

Run: `uv run --extra ingest pytest services/data/tests/test_source_urls.py -q`
Expected: `4 passed`.

- [ ] **Step 4: Commit**

```bash
git add -A services/model services/data
git commit -m "refactor(data): move the citation url lookup next to the index build"
```

---

### Task 3: The index build, save, load and search

**Files:**
- Modify: `services/data/pyproject.toml` (the `retrieval` extra and `[tool.uv.sources]`)
- Modify: `pyproject.toml` (root: the `retrieval` extra)
- Modify: `Makefile` (the `test` recipe)
- Rewrite: `services/data/src/herhealth_data/retrieval/embed.py`
- Create: `services/data/src/herhealth_data/retrieval/vectorstore.py`
- Create: `services/data/tests/test_vectorstore.py`

**Interfaces:**
- Consumes: Task 1's contract; Task 2's `resolve_url`, `SourceUrlIndex`; existing `Passage`.
- Produces, in `herhealth_data.retrieval.vectorstore`:
  - `HASHING_MODEL = "hashing"`
  - `class HashingEmbeddings(Embeddings)` with attribute `name: str`
  - `endpoint_embeddings(*, url: str, model: str, api_key: str | None = None) -> Embeddings`
  - `to_indexed(passage: Passage, urls: SourceUrlIndex) -> IndexedPassage`
  - `read_manifest(directory: Path) -> IndexManifest`
  - `@dataclass Hit(passage: IndexedPassage, score: float)`
  - `class PassageStore` with `manifest: IndexManifest`, `passages: tuple[IndexedPassage, ...]`, `PassageStore.build(passages, embeddings, *, embedding_model, embedding_revision=None, query_formatter=format_query)`, `.save(directory)`, `PassageStore.load(directory, embeddings, *, query_formatter=format_query)`, `.search(query, *, k=8, where=None, min_score=0.0) -> list[Hit]`

- [ ] **Step 1: Declare the dependencies**

In `services/data/pyproject.toml`, replace the whole `retrieval = [ ... ]` list with:

```toml
retrieval = [
    # Vectors are held as float32 arrays on the way into the index.
    "numpy>=1.26",
    # The index itself. Exact inner-product search over unit vectors, which is
    # cosine similarity; at a few thousand passages nothing approximate is
    # needed. Written with faiss's own serialiser, never pickled.
    "faiss-cpu>=1.9",
    # The pipeline is built from LangChain components (ADR 0017): the
    # embeddings interface, the FAISS vector store, and the OpenAI-compatible
    # client that talks to the vLLM embedding endpoint.
    "langchain-core>=1.0",
    "langchain-community>=0.4",
    "langchain-openai>=1.0",
]
```

In the same file, delete the `torch = [...]` line and its two comment lines under `[tool.uv.sources]`, leaving `herhealth-contracts = { workspace = true }`.

In the root `pyproject.toml`, delete the whole `[[tool.uv.index]]` block named `pytorch-cpu` together with the comment paragraph above it that begins `# torch on Linux comes from PyTorch's CPU index`. Nothing depends on torch any more.

In `Makefile`, in the `test` recipe, change `$(UV) run --extra ingest pytest` to `$(UV) run --extra ingest --extra retrieval pytest`.

Then resolve and install (network, approved):

```bash
uv lock && uv sync --extra ingest --extra retrieval
```

Expected: `uv lock` rewrites `uv.lock` without `torch` or `sentence-transformers`; `uv sync` succeeds.

- [ ] **Step 2: Write the failing tests**

`services/data/tests/test_vectorstore.py`:

```python
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
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run --extra ingest --extra retrieval pytest services/data/tests/test_vectorstore.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'herhealth_data.retrieval.vectorstore'`.

- [ ] **Step 4: Rewrite `embed.py`**

Replace the whole of `services/data/src/herhealth_data/retrieval/embed.py` with:

```python
"""The offline stand-in for an embedding model.

The real embedder is ``Qwen/Qwen3-Embedding-4B``, served by vLLM and reached
over HTTP (see ``vectorstore.endpoint_embeddings`` and ADR 0017). No model
runs in this process. What remains here is the deterministic stand-in the
tests use, so that nothing in the test suite needs a model, a GPU or a
network.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

import numpy as np

__all__ = ["HashingEmbedder"]


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """Unit-length rows, so cosine similarity is a dot product.

    A zero row would divide by zero and produce NaN, which would then propagate
    silently through every similarity score. Zero rows are left as zeros, which
    score 0 against everything — visibly useless rather than invisibly wrong.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


class HashingEmbedder:
    """A deterministic bag-of-words embedder. No model, no network, no download.

    Every token is hashed to a dimension and accumulated. That gives genuine
    lexical similarity — two sentences sharing words score higher — which is
    enough to test that retrieval *plumbing* works: that the right passage comes
    back for an obviously matching query, that filters apply, that an index
    round-trips through disk.

    It is emphatically **not** semantic. It cannot match "heavy periods" to
    "menorrhagia", and no test should assert that it does. Judging retrieval
    *quality* needs the real model and belongs in an evaluation, not a unit test.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.name = f"hashing-{dimensions}"
        self.dimensions = dimensions

    def encode(self, texts: Sequence[str], *, is_query: bool = False) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                vectors[row, int.from_bytes(digest, "big") % self.dimensions] += 1.0
        return _normalise(vectors)
```

- [ ] **Step 5: Write `vectorstore.py`**

`services/data/src/herhealth_data/retrieval/vectorstore.py`:

```python
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
            passages = [
                IndexedPassage.model_validate_json(line) for line in handle if line.strip()
            ]
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
```

- [ ] **Step 6: Run the tests**

Run: `uv run --extra ingest --extra retrieval pytest services/data/tests/test_vectorstore.py -q`
Expected: `13 passed`.

`services/data/tests/test_compose.py` and `test_cli.py` now fail at import or on the old flags. That is expected until Tasks 4 and 5; do not run the whole data suite yet.

- [ ] **Step 7: Commit**

```bash
git add services/data/pyproject.toml pyproject.toml uv.lock Makefile services/data/src/herhealth_data/retrieval/embed.py services/data/src/herhealth_data/retrieval/vectorstore.py services/data/tests/test_vectorstore.py
git commit -m "feat(data): build the retrieval index on LangChain and FAISS, without pickle"
```

---

### Task 4: The `index`, `search` and `propose` commands on the new store

**Files:**
- Modify: `services/data/src/herhealth_data/paths.py`
- Modify: `services/data/src/herhealth_data/retrieval/propose.py`
- Modify: `services/data/src/herhealth_data/retrieval/__init__.py`
- Modify: `services/data/src/herhealth_data/commands.py` (`_load_embedder`, `run_index`, `run_search`, `run_propose`)
- Modify: `services/data/src/herhealth_data/cli.py` (the `index`, `search`, `propose` parsers)
- Modify: `services/data/tests/test_cli.py` (the index section)
- Create: `services/data/tests/test_propose.py`
- Modify: `Makefile` (add `index`, `index-authoring`)

**Interfaces:**
- Consumes: Task 3's `PassageStore`, `Hit`, `HashingEmbeddings`, `endpoint_embeddings`, `read_manifest`, `to_indexed`, `HASHING_MODEL`.
- Produces: `herhealth-data index [--authoring] [--model hashing] [--embedding-url URL] [--clean-dir] [--index-dir] [--knowledge]`; `herhealth-data search QUERY`; `herhealth-data propose` (unchanged flags). `propose_rows(base, store: PassageStore, *, condition_ids=None, per_gap=2, min_score=0.30, limit=10, cited_sources_only=True) -> list[Proposal]`. `paths.AUTHORING_INDEX_DIR`, `paths.SERVE_CONF`, `paths.INGEST_LOCK_FILE`.

- [ ] **Step 1: Rewrite the index tests in `test_cli.py`**

In `services/data/tests/test_cli.py`, replace everything from the comment banner `# index --exclude-quote-only, offline (hashing stand-in, no model download)` down to (not including) the banner `# fetch --tolerate-quote-only-failures` with:

```python
# index, offline (hashing stand-in, no model, no endpoint)
# --------------------------------------------------------------------------


def _write_clean_doc(clean_dir: Path, source_id: str, slug: str, sentence: str) -> None:
    document = {
        "source_id": source_id,
        "slug": slug,
        "sections": [{"heading": "Symptoms", "section_type": "symptoms", "paragraphs": [sentence]}],
    }
    (clean_dir / source_id).mkdir(parents=True, exist_ok=True)
    (clean_dir / source_id / f"{slug}.json").write_text(json.dumps(document), encoding="utf-8")


def _build_index(tmp_path: Path, *extra: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    clean_dir = tmp_path / "clean"
    # Placeholder text, not clinical content: only the source id matters here.
    _write_clean_doc(clean_dir, "womenshealth", "page", "A placeholder sentence, public domain.")
    _write_clean_doc(clean_dir, "nhs", "page", "A placeholder sentence from a quote-only page.")
    index_dir = tmp_path / "index"
    code = main(
        [
            "index",
            *("--clean-dir", str(clean_dir), "--index-dir", str(index_dir)),
            *("--model", "hashing", *extra),
        ]
    )
    assert code == 0
    lines = (index_dir / "passages.jsonl").read_text(encoding="utf-8").splitlines()
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    return [json.loads(line) for line in lines], manifest


def test_the_served_index_has_no_quote_only_text(tmp_path: Path) -> None:
    """The default build is the one the backend serves and the one that may be
    copied to a server: every passage ingestable, none from nhs. Covers source
    passages and the evidence statements built from knowledge/ alike."""
    passages, manifest = _build_index(tmp_path)
    assert passages
    assert all(p["may_be_ingested"] is True for p in passages)
    assert not any(p["source_id"] == "nhs" for p in passages)
    assert any(p["passage_type"] == "evidence_statement" for p in passages)
    assert manifest["contains_quote_only"] is False


def test_the_authoring_index_keeps_quote_only_text_and_says_so(tmp_path: Path) -> None:
    passages, manifest = _build_index(tmp_path, "--authoring")
    assert any(p["source_id"] == "nhs" for p in passages)
    assert manifest["contains_quote_only"] is True


def test_index_writes_no_pickle(tmp_path: Path) -> None:
    _build_index(tmp_path)
    assert sorted(p.name for p in (tmp_path / "index").iterdir()) == [
        "index.faiss",
        "manifest.json",
        "passages.jsonl",
    ]


def test_authoring_defaults_off_and_the_old_flag_is_gone() -> None:
    assert build_parser().parse_args(["index"]).authoring is False
    with pytest.raises(SystemExit):
        build_parser().parse_args(["index", "--exclude-quote-only"])


def test_search_finds_a_passage_in_a_built_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _build_index(tmp_path)
    code = main(["search", "placeholder sentence public domain", "--index-dir", str(tmp_path / "index")])
    assert code == 0
    assert "A placeholder sentence, public domain." in capsys.readouterr().out


# --------------------------------------------------------------------------
```

- [ ] **Step 2: Write the propose test**

`services/data/tests/test_propose.py`:

```python
"""The evidence-proposal tool over the new store. It reads the real knowledge
base (tracked, offline) and a synthetic index, so no source text is needed."""

from __future__ import annotations

from herhealth_data import paths
from herhealth_data.knowledge import load_knowledge_base
from herhealth_data.retrieval.passages import Passage
from herhealth_data.retrieval.propose import find_gaps, propose_rows
from herhealth_data.retrieval.vectorstore import HashingEmbeddings, PassageStore, to_indexed


def _store_for(text: str, source_id: str) -> PassageStore:
    passage = Passage(
        source_id=source_id, slug="page", heading="", section_type="other", text=text
    )
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
```

- [ ] **Step 3: Run both to verify they fail**

Run: `uv run --extra ingest --extra retrieval pytest services/data/tests/test_cli.py services/data/tests/test_propose.py -q`
Expected: failures. `test_propose.py` fails with a `TypeError` (`propose_rows` still requires `index` and `embedder`) or an import error from `propose.py`; the new `test_cli.py` tests fail on the unknown `--authoring` flag.

- [ ] **Step 4: Add the paths**

In `services/data/src/herhealth_data/paths.py`, add after the `INDEX_DIR` line:

```python
#: Includes quote-only (NHS) passages. For the evidence-proposal tool on the
#: authoring machine only; never served and never copied to a server.
AUTHORING_INDEX_DIR: Final[Path] = BUILD_DIR / "index-authoring"
```

and after the `INGEST_TARGETS_FILE` line:

```python
INGEST_LOCK_FILE: Final[Path] = DATA_SERVICE_DIR / "ingest.lock.jsonl"
#: Model ids, pinned revisions and ports for the vLLM processes (step 1).
SERVE_CONF: Final[Path] = REPO_ROOT / "infra" / "model" / "serve.conf"
```

If `paths.py` has an `__all__`, add the three names to it.

- [ ] **Step 5: Port `propose.py`**

In `services/data/src/herhealth_data/retrieval/propose.py`:

Replace the three import lines

```python
from herhealth_data.retrieval.embed import Embedder
from herhealth_data.retrieval.index import Hit, PassageIndex
from herhealth_data.retrieval.passages import Passage
```

with

```python
from herhealth_contracts.retrieval import IndexedPassage

from herhealth_data.retrieval.vectorstore import Hit, PassageStore
```

In `class Proposal`, change `passage: Passage` to `passage: IndexedPassage`.

Replace the signature and body of `propose_rows` from `def propose_rows(` through `return proposals[:limit]` with:

```python
def propose_rows(
    base: KnowledgeBase,
    store: PassageStore,
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

        def keep(passage: IndexedPassage, allowed: set[str] | None = allowed) -> bool:
            return allowed is None or passage.source_id in allowed

        hits: list[Hit] = store.search(gap.query(), k=per_gap, where=keep, min_score=min_score)
        proposals.extend(
            Proposal(gap=gap, passage=hit.passage, score=hit.score) for hit in hits
        )

    proposals.sort(key=lambda p: -p.score)
    return proposals[:limit]
```

- [ ] **Step 6: Rewrite `retrieval/__init__.py`**

Replace the whole of `services/data/src/herhealth_data/retrieval/__init__.py` with:

```python
"""Semantic search over the cleaned corpus.

Two jobs, and they are separate on purpose:

1. **Serving** — build the index the backend retrieves from. Only passages
   whose source licence permits redistribution go into it; a quote-only (NHS)
   passage never does, so the files are safe to copy to a server.
2. **Authoring** — propose candidate evidence rows for a human to approve,
   over a second, local-only index that does include quote-only passages.

:func:`~herhealth_data.retrieval.passages.evidence_statement_passages` is what
makes ``evidence.csv`` part of the corpus: each row is rendered into a passage
tagged ``passage_type="evidence_statement"``, searchable like any sentence.

Nothing here decides urgency. Retrieval finds text.
"""

from herhealth_data.retrieval.embed import HashingEmbedder
from herhealth_data.retrieval.passages import (
    Passage,
    evidence_statement_passages,
    load_passages,
    split_sentences,
)
from herhealth_data.retrieval.propose import (
    Gap,
    Proposal,
    find_gaps,
    propose_rows,
    render_batch,
    write_batch,
)
from herhealth_data.retrieval.source_urls import load_source_urls, resolve_url
from herhealth_data.retrieval.vectorstore import (
    HASHING_MODEL,
    HashingEmbeddings,
    Hit,
    PassageStore,
    endpoint_embeddings,
    read_manifest,
    to_indexed,
)

__all__ = [
    "HASHING_MODEL",
    "Gap",
    "HashingEmbedder",
    "HashingEmbeddings",
    "Hit",
    "Passage",
    "PassageStore",
    "Proposal",
    "endpoint_embeddings",
    "evidence_statement_passages",
    "find_gaps",
    "load_passages",
    "load_source_urls",
    "propose_rows",
    "read_manifest",
    "render_batch",
    "resolve_url",
    "split_sentences",
    "to_indexed",
    "write_batch",
]
```

- [ ] **Step 7: Rewrite the three commands**

In `services/data/src/herhealth_data/commands.py`, make sure `import os` is among the imports at the top, then replace everything from `def _load_embedder(` down to the end of `run_propose` (the line `return 0` that follows `print("Review each row, set a real strength, then re-run \`make evidence\`.")`) with:

```python
def _serve_conf() -> dict[str, str]:
    """``infra/model/serve.conf`` as a dict; empty if the file is absent."""
    values: dict[str, str] = {}
    if not paths.SERVE_CONF.is_file():
        return values
    for line in paths.SERVE_CONF.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _load_embeddings(model: str | None, url: str | None):  # type: ignore[no-untyped-def]
    """``(embeddings, model id, revision, query formatter)``.

    The hashing stand-in when asked for it by name, otherwise the embedding
    model served by vLLM. Named explicitly rather than falling back silently: a
    run that quietly used a bag-of-words embedder would produce plausible-looking
    results with no semantic matching behind them at all.
    """
    from herhealth_contracts.retrieval import format_query

    from herhealth_data.retrieval import HASHING_MODEL, HashingEmbeddings, endpoint_embeddings

    if model == HASHING_MODEL:
        print("using the hashing stand-in — lexical overlap only, NOT semantic")
        stand_in = HashingEmbeddings()
        return stand_in, stand_in.name, None, (lambda query: query)

    conf = _serve_conf()
    endpoint = (
        url
        or os.environ.get("HERHEALTH_EMBEDDING_URL")
        or f"http://127.0.0.1:{conf.get('EMBED_PORT', '8003')}"
    )
    served_name = conf.get("EMBED_SERVED_NAME", "herhealth-embed")
    embeddings = endpoint_embeddings(
        url=endpoint, model=served_name, api_key=os.environ.get("HERHEALTH_MODELS_API_KEY")
    )
    print(f"embedding endpoint: {endpoint} ({served_name})")
    return (
        embeddings,
        conf.get("EMBED_MODEL", "Qwen/Qwen3-Embedding-4B"),
        conf.get("EMBED_REVISION"),
        format_query,
    )


def _load_store(index_dir: Path, url: str | None):  # type: ignore[no-untyped-def]
    """An existing index, opened with whatever embedder built it."""
    from herhealth_data.retrieval import HASHING_MODEL, PassageStore, read_manifest

    manifest = read_manifest(index_dir)
    model = HASHING_MODEL if manifest.embedding_model.startswith("hashing") else None
    embeddings, _, _, formatter = _load_embeddings(model, url)
    return PassageStore.load(index_dir, embeddings, query_formatter=formatter)


def run_index(args: argparse.Namespace) -> int:
    """Build a retrieval index from build/clean/ and knowledge/.

    The default is the SERVED index: no quote-only text, safe to copy to a
    server. ``--authoring`` builds the second, local-only index that keeps
    quote-only passages for the evidence-proposal tool.
    """
    from herhealth_data.retrieval import (
        PassageStore,
        evidence_statement_passages,
        load_passages,
        load_source_urls,
        to_indexed,
    )

    if not args.clean_dir.is_dir():
        print(f"error: no cleaned documents at {args.clean_dir} — run `make clean` first")
        return 2

    base, problems = load_knowledge_base(args.knowledge)
    if base is None:
        for problem in problems:
            print(problem)
        return 2

    ingestable = {s.id: s.may_be_ingested for s in base.sources}
    source_passages = load_passages(args.clean_dir, ingestable)
    evidence_passages = evidence_statement_passages(
        base.evidence, base.features_by_id, base.conditions_by_id, ingestable
    )
    passages = [*source_passages, *evidence_passages]
    if not passages:
        print(f"error: no passages found in {args.clean_dir}")
        return 1

    by_source = Counter(p.source_id for p in passages)
    quote_only = sum(1 for p in passages if not p.may_be_ingested)
    print(
        f"{len(source_passages)} source passage(s) + {len(evidence_passages)} "
        f"evidence statement(s) = {len(passages)} total, from {len(by_source)} source(s)"
    )
    for source_id, count in sorted(by_source.items()):
        ingestable_here = any(p.may_be_ingested for p in passages if p.source_id == source_id)
        mark = "" if ingestable_here else "  (quote-only)"
        print(f"  {source_id:<14} {count:>5}{mark}")

    if args.authoring:
        index_dir = args.index_dir or paths.AUTHORING_INDEX_DIR
        print(f"\nauthoring index: keeping {quote_only} quote-only passage(s). Never serve it.")
    else:
        index_dir = args.index_dir or paths.INDEX_DIR
        passages = [p for p in passages if p.may_be_ingested]
        print(f"\nserved index: dropped {quote_only} quote-only passage(s), {len(passages)} remain.")
        if not passages:
            print("error: nothing left to index once quote-only passages are dropped")
            return 1

    urls = load_source_urls(paths.INGEST_LOCK_FILE)
    indexed = [to_indexed(p, urls) for p in passages]

    embeddings, model_id, revision, formatter = _load_embeddings(args.model, args.embedding_url)
    print(f"embedding {len(indexed)} passage(s) with {model_id}...")
    store = PassageStore.build(
        indexed,
        embeddings,
        embedding_model=model_id,
        embedding_revision=revision,
        query_formatter=formatter,
    )
    if not args.authoring and store.manifest.contains_quote_only:
        print("error: a quote-only passage reached the served index; nothing was written")
        return 1
    store.save(index_dir)
    print(f"index written to {index_dir} ({store.manifest.dimensions}d)")
    return 0


def run_search(args: argparse.Namespace) -> int:
    """Query an index by hand. The quickest way to see whether it works."""
    if not (args.index_dir / "manifest.json").is_file():
        print(f"error: no index at {args.index_dir} — run `make index` first")
        return 2

    store = _load_store(args.index_dir, args.embedding_url)
    hits = store.search(args.query, k=args.k)
    if not hits:
        print("no hits")
        return 1

    for hit in hits:
        print(f"\n  {hit.score:.3f}  {hit.passage.citation}")
        print(f"         {hit.passage.text}")
    print()
    return 0


def run_propose(args: argparse.Namespace) -> int:
    """Propose candidate evidence rows into a DRAFT batch for review.

    Writes `approved: false` and a placeholder strength, so nothing can reach
    evidence.csv without a person reading it.
    """
    from herhealth_data.retrieval import propose_rows, write_batch

    if not (args.index_dir / "manifest.json").is_file():
        print(f"error: no index at {args.index_dir} — run `make index-authoring` first")
        return 2

    base, problems = load_knowledge_base(args.knowledge)
    if base is None:
        for problem in problems:
            print(problem)
        return 2

    store = _load_store(args.index_dir, args.embedding_url)
    proposals = propose_rows(
        base,
        store,
        condition_ids=args.condition or None,
        per_gap=args.per_gap,
        min_score=args.min_score,
        limit=args.limit,
    )

    for proposal in proposals:
        gap = proposal.gap
        print(f"\n  {proposal.score:.3f}  {gap.condition.id} · {gap.feature.id}={gap.value}")
        print(f"         {proposal.passage.citation}")
        print(f"         {proposal.passage.text[:110]}")

    if not proposals:
        print("no candidates cleared the score threshold")
        return 1

    write_batch(proposals, args.out, model_name=store.manifest.embedding_model)
    print(f"\n{len(proposals)} proposal(s) written to {args.out}")
    print("DRAFT — approved: false, every strength is a placeholder.")
    print("Review each row, set a real strength, then re-run `make evidence`.")
    return 0
```

If `commands.py` does not already import `paths` and `Path`, add `from pathlib import Path` and `from herhealth_data import paths`.

- [ ] **Step 8: Update the CLI parsers**

In `services/data/src/herhealth_data/cli.py`, replace the block that starts `index_parser = subparsers.add_parser(` and ends `propose_parser.add_argument("--model", default=None)` with:

```python
    index_parser = subparsers.add_parser(
        "index", help="embed build/clean/ and knowledge/ into a retrieval index"
    )
    index_parser.add_argument("--clean-dir", type=Path, default=paths.CLEAN_DIR)
    index_parser.add_argument(
        "--index-dir", type=Path, default=None, help="defaults to build/index, or build/index-authoring"
    )
    index_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    index_parser.add_argument(
        "--model", default=None, help="'hashing' for the offline stand-in; default is the served embedder"
    )
    index_parser.add_argument(
        "--embedding-url", default=None, help="defaults to the port in infra/model/serve.conf"
    )
    index_parser.add_argument(
        "--authoring",
        action="store_true",
        help="keep quote-only (NHS) passages; for the proposal tool only, never served",
    )
    index_parser.set_defaults(func=commands.run_index)

    search_parser = subparsers.add_parser("search", help="query a retrieval index by hand")
    search_parser.add_argument("query")
    search_parser.add_argument("--index-dir", type=Path, default=paths.INDEX_DIR)
    search_parser.add_argument("--embedding-url", default=None)
    search_parser.add_argument("-k", type=int, default=8)
    search_parser.set_defaults(func=commands.run_search)

    propose_parser = subparsers.add_parser(
        "propose", help="propose candidate evidence rows into a DRAFT batch"
    )
    propose_parser.add_argument("--knowledge", type=Path, default=paths.KNOWLEDGE_DIR)
    propose_parser.add_argument("--index-dir", type=Path, default=paths.AUTHORING_INDEX_DIR)
    propose_parser.add_argument("--embedding-url", default=None)
```

- [ ] **Step 9: Add the Makefile targets**

In `Makefile`, add `index index-authoring` to the `.PHONY` line, and add after the `clean:` recipe:

```make
# Needs the embedding endpoint (scripts/serve-models.sh) and build/clean/.
# The served index: no quote-only text, safe to copy to a server.
index:
	$(UV) run --extra retrieval python -m herhealth_data.cli index --knowledge $(KNOWLEDGE_DIR)

# Keeps quote-only (NHS) passages. For `herhealth-data propose` only.
index-authoring:
	$(UV) run --extra retrieval python -m herhealth_data.cli index --authoring --knowledge $(KNOWLEDGE_DIR)
```

- [ ] **Step 10: Run the tests**

Run: `uv run --extra ingest --extra retrieval pytest services/data/tests/test_cli.py services/data/tests/test_propose.py services/data/tests/test_vectorstore.py -q`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add services/data Makefile
git commit -m "feat(data): run index, search and propose on the new retrieval store"
```

---

### Task 5: Delete the old index code in the data service

**Files:**
- Delete: `services/data/src/herhealth_data/retrieval/index.py`
- Delete: `services/data/src/herhealth_data/retrieval/compose.py`
- Delete: `services/data/tests/test_compose.py`

**Interfaces:** none produced. After this task nothing in `services/data` refers to `PassageIndex`, `balanced_search`, `SentenceTransformerEmbedder` or `bge-m3`.

- [ ] **Step 1: Confirm nothing still imports them**

Run: `git grep -n -E 'PassageIndex|balanced_search|build_index|SentenceTransformerEmbedder|cosine_similarity|retrieval\.index|retrieval\.compose' -- services/data packages`
Expected: matches only inside `retrieval/index.py`, `retrieval/compose.py` and `tests/test_compose.py`. If anything else matches, fix that file first.

- [ ] **Step 2: Delete them**

```bash
git rm services/data/src/herhealth_data/retrieval/index.py services/data/src/herhealth_data/retrieval/compose.py services/data/tests/test_compose.py
```

- [ ] **Step 3: Run the whole data and contracts suites, and lint**

Run: `uv run --extra ingest --extra retrieval pytest packages/contracts/tests services/data/tests -q && uv run ruff check packages/contracts services/data && git grep -n -i -E 'bge-m3|sentence.transformers' -- services/data`
Expected: all tests pass, ruff is clean, and the last `git grep` prints nothing.

- [ ] **Step 4: Commit**

```bash
git add -A services/data
git commit -m "refactor(data): remove the numpy index and the bge-m3 embedder"
```

---

### Task 6: The retriever in the backend

**Files:**
- Modify: `services/backend/pyproject.toml` (new `retrieval` extra; `api` includes it)
- Modify: `pyproject.toml` (root `retrieval` extra)
- Create: `services/backend/src/herhealth_backend/triage/retrieval.py`
- Create: `services/backend/tests/test_retrieval.py`

**Interfaces:**
- Consumes: Task 1's contract. The existing protocol `RetrievalClient.search(query: str, *, k: int = 8) -> list[RetrievedPassage]` in `herhealth_backend.triage.agent`.
- Produces, in `herhealth_backend.triage.retrieval`:
  - `class IndexRefused(RuntimeError)`
  - `@dataclass RetrievalSettings` with `index_dir: Path`, `embedding_url`, `embedding_model`, `embedding_model_id`, `reranker_url`, `reranker_model`, `api_key: str | None`, `evidence_slots: int`; `RetrievalSettings.from_env(environ=os.environ)`
  - `load_vector_store(directory: Path, embeddings: Embeddings, *, expected_model: str | None) -> tuple[Any, IndexManifest]`
  - `class VllmReranker(BaseDocumentCompressor)` with fields `url`, `model`, `api_key=None`, `client`
  - `class TriageRetriever(BaseRetriever)` with fields `store`, `embeddings`, `reranker=None`, `k=8`, `candidates=40`, `evidence_candidates=12`, `evidence_slots=3`
  - `class LangChainRetrievalClient` with `__init__(retriever)`, `from_settings(settings, *, rerank=True)`, `search(query, *, k=8)`

- [ ] **Step 1: Declare the dependencies**

In `services/backend/pyproject.toml`, under `[project.optional-dependencies]`, add before `api = [`:

```toml
# The retriever (triage/retrieval.py, ADR 0017). An extra of its own so the
# offline suite can install it without the web layer. No model weights: the
# embedder and the reranker are HTTP calls to vLLM.
retrieval = [
    "numpy>=1.26",
    "faiss-cpu>=1.9",
    "langchain-core>=1.0",
    "langchain-community>=0.4",
    "langchain-openai>=1.0",
    "httpx>=0.27",
]
```

and add `"herhealth-backend[retrieval]",` as the first entry inside the `api = [` list.

In the root `pyproject.toml`, change `retrieval = ["herhealth-data[retrieval]"]` to:

```toml
retrieval = ["herhealth-data[retrieval]", "herhealth-backend[retrieval]"]
```

Then: `uv lock && uv sync --extra ingest --extra retrieval`

- [ ] **Step 2: Write the failing tests**

`services/backend/tests/test_retrieval.py`:

```python
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
    retriever = TriageRetriever(
        store=store, embeddings=embeddings, reranker=reranker, **options
    )
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


DOCS = [Document(page_content="first", metadata={"slug": "a"}), Document(page_content="second", metadata={"slug": "b"})]


def test_reranker_request_and_score_mapping() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]},
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


def test_reranker_malformed_body_falls_back(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
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
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run --extra retrieval pytest services/backend/tests/test_retrieval.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'herhealth_backend.triage.retrieval'`.

- [ ] **Step 4: Write the retriever**

`services/backend/src/herhealth_backend/triage/retrieval.py`:

```python
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
            embedding_url=environ.get("HERHEALTH_EMBEDDING_URL", "http://127.0.0.1:8003").rstrip("/"),
            embedding_model=environ.get("HERHEALTH_EMBEDDING_MODEL", "herhealth-embed"),
            embedding_model_id=environ.get("HERHEALTH_EMBEDDING_MODEL_ID", "Qwen/Qwen3-Embedding-4B"),
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
            passages = [
                IndexedPassage.model_validate_json(line) for line in handle if line.strip()
            ]
    except ValidationError as error:
        raise IndexRefused(f"the index at {directory} is not in the expected format: {error}") from error

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
        rest = [d for d in ranked if d.metadata["id"] not in reserved_ids][
            : limit - len(reserved)
        ]
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
```

- [ ] **Step 5: Run the tests**

Run: `uv run --extra retrieval pytest services/backend/tests/test_retrieval.py -q`
Expected: `19 passed`.

- [ ] **Step 6: Commit**

```bash
git add services/backend/pyproject.toml pyproject.toml uv.lock services/backend/src/herhealth_backend/triage/retrieval.py services/backend/tests/test_retrieval.py
git commit -m "feat(triage): retrieve with a LangChain retriever, FAISS and the Qwen3 reranker"
```

---

### Task 7: Wire the retriever into the backend and remove the HTTP client

**Files:**
- Modify: `services/backend/src/herhealth_backend/app/main.py`
- Modify: `services/backend/src/herhealth_backend/app/config.py`
- Modify: `services/backend/src/herhealth_backend/triage/clients.py`
- Modify: `services/backend/src/herhealth_backend/app/triage/routes.py` (one error string and one docstring mention)
- Modify: `infra/envs/backend.env.example`

**Interfaces:**
- Consumes: Task 6's `RetrievalSettings`, `LangChainRetrievalClient`, `IndexRefused`.
- Produces: `_build_triage_agent()` returns `None` when there is no usable index (outside `demo` mode), so `POST /triage/turn` answers 503 "not configured".

- [ ] **Step 1: Remove `HttpRetrievalClient`**

In `services/backend/src/herhealth_backend/triage/clients.py`: delete the whole `class HttpRetrievalClient` (from its `class` line to the end of its `search` method) and remove `"HttpRetrievalClient",` from `__all__`. If `TypeAdapter` or `RetrievedPassage` is then unused in the file, ruff will say so in Step 5; remove what it flags.

- [ ] **Step 2: Remove the old setting**

In `services/backend/src/herhealth_backend/app/config.py`: delete the `MODEL_SERVICE_URL_ENV` constant with its comment, the `model_service_url` function, and both names from `__all__`. In the `TRIAGE_MODE_ENV` comment, change `a running services/model` to `a retrieval index (see triage/retrieval.py)`.

- [ ] **Step 3: Wire the new client in `main.py`**

In `services/backend/src/herhealth_backend/app/main.py`:

Delete the line `from herhealth_backend.app.config import model_service_url as configured_model_service_url`.

Remove `HttpRetrievalClient,` from the `from herhealth_backend.triage.clients import (` list.

Change `from herhealth_backend.triage.agent import ReasoningClient, TriageAgent` to `from herhealth_backend.triage.agent import ReasoningClient, RetrievalClient, TriageAgent`, and add after the `demo_clients` import:

```python
from herhealth_backend.triage.retrieval import (
    IndexRefused,
    LangChainRetrievalClient,
    RetrievalSettings,
)
```

If the module has no logger yet, add `import logging` to the imports and `logger = logging.getLogger(__name__)` after `__all__`.

Add this function immediately before `def _build_triage_agent`:

```python
def _build_retrieval() -> RetrievalClient | None:
    """The retriever for this deployment, or ``None`` when it has no usable
    index. ``None`` is not an error: triage is one feature of this backend,
    and a host without an index still serves accounts and the rest — the turn
    route answers 503 "not configured", the way it does without a reasoning
    model. The reason is logged, so it is never silent.
    """
    try:
        return LangChainRetrievalClient.from_settings(RetrievalSettings.from_env())
    except IndexRefused as error:
        logger.warning("triage retrieval is not configured: %s", error)
        return None
```

In `_build_triage_agent`, delete the line `retrieval = HttpRetrievalClient(base_url=configured_model_service_url())`, and insert immediately after the `if mode == "demo":` block (after its `return TriageAgent(...)`):

```python
    retrieval = _build_retrieval()
    if retrieval is None:
        return None
```

In that function's docstring, change `a running ``services/model``` to `a retrieval index and the two model endpoints`.

- [ ] **Step 4: Update the user-facing strings**

In `services/backend/src/herhealth_backend/app/triage/routes.py`, in the 503 `detail`, add one clause so the message covers the new cause. Replace

```python
                "or OPENROUTER_API_KEY for openrouter/vllm fallback)"
```

with

```python
                "or OPENROUTER_API_KEY for openrouter/vllm fallback; a real "
                "mode also needs a retrieval index at HERHEALTH_INDEX_DIR)"
```

In the same file's `_run_turn` docstring, change the two words `HttpRetrievalClient`` holds` to `the retrieval client holds`.

In `infra/envs/backend.env.example`, replace the line `HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001` with:

```
# Retrieval (ADR 0017). The index is built by `make index`; the two endpoints
# are the vLLM processes from scripts/serve-models.sh. Set the API key when the
# endpoints are reached over a network and require one.
HERHEALTH_INDEX_DIR=build/index
HERHEALTH_EMBEDDING_URL=http://127.0.0.1:8003
HERHEALTH_RERANKER_URL=http://127.0.0.1:8004
HERHEALTH_MODELS_API_KEY=
```

and change the comment line `# openrouter = OpenRouter reasoning + services/model RAG on :8001.` to `# openrouter = OpenRouter reasoning + the retrieval index and model endpoints below.`

- [ ] **Step 5: Verify**

```bash
uv sync --extra ingest --extra retrieval --extra api
uv run ruff check services/backend
uv run mypy services/backend/src/herhealth_backend/app
uv run python -c "import herhealth_backend.app.main"
git grep -n -E 'HttpRetrievalClient|model_service_url|MODEL_SERVICE_URL' -- services/backend infra/envs
uv run --extra ingest --extra retrieval pytest services/backend/tests --ignore=services/backend/tests/app -q
```

Expected: ruff clean; mypy `Success`; the import prints nothing; the `git grep` prints nothing; the tests pass. The tests under `services/backend/tests/app` need PostgreSQL in Docker and cannot run on the campus box; `backend.yml` runs them in CI.

- [ ] **Step 6: Commit**

```bash
git add services/backend infra/envs/backend.env.example
git commit -m "feat(triage): wire the LangChain retriever into the backend"
```

---

### Task 8: The recall check

**Files:**
- Create: `services/backend/src/herhealth_backend/evaluation/retrieval_eval.py`
- Create: `services/backend/tests/test_retrieval_eval.py`
- Modify: `services/backend/pyproject.toml` (`[project.scripts]`)

**Interfaces:**
- Consumes: `RetrievalClient` protocol; `LangChainRetrievalClient.from_settings(settings, rerank=...)`; `herhealth_contracts.loading.load_knowledge_base(directory) -> KnowledgeBase`.
- Produces: `build_query(base, row) -> str`; `evaluate(base, retrieval, *, k=8) -> Evaluation`; `Evaluation.summary() -> dict[str, object]`; console script `herhealth-eval-retrieval [--knowledge DIR] [--out FILE] [-k N]`.

- [ ] **Step 1: Write the failing test**

`services/backend/tests/test_retrieval_eval.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra retrieval pytest services/backend/tests/test_retrieval_eval.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'herhealth_backend.evaluation.retrieval_eval'`.

- [ ] **Step 3: Write the recall check**

`services/backend/src/herhealth_backend/evaluation/retrieval_eval.py`:

```python
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
    print(f"\n{label}: {summary['scored_rows']} rows scored, "
          f"{summary['excluded_quote_only_rows']} quote-only rows excluded")
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
```

In `services/backend/pyproject.toml`, under `[project.scripts]`, add:

```toml
herhealth-eval-retrieval = "herhealth_backend.evaluation.retrieval_eval:main"
```

Then `uv sync --extra ingest --extra retrieval --extra api` so the script is installed.

- [ ] **Step 4: Run the tests**

Run: `uv run --extra retrieval pytest services/backend/tests/test_retrieval_eval.py -q && uv run ruff check services/backend`
Expected: `4 passed`; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add services/backend
git commit -m "feat(eval): add a recall check for retrieval built from evidence.csv"
```

---

### Task 9: Delete the retrieval service and its place in the deploy

**Files:**
- Delete: `services/model/` (everything left in it)
- Delete: `scripts/pin-bge-m3.py`, `scripts/publish-index.sh`, `.github/workflows/build-index.yml`
- Modify: `pyproject.toml`, `Makefile`, `services/backend/Dockerfile`, `.dockerignore`
- Modify: `.github/workflows/deploy.yml`, `infra/compose.prod.yml`, `infra/deploy/deploy.sh`

**Interfaces:** none produced. After this task `git grep -n -E 'services/model|herhealth.model\b|bge'` matches only docs.

- [ ] **Step 1: Delete the service and the scripts**

```bash
git rm -r services/model
git rm scripts/pin-bge-m3.py scripts/publish-index.sh .github/workflows/build-index.yml
```

- [ ] **Step 2: Remove it from the workspace**

In the root `pyproject.toml`: delete `"herhealth-model",` from `dependencies`, `"services/model",` from `[tool.uv.workspace] members`, and the line `herhealth-model = { workspace = true }` from `[tool.uv.sources]`.

In `Makefile`: remove ` services/model` from the three `ruff` lines in `lint` and `fmt`, and ` services/model/tests` from the `test` recipe.

Run: `uv lock && uv sync --extra ingest --extra retrieval --extra api`
Expected: both succeed; `uv.lock` no longer lists `herhealth-model`.

- [ ] **Step 3: Fix the backend image**

In `services/backend/Dockerfile`: delete the line `COPY services/model/pyproject.toml services/model/`, and change

```dockerfile
RUN mkdir -p packages/contracts/src services/data/src services/model/src services/backend/src
```

to

```dockerfile
RUN mkdir -p packages/contracts/src services/data/src services/backend/src
```

In the comment near line 13 that mentions `services/model`, replace the reference so it reads that this image never imports `services/data`.

In `.dockerignore`, replace the comment sentence `build/ is deliberately NOT excluded — services/model/Dockerfile copies build/index, which is the one generated artefact a container needs.` with `build/index is not excluded: it is the one generated artefact a container may need.`

- [ ] **Step 4: Remove the retrieval image from the deploy workflow**

In `.github/workflows/deploy.yml`:

- In the header comment, replace step 1's three lines with `#   1. build the two images (frontend, backend), tagged with the git SHA (never \`latest\`)`, and delete the two variable lines `RETRIEVAL_INDEX_VERSION` and `BGE_M3_REVISION`.
- Under `on.push.paths`, delete `- "services/model/**"`.
- In the job's `env`, delete the `INDEX_VERSION` and `BGE_M3_REVISION` lines.
- In "Check required repository variables", change the loop to `for v in ROLE ARTIFACTS_BUCKET INSTANCE_ID; do`.
- Delete the steps "Fetch the published index", "Verify the index (model, revision, no quote-only text)" and "Build and push retrieval", each with its preceding comment lines.
- In "Which images already exist for this commit?", change `for repo in frontend backend retrieval; do` to `for repo in frontend backend; do`.
- In the comment above "Free runner disk space", replace `the three image builds (retrieval bakes bge-m3, about 2.3 GB)` with `the image builds`.

- [ ] **Step 5: Remove the retrieval container from production compose**

In `infra/compose.prod.yml`:

- Header: change `ONE host, four containers` to `ONE host, three containers`; delete the diagram line ending `--> retrieval:8001`; change `retrieval and the others are reachable` to `The others are reachable`.
- In the backend service's `environment`, delete `HERHEALTH_MODEL_SERVICE_URL: http://retrieval:8001`.
- Delete the whole `retrieval:` service block, from the `  retrieval:` line to the end of its `logging` section.
- If the backend service has `depends_on` naming `retrieval`, remove that entry.

In `infra/deploy/deploy.sh`, change the comment on the `MIN_FREE_GB=15` line to `# room for two image pulls and the previous release`.

- [ ] **Step 6: Verify**

```bash
python3 -c "import yaml; [yaml.safe_load(open(p)) for p in ('.github/workflows/deploy.yml', 'infra/compose.prod.yml')]; print('yaml ok')"
git grep -n -i -E 'retrieval:|herhealth-retrieval|INDEX_VERSION|BGE_M3' -- .github infra
git grep -n -E 'services/model|herhealth[-_]model\b' -- . ':!docs' ':!graphify-out' ':!CLAUDE.md' ':!README.md' ':!HANDOFF.md' ':!uv.lock'
make lint
make test
python3 scripts/check_repo_hygiene.py
```

Expected: `yaml ok`; both `git grep` commands print nothing (Terraform files under `infra/terraform` may still name the retrieval log group and repository: that is intended, leave them); lint and tests pass; hygiene reports nothing.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: delete the bge-m3 retrieval service and drop it from the deploy"
```

---

### Task 10: Build the index and run the live checks

This task uses the network and the GPUs. The corpus fetch was approved on 2026-10-12.

**Files:**
- Create (generated, gitignored): `raw/`, `build/clean/`, `build/index/`, `build/retrieval_eval.json`

**Interfaces:**
- Consumes: Tasks 3, 4, 6, 8; the three vLLM processes from step 1.
- Produces: the recall numbers and one live turn's output, for Task 11.

- [ ] **Step 1: Check the models and the disk**

```bash
bash scripts/serve-models.sh check
df -h /home/jovyan | tail -1
```

Expected: all three `endpoint=answering`; at least 1 GB free. If a process is down: `bash scripts/serve-models.sh start all` and wait for `check` to show them answering.

- [ ] **Step 2: Fetch and clean the corpus**

```bash
make fetch-plan
make fetch
make clean
ls build/clean/*/ | wc -l
du -sh raw build
```

Expected: `fetch-plan` lists the targets without requesting anything; `fetch` retrieves them (one NHS page, `nhs/pregnancy_bleeding`, is known to fail and no row cites it); `clean` writes JSON documents under `build/clean/`. If `fetch` stops on a failure other than that page, read its message and report it; do not retry in a loop.

- [ ] **Step 3: Build the served index**

```bash
make index
cat build/index/manifest.json
du -sh build/index
```

Expected: the manifest shows `"embedding_model": "Qwen/Qwen3-Embedding-4B"`, `"dimensions": 2560`, `"contains_quote_only": false`, and a passage count in the thousands.

- [ ] **Step 4: Search it by hand**

```bash
uv run --extra retrieval python -m herhealth_data.cli search "irregular periods and excess hair growth" -k 5
```

Expected: five passages with scores and citations, on topic.

- [ ] **Step 5: Run the recall check**

```bash
uv run --extra retrieval --extra api herhealth-eval-retrieval
```

Expected: two blocks, `reranker_on` and `reranker_off`, each with `sentence` and `statement` rows of `recall@1`, `recall@3`, `recall@8` and `mrr`, and `written to build/retrieval_eval.json`. Save the full output for Task 11.

- [ ] **Step 6: Run one live turn through the agent**

```bash
uv run --extra retrieval --extra api python - <<'PY'
from pathlib import Path

from herhealth_contracts.loading import load_knowledge_base

from herhealth_backend.triage.agent import Message, TriageAgent
from herhealth_backend.triage.clients import VllmReasoningClient
from herhealth_backend.triage.retrieval import LangChainRetrievalClient, RetrievalSettings


class Recording:
    def __init__(self, inner):
        self._inner = inner

    def search(self, query, *, k=8):
        hits = self._inner.search(query, k=k)
        print(f"retrieved {len(hits)} passage(s) for: {query!r}")
        for hit in hits:
            print(f"  {hit.score:.3f} {hit.passage_type.value:<19} {hit.citation}  {hit.url}")
        return hits


agent = TriageAgent(
    base=load_knowledge_base(Path("knowledge")),
    reasoning=VllmReasoningClient(base_url="http://127.0.0.1:8002", timeout=300.0),
    retrieval=Recording(LangChainRetrievalClient.from_settings(RetrievalSettings.from_env())),
)
try:
    turn = agent.run_turn([Message(role="user", content="My periods have been irregular for three months.")])
    print("decision:", turn.decision.type.value)
except Exception as error:  # the reply's validity is step 3's concern
    print("reasoning did not return a valid decision:", type(error).__name__, str(error)[:200])
PY
```

Expected: a `retrieved 8 passage(s)` block in which at least three lines are `evidence_statement` and the source passages carry `https://` URLs. The last line is either a decision type or a note that the reply did not validate; either is acceptable here. Save the output for Task 11.

- [ ] **Step 7: Confirm nothing generated is tracked**

Run: `git status --short`
Expected: no `raw/` or `build/` entries. If any appear, they are not ignored: stop and report.

---

### Task 11: Record the decision and update the docs

**Files:**
- Create: `docs/adr/0017-qwen3-embedding-and-reranker-on-langchain.md`
- Modify: `docs/adr/0010-multilingual-embeddings-beat-arabic-specific-ones.md` (status line)
- Modify: `CLAUDE.md`, `README.md`, `docs/runbooks/running-the-app.md`, `docs/runbooks/aws-deploy.md`, `docs/FLOW_EXPLAINED.md`
- Modify: `docs/superpowers/specs/2026-10-12-retrieval-langchain-design.md` (two corrections)

- [ ] **Step 1: Write the ADR**

`docs/adr/0017-qwen3-embedding-and-reranker-on-langchain.md`, replacing the two fenced result blocks with the saved output of Task 10 Steps 5 and 6:

````markdown
---
status: accepted
date: 2026-10-12
supersedes: 0010
---

# Retrieval uses Qwen3-Embedding-4B and Qwen3-Reranker-4B, built on LangChain

## Context

[ADR 0010](0010-multilingual-embeddings-beat-arabic-specific-ones.md) chose
`BAAI/bge-m3` on published Arabic RAG results and deferred a reranker until
retrieval evaluation showed the right passage retrieved but ranked outside the
top *k*. Retrieval ran as a CPU service, `services/model`, which the backend
called over HTTP.

On 2026-10-11 the repo owner decided that all three models run on the campus
GPU box, that the backend and frontend run on the EC2 instance and are given
the model endpoints, and that the RAG pipeline is rewritten on LangChain. On
2026-10-12 the owner decided that the `bge-m3` code and everything tied to it
is deleted.

## Decision

- **Embedding model:** `Qwen/Qwen3-Embedding-4B`, 2560 dimensions, served by
  vLLM. Queries carry the instruction prefix the model expects; documents do
  not.
- **Reranker:** `Qwen/Qwen3-Reranker-4B`, served by vLLM, applied to about 50
  candidates per query.
- **Pipeline:** LangChain components. `services/data` builds a FAISS index;
  the backend loads it into a LangChain FAISS store and retrieves through a
  `BaseRetriever` subclass with a custom reranking compressor.
- **Where it runs:** the retriever runs inside the backend process and holds
  the index. It loads no model weights; the embedder and the reranker are
  HTTP calls. `services/model` is deleted.
- **Index format:** three plain files (`index.faiss`, `passages.jsonl`,
  `manifest.json`), never pickled, because the index is copied between
  machines and unpickling executes code.
- **Unchanged:** sentence-level passages, evidence statements as passages,
  three reserved evidence-statement slots of eight, and no quote-only (NHS)
  text in anything served. The served index now excludes that text when it is
  built; a second, local-only index keeps it for the evidence-proposal tool.

## What was not established

This decision was **not** made on a measurement that the new models retrieve
better than `bge-m3`. No comparison was run: there was no retrieval evaluation
in the repo, and the campus box had no disk space for both embedders. ADR
0010's reasoning from the Arabic RAG literature is not refuted by anything
here. If retrieval quality in Arabic or French is questioned, that comparison
is the first thing to run.

## Measurement

A recall check now exists (`herhealth-eval-retrieval`). For each evidence row
from an ingestable source it builds a query from the row's condition and
feature labels and looks for two things in the top 8: the source sentence the
row quotes, and the evidence statement generated from the row.

Run on the campus box on 2026-10-12:

```
<paste the output of Task 10 Step 5 here>
```

Read these numbers with their limits. The queries come from the knowledge
base's own labels, not from how users write. The statement target is the
easier one, because the statement contains the query's words. It is English
only. Rows from NHS cannot be scored, because their text is not in the served
index. The knowledge base is source-traceable, not clinician-adjudicated.

One live turn through `TriageAgent` with the new retriever:

```
<paste the output of Task 10 Step 6 here>
```

## Consequences

- **Production triage is off** until the EC2 backend has an index and a route
  to the campus endpoints. They listen on localhost inside a pod today and
  have no API key. The backend reports "not configured" in the meantime.
- **Every query needs two network calls to the campus box.** If the box is
  down or its pod was culled, retrieval fails and so does triage.
- **`langchain-community` is being wound down** by its maintainers; it is
  where the FAISS vector store lives. If it is removed, the store has to move
  to whichever standalone package replaces it. The index files do not depend
  on it.
- The deploy pipeline builds two images, not three. The Terraform resources
  for the retrieval image and the index bucket role still exist and can be
  removed in a later `terraform apply`.
- `torch` and `sentence-transformers` are no longer dependencies of anything
  in the workspace.
````

- [ ] **Step 2: Mark ADR 0010 superseded**

In `docs/adr/0010-multilingual-embeddings-beat-arabic-specific-ones.md`, change the front-matter line `status: accepted` to `status: superseded by 0017`.

- [ ] **Step 3: Update the remaining docs**

Find every stale statement:

```bash
git grep -n -i -E 'bge-m3|services/model|:8001|MODEL_SERVICE_URL|build-index|publish-index|pin-bge|no reranker|exclude-quote-only|retrieval (service|image)' -- CLAUDE.md README.md docs/runbooks docs/FLOW_EXPLAINED.md docs/CODE_GUIDE.md CONTRIBUTING.md
```

Rewrite each hit so it states the current arrangement. The facts to use:

- Retrieval is `Qwen/Qwen3-Embedding-4B` plus `Qwen/Qwen3-Reranker-4B`, on LangChain, per ADR 0017, which supersedes ADR 0010.
- The retriever runs inside the backend; there is no retrieval service and nothing listens on port 8001.
- The index is built with `make index` (served, no NHS text) or `make index-authoring` (local only), into `build/index` and `build/index-authoring`.
- The backend reads `HERHEALTH_INDEX_DIR`, `HERHEALTH_EMBEDDING_URL`, `HERHEALTH_RERANKER_URL`, `HERHEALTH_MODELS_API_KEY`.
- The deploy builds two images (frontend, backend). `build-index.yml`, `scripts/pin-bge-m3.py` and `scripts/publish-index.sh` no longer exist.
- Production triage is "not configured" until step 3 connects EC2 to the campus endpoints.
- In `CLAUDE.md` specifically: the architecture block's `services/model/` line, the paragraph beginning `**Retrieval is \`BAAI/bge-m3\``, the `**No model weights load inside the backend process.**` line (still true; change its second sentence to say embedding and reranking are HTTP calls to vLLM), and the Deploy paragraph's "three images" and index sentences. Do not change the sections on the knowledge base, sources or verification.

Where a passage describes the old design as history (for example the incident write-up in `docs/security/`), leave it.

- [ ] **Step 4: Correct the spec**

In `docs/superpowers/specs/2026-10-12-retrieval-langchain-design.md`:

- Replace every `herhealth_data/retrieval/store.py` with `herhealth_data/retrieval/vectorstore.py` (a `test_store.py` for the fetch store already exists in the data tests).
- In the configuration table, add a row: `| \`HERHEALTH_EMBEDDING_MODEL_ID\` | \`Qwen/Qwen3-Embedding-4B\` | the model the index must have been built with |`.

- [ ] **Step 5: Verify**

```bash
git grep -n -i -E 'bge-m3|services/model|:8001|MODEL_SERVICE_URL' -- . ':!docs/adr' ':!docs/research' ':!docs/security' ':!docs/superpowers' ':!graphify-out' ':!HANDOFF.md' ':!infra/terraform' ':!uv.lock'
make lint && make test && python3 scripts/check_repo_hygiene.py
```

Expected: the `git grep` prints nothing; lint, tests and hygiene pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: record the move to Qwen3 embedding and reranking on LangChain (ADR 0017)"
```

---

## Done when

- `build/index/manifest.json` shows `Qwen/Qwen3-Embedding-4B`, 2560 dimensions, `contains_quote_only: false`.
- The live turn in Task 10 shows eight retrieved passages, at least three of them evidence statements, with URLs.
- ADR 0017 holds the recorded recall numbers for both targets, reranker on and off.
- `git grep -i bge-m3` matches only ADRs, research notes, the security write-up, Terraform and the superpowers documents.
- `make lint`, `make test` and the hygiene check pass.
- The deploy workflow builds two images and expects no index.
