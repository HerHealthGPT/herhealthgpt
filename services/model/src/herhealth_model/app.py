"""The FastAPI application: how the service boots and its one real route.

:func:`create_app` is a factory, mirroring ``herhealth_backend.app.main``'s
shape, so a test can build an app around an in-memory index and a fake
embedder and never touch disk or download model weights. Pass ``index`` and
``embedder`` in and the app uses them as-is; pass neither and the lifespan
loads the real ``PassageIndex`` from disk and the real ``bge-m3`` model at
start-up, per ``config.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from herhealth_data.ingest.fetch import http_get
from herhealth_data.ingest.robots import RobotsPolicy
from herhealth_data.retrieval.embed import Embedder, SentenceTransformerEmbedder
from herhealth_data.retrieval.index import PassageIndex
from pydantic import BaseModel

from herhealth_model.config import embedding_model_name, index_dir, min_score
from herhealth_model.web_fallback import (
    CandidateUrlFinder,
    FallbackPassage,
    NullCandidateUrlFinder,
    WebSearchFallback,
)

__all__ = ["create_app"]

#: Where fallback attempts are logged for later human review — ADR 0012 §3,
#: rule 7. Alongside the index rather than under services/model/ itself, so
#: it survives a redeploy of this service the same way build/index does.
_REVIEW_QUEUE_PATH = Path("build/web_fallback_review_queue.jsonl")


class SearchRequest(BaseModel):
    query: str
    k: int = 8


def _passage_to_retrieved(passage: object, score: float) -> RetrievedPassage:
    """``herhealth_data.retrieval.passages.Passage`` -> the boundary-safe
    ``RetrievedPassage`` contract. Kept as one function so the field mapping
    is defined once rather than at each call site."""
    return RetrievedPassage(
        id=passage.id,  # type: ignore[attr-defined]
        passage_type=PassageType(passage.passage_type),  # type: ignore[attr-defined]
        source_id=passage.source_id,  # type: ignore[attr-defined]
        text=passage.text,  # type: ignore[attr-defined]
        citation=passage.citation,  # type: ignore[attr-defined]
        score=score,
        condition_id=passage.condition_id,  # type: ignore[attr-defined]
        feature_id=passage.feature_id,  # type: ignore[attr-defined]
        value=passage.value,  # type: ignore[attr-defined]
        strength=passage.strength,  # type: ignore[attr-defined]
    )


def _fallback_to_retrieved(passage: FallbackPassage) -> RetrievedPassage:
    return RetrievedPassage(
        id=passage.id,
        passage_type=PassageType.LIVE_FALLBACK,
        source_id=passage.source_id,
        text=passage.text,
        citation=passage.citation,
        score=passage.score,
        condition_id=None,
        feature_id=None,
        value=None,
        strength=None,
    )


def create_app(
    index: PassageIndex | None = None,
    embedder: Embedder | None = None,
    candidate_finder: CandidateUrlFinder | None = None,
) -> FastAPI:
    """Build the application.

    ``index``/``embedder`` given: the app uses them as-is (tests). Neither
    given: the lifespan loads the real index from ``config.index_dir()`` and
    the real embedder named by ``config.embedding_model_name()`` — this is
    what downloads ``bge-m3``'s weights on first run. ``candidate_finder``
    defaults to :class:`~herhealth_model.web_fallback.NullCandidateUrlFinder`
    — see that class's docstring for why that is the safe default rather
    than a limitation of this function.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "index", None) is None:
            directory = index_dir()
            if not (directory / "manifest.json").is_file():
                raise RuntimeError(
                    f"no passage index at {directory} — run "
                    "`python -m herhealth_data.cli index` first "
                    "(needs the retrieval extra; downloads bge-m3 on first run)"
                )
            app.state.index = PassageIndex.load(directory)
        if getattr(app.state, "embedder", None) is None:
            app.state.embedder = SentenceTransformerEmbedder(embedding_model_name())
        if getattr(app.state, "fallback", None) is None:
            app.state.fallback = WebSearchFallback(
                finder=candidate_finder or NullCandidateUrlFinder(),
                robots=RobotsPolicy(transport=http_get),
                transport=http_get,
                embedder=app.state.embedder,
                review_queue_path=_REVIEW_QUEUE_PATH,
            )
        yield

    app = FastAPI(title="HerHealthGPT retrieval service", lifespan=lifespan)
    if index is not None:
        app.state.index = index
    if embedder is not None:
        app.state.embedder = embedder
    if candidate_finder is not None:
        app.state.fallback = WebSearchFallback(
            finder=candidate_finder,
            robots=RobotsPolicy(transport=http_get),
            transport=http_get,
            embedder=embedder or SentenceTransformerEmbedder(embedding_model_name()),
            review_queue_path=_REVIEW_QUEUE_PATH,
        )

    @app.get("/health")
    async def health() -> JSONResponse:
        ok = getattr(app.state, "index", None) is not None and getattr(app.state, "embedder", None) is not None
        return JSONResponse({"status": "ok" if ok else "unavailable"}, status_code=200 if ok else 503)

    @app.post("/search", response_model=list[RetrievedPassage])
    async def search(request: SearchRequest) -> list[RetrievedPassage]:
        index: PassageIndex = app.state.index
        embedder: Embedder = app.state.embedder
        fallback: WebSearchFallback = app.state.fallback

        hits = index.search(
            request.query,
            embedder,
            k=request.k,
            where=lambda p: p.may_be_ingested,  # ADR 0011: mandatory, not optional
        )
        threshold = min_score()
        usable = [h for h in hits if h.score >= threshold]
        if usable:
            return [_passage_to_retrieved(h.passage, h.score) for h in usable]

        # Primary index had nothing usable — ADR 0012 §3 fallback path.
        fallback_hits = fallback.run(request.query, top_k=request.k)
        return [_fallback_to_retrieved(p) for p in fallback_hits]

    return app
