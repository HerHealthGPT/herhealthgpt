"""Embedding models, behind an interface so tests never load one.

Two implementations:

* :class:`SentenceTransformerEmbedder` wraps the real model. It imports
  ``sentence_transformers`` **inside** the constructor, so importing this module
  costs nothing and the heavy dependency stays optional.
* :class:`HashingEmbedder` is a deterministic stand-in with no model, no
  download and no network. Every test uses it.

That split is the same transport-injection trick used in the ingest client, and
it is what makes "tests never hit the network" structural rather than a rule
someone has to remember.

Model choice
------------
``BAAI/bge-m3``. Alsubhi et al. compared six embedding models across six Arabic
datasets: bge-m3 scored best (70.99), multilingual-e5-large close behind
(70.31), and both **beat the Arabic-specific models** — Arabic-Triplet-
Matryoshka-V2 (66.46) and Arabic-mpnet-base-all-nli-triplet (45.92). Reaching
for an Arabic-specialised encoder would have been the intuitive move and the
wrong one. See docs/adr/0010 for the full reasoning and the alternatives.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import numpy as np

__all__ = [
    "DEFAULT_MODEL",
    "Embedder",
    "HashingEmbedder",
    "SentenceTransformerEmbedder",
    "cosine_similarity",
]

#: Chosen on published Arabic RAG results, not on popularity. See ADR 0010.
DEFAULT_MODEL = "BAAI/bge-m3"

#: bge-m3 asymmetry: queries and passages are encoded with different prefixes in
#: some model families. bge-m3 does not require one, but the interface carries
#: the distinction so a model that does need it can be swapped in without
#: changing any caller.
QUERY_PREFIX = ""
PASSAGE_PREFIX = ""


@runtime_checkable
class Embedder(Protocol):
    """Anything that turns text into unit-length vectors."""

    name: str
    dimensions: int

    def encode(self, texts: Sequence[str], *, is_query: bool = False) -> np.ndarray:
        """Return an ``(len(texts), dimensions)`` array of unit-length rows."""
        ...


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """Unit-length rows, so cosine similarity is a dot product.

    A zero row would divide by zero and produce NaN, which would then propagate
    silently through every similarity score. Zero rows are left as zeros, which
    score 0 against everything — visibly useless rather than invisibly wrong.
    """
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Similarity of one unit vector against unit rows. Just a dot product."""
    return matrix @ query


class SentenceTransformerEmbedder:
    """The real model. Downloads weights on first use."""

    def __init__(self, model_name: str = DEFAULT_MODEL, *, device: str | None = None) -> None:
        # Imported here rather than at module scope: the dependency is optional,
        # and importing it costs seconds plus a large memory footprint.
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover - depends on the extra
            raise ImportError(
                "sentence-transformers is not installed. Install the retrieval "
                "extra:  uv sync --extra retrieval"
            ) from error

        self._model = SentenceTransformer(model_name, device=device)
        self.name = model_name
        self.dimensions = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: Sequence[str], *, is_query: bool = False) -> np.ndarray:
        prefix = QUERY_PREFIX if is_query else PASSAGE_PREFIX
        prepared = [prefix + text for text in texts]
        vectors = self._model.encode(
            prepared, normalize_embeddings=True, show_progress_bar=len(prepared) > 256
        )
        return np.asarray(vectors, dtype=np.float32)


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
