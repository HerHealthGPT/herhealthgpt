"""A searchable index over passages.

**Brute-force cosine similarity, not FAISS, and that is a considered choice.**
The corpus is a few thousand sentences. At that size an exhaustive dot product
over a normalised matrix takes milliseconds, returns *exact* nearest neighbours
rather than approximate ones, adds no dependency, and has no index-building
parameters to get wrong. FAISS earns its place somewhere above roughly a hundred
thousand vectors; below that it is a liability with a build step.

:class:`PassageIndex` is the seam. When the served corpus outgrows this, only
:meth:`search` changes.

Persisted as two files that can both be inspected by hand: a ``.npy`` matrix and
a ``.jsonl`` of passages, one per line, in the same order. Storing the model
name alongside them means an index built with one model can never be silently
searched with another — the vectors would be meaningless and the failure would
look like bad retrieval rather than a mismatch.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from herhealth_data.retrieval.embed import Embedder, cosine_similarity
from herhealth_data.retrieval.passages import Passage

__all__ = ["Hit", "PassageIndex", "build_index"]

VECTORS_FILE = "vectors.npy"
PASSAGES_FILE = "passages.jsonl"
MANIFEST_FILE = "manifest.json"


@dataclass(frozen=True, slots=True)
class Hit:
    passage: Passage
    score: float


class IndexMismatchError(RuntimeError):
    """Raised when an index is searched with a different model than built it."""


@dataclass(frozen=True, slots=True)
class PassageIndex:
    passages: tuple[Passage, ...]
    vectors: np.ndarray
    model_name: str

    def __post_init__(self) -> None:
        if len(self.passages) != self.vectors.shape[0]:
            raise ValueError(
                f"{len(self.passages)} passages but {self.vectors.shape[0]} vectors; "
                "the index is corrupt and searching it would return the wrong text"
            )

    def search(
        self,
        query: str,
        embedder: Embedder,
        *,
        k: int = 8,
        where: Callable[[Passage], bool] | None = None,
        min_score: float = 0.0,
    ) -> list[Hit]:
        """The ``k`` most similar passages, most similar first.

        ``where`` filters *before* ranking, so asking for eight hits inside one
        source returns eight from that source rather than however many survive a
        filter applied afterwards.
        """
        if embedder.name != self.model_name:
            raise IndexMismatchError(
                f"index was built with {self.model_name!r} but searched with "
                f"{embedder.name!r}; rebuild it or use the original model"
            )
        if not self.passages:
            return []

        keep = (
            np.array([where(p) for p in self.passages], dtype=bool)
            if where is not None
            else np.ones(len(self.passages), dtype=bool)
        )
        if not keep.any():
            return []

        query_vector = embedder.encode([query], is_query=True)[0]
        scores = cosine_similarity(query_vector, self.vectors)
        scores = np.where(keep, scores, -np.inf)

        top = np.argsort(-scores)[: min(k, int(keep.sum()))]
        return [
            Hit(passage=self.passages[i], score=float(scores[i]))
            for i in top
            if scores[i] >= min_score
        ]

    # -- persistence -------------------------------------------------------

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / VECTORS_FILE, self.vectors)
        with (directory / PASSAGES_FILE).open("w", encoding="utf-8", newline="\n") as handle:
            for passage in self.passages:
                handle.write(json.dumps(asdict(passage), ensure_ascii=False) + "\n")
        (directory / MANIFEST_FILE).write_text(
            json.dumps(
                {
                    "model_name": self.model_name,
                    "passages": len(self.passages),
                    "dimensions": int(self.vectors.shape[1]),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> PassageIndex:
        manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
        vectors = np.load(directory / VECTORS_FILE)
        passages = []
        with (directory / PASSAGES_FILE).open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    passages.append(Passage(**json.loads(line)))
        return cls(
            passages=tuple(passages),
            vectors=vectors,
            model_name=str(manifest["model_name"]),
        )


def build_index(
    passages: Sequence[Passage], embedder: Embedder, *, batch_size: int = 128
) -> PassageIndex:
    """Embed every passage. Batched so a large corpus does not exhaust memory."""
    if not passages:
        return PassageIndex(
            passages=(),
            vectors=np.zeros((0, embedder.dimensions), dtype=np.float32),
            model_name=embedder.name,
        )

    chunks = [
        embedder.encode([p.text for p in passages[start : start + batch_size]])
        for start in range(0, len(passages), batch_size)
    ]
    return PassageIndex(
        passages=tuple(passages),
        vectors=np.vstack(chunks).astype(np.float32),
        model_name=embedder.name,
    )
