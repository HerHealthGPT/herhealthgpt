"""The prose channel: similarity search, made usable for grounding.

``PassageIndex.search`` returns the top *k* sentences by cosine and stops
there. Two properties of this corpus make that the wrong thing to hand a
reasoning model, and both are measured rather than assumed.

**Sentences are too small to stand alone.** Median servable passage is 77
characters. Sentence-level chunking is load-bearing — ``make verify-quotes``
needs the quotable unit to exist as a retrievable one, see
``passages.split_sentences`` — so the chunk stays a sentence. What changes is
what gets *shown*: retrieve small, present large. Each hit is widened to its
neighbouring sentences within the same document, which costs nothing in
provenance (the hit's own text is unchanged and still verifies verbatim) and
roughly triples usable context per hit.

**One source dominates the corpus.** Of 3,747 servable passages, 2,415 are
``womenshealth`` — 64%. Top-8 by raw cosine is therefore usually six or seven
sentences from one site, which makes the differential a function of which
source was fetched most, not of what the query says. A per-source cap fixes
that for the cost of a slightly lower mean similarity.

Neither of these is a knob to tune for its own sake. The defaults below are the
smallest values that fix the measured problem.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from herhealth_data.retrieval.embed import Embedder, cosine_similarity
from herhealth_data.retrieval.index import PassageIndex
from herhealth_data.retrieval.passages import Passage

__all__ = ["WidenedHit", "balanced_search"]

#: At most this many hits from any one source in a result set. Three of eight
#: leaves room for every source to appear while stopping ``womenshealth``'s 64%
#: share of the corpus from deciding the whole window.
DEFAULT_PER_SOURCE_CAP = 3

#: Sentences of context either side of a hit. One is enough to resolve the
#: pronouns and elisions that make an isolated clinical sentence unreadable
#: ("It can also cause..."), and small enough that the widened text stays
#: quotable at a glance.
DEFAULT_WINDOW = 1


@dataclass(frozen=True, slots=True)
class WidenedHit:
    """One retrieved sentence, plus the sentences either side of it.

    ``passage`` is the hit itself and is what a citation resolves to — its
    ``text`` is unchanged and still appears verbatim in the cleaned document.
    ``context_text`` is the widened form, for display and for the model to read.
    Keeping them separate is what stops a widened window ever being mistaken
    for the quote a row was authored from.
    """

    passage: Passage
    score: float
    context_text: str

    @property
    def id(self) -> str:
        return self.passage.id

    @property
    def citation(self) -> str:
        return self.passage.citation


def _widen(passages: Sequence[Passage], position: int, window: int) -> str:
    """The hit's text with up to ``window`` neighbours either side.

    Neighbours are index-adjacent passages from the same document.
    ``load_passages`` walks documents, then sections, then paragraphs, then
    sentences in order, so adjacency in the index is adjacency in the source —
    but the source/slug guard is what makes that a checked property rather than
    an assumption that breaks silently the first time the loader changes.
    """
    hit = passages[position]
    start = position
    while start > 0 and position - start < window:
        candidate = passages[start - 1]
        if candidate.source_id != hit.source_id or candidate.slug != hit.slug:
            break
        start -= 1

    end = position
    while end + 1 < len(passages) and end - position < window:
        candidate = passages[end + 1]
        if candidate.source_id != hit.source_id or candidate.slug != hit.slug:
            break
        end += 1

    return " ".join(p.text for p in passages[start : end + 1])


def balanced_search(
    index: PassageIndex,
    query: str,
    embedder: Embedder,
    *,
    k: int = 8,
    per_source_cap: int = DEFAULT_PER_SOURCE_CAP,
    window: int = DEFAULT_WINDOW,
    min_score: float = 0.0,
) -> list[WidenedHit]:
    """Top ``k`` widened hits, with no source taking more than ``per_source_cap``.

    Only passages whose licence permits serving are considered — the same rule
    ``services/model``'s ``/search`` applies, restated here rather than left to
    the caller, because a passage that may not be served must not be able to
    reach a result set by a different code path.

    The cap is applied during selection, not after: candidates are walked in
    descending similarity and skipped when their source is full, so a capped
    result set still contains ``k`` hits whenever ``k`` are available.
    """
    if embedder.name != index.model_name:
        raise ValueError(
            f"index was built with {index.model_name!r} but searched with "
            f"{embedder.name!r}; rebuild it or use the original model"
        )
    if not index.passages:
        return []

    servable = np.array([p.may_be_ingested for p in index.passages], dtype=bool)
    if not servable.any():
        return []

    query_vector = embedder.encode([query], is_query=True)[0]
    scores = cosine_similarity(query_vector, index.vectors)
    scores = np.where(servable, scores, -np.inf)

    taken: dict[str, int] = {}
    hits: list[WidenedHit] = []
    for position in np.argsort(-scores):
        score = float(scores[position])
        if score < min_score or score == -np.inf:
            break
        passage = index.passages[position]
        if taken.get(passage.source_id, 0) >= per_source_cap:
            continue
        taken[passage.source_id] = taken.get(passage.source_id, 0) + 1
        hits.append(
            WidenedHit(
                passage=passage,
                score=score,
                context_text=_widen(index.passages, int(position), window),
            )
        )
        if len(hits) >= k:
            break

    return hits
