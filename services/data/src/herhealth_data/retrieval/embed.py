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
