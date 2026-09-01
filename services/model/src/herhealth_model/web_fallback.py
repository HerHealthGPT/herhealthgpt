"""The guarded web-search fallback — docs/adr/0012-openrouter-reasoning-and-guarded-web-fallback.md, §3.

Fires only when the reviewed index has nothing usable for a query (that
decision is the caller's — see ``app.py``). Every rule from the ADR's §3 is
enforced in one place, here, so "is this safe" is a question about this
module rather than something a caller could get wrong by forgetting a check.

**What this module deliberately does not do.** It cannot choose WHICH urls,
among the five allowed domains, are relevant to a query — that needs a real
search provider (Bing/Google/Brave/etc.), an account and an API key this
project has not chosen or paid for. :class:`CandidateUrlFinder` names that
seam explicitly, the same way ``ReasoningClient`` named "a real model" before
OpenRouter was chosen (``herhealth_backend.triage.agent``).
:class:`NullCandidateUrlFinder` is the safe default: until a real finder is
configured, every call finds zero candidates, so this fallback is wired in
architecturally but never actually fetches anything — a search behaves
exactly as if this module did not exist, rather than guessing at a URL.
Guessing a URL is the one thing this whole project's sourcing discipline
refuses to do (see CLAUDE.md, "You must NEVER generate or guess URLs"), and
that refusal applies here as much as anywhere else.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

import numpy as np
from herhealth_data.ingest.clean import clean_html
from herhealth_data.ingest.config import USER_AGENT, Transport
from herhealth_data.ingest.robots import RobotsPolicy
from herhealth_data.retrieval.embed import Embedder, cosine_similarity
from herhealth_data.retrieval.passages import split_sentences

from herhealth_model.config import ALLOWED_FALLBACK_DOMAINS, MEDLINEPLUS_EXCLUDED_PATH_FRAGMENT

__all__ = [
    "CandidateUrlFinder",
    "FallbackPassage",
    "NullCandidateUrlFinder",
    "WebSearchFallback",
]

#: Same floor load_passages uses for a real passage — below this, a
#: "sentence" is heading debris, not a clinical statement.
_MIN_SENTENCE_CHARS = 40


@dataclass(frozen=True, slots=True)
class FallbackPassage:
    """One live-fetched sentence, shaped enough to become a ``RetrievedPassage``.

    Deliberately not ``herhealth_data.retrieval.passages.Passage``: that
    type's ``id``/``citation`` assume the text lives in ``build/clean/`` and
    is eligible for the served index. This text is neither — it is used once
    and never persisted (§3, rule 3) — so giving it the same type would be a
    standing invitation to accidentally index it later.
    """

    source_id: str
    url: str
    heading: str
    text: str
    score: float

    @property
    def id(self) -> str:
        """Same construction as ``Passage.id`` (sha256, first 16 hex chars),
        keyed on the live url instead of a corpus slug — there is no slug for
        content that was never written to ``build/clean/``.
        """
        digest = hashlib.sha256(f"{self.url}\x00{self.text}".encode()).hexdigest()
        return digest[:16]

    @property
    def citation(self) -> str:
        """Marked "(live)" so a citation from this path is never visually
        indistinguishable from a reviewed one, even before passage_type is
        checked programmatically."""
        return f"{self.source_id} (live, unreviewed) — {self.url}"


@runtime_checkable
class CandidateUrlFinder(Protocol):
    """Anything that can propose candidate URLs for a query, restricted to
    the given domains. THE SEAM THIS MODULE DOES NOT IMPLEMENT — see the
    module docstring. A real implementation needs a chosen, provisioned
    search provider; wire one in before this fallback can do anything beyond
    exist.
    """

    def find(self, query: str, *, domains: Sequence[str], limit: int = 3) -> list[str]: ...


class NullCandidateUrlFinder:
    """The safe default. Always finds nothing. See the module docstring —
    this is what makes an unconfigured fallback inert rather than dangerous.
    """

    def find(self, query: str, *, domains: Sequence[str], limit: int = 3) -> list[str]:
        return []


def _domain_of(url: str) -> str:
    return urlsplit(url).netloc.removeprefix("www.")


def _source_id_for(url: str) -> str | None:
    """The knowledge-base source id a url belongs to, or None if the domain
    is not one of the five allowed — §3, rule 1."""
    domain = _domain_of(url)
    for allowed_domain, source_id in ALLOWED_FALLBACK_DOMAINS.items():
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return source_id
    return None


@dataclass
class WebSearchFallback:
    """Enforces every rule in ADR 0012 §3. One entry point: :meth:`run`.

    ``finder`` is the one seam a real deployment must supply for this to do
    anything (see :class:`CandidateUrlFinder`'s docstring); everything else
    here is real, working enforcement of the ADR's safety rules, not a stub.
    """

    finder: CandidateUrlFinder
    robots: RobotsPolicy
    transport: Transport
    embedder: Embedder
    review_queue_path: Path
    candidate_limit: int = 3

    def run(self, query: str, *, top_k: int = 3) -> list[FallbackPassage]:
        """Find, fetch, and rank live passages for ``query``. Logs the
        attempt regardless of outcome — rule 7, the review-queue feed."""
        candidates = self.finder.find(
            query, domains=tuple(ALLOWED_FALLBACK_DOMAINS), limit=self.candidate_limit
        )
        self._log_attempt(query, candidates)

        fetched: list[FallbackPassage] = []
        for url in candidates:
            fetched.extend(self._fetch_one(url))

        if not fetched:
            return []
        return self._rank(query, fetched, top_k=top_k)

    def _fetch_one(self, url: str) -> list[FallbackPassage]:
        """One url, gated by every rule that must hold before a byte is
        requested — mirrors ``herhealth_data.ingest.fetch._fetch_one``'s
        ordering: licence guard, then robots, then (and only then) request.
        """
        source_id = _source_id_for(url)
        if source_id is None:
            return []  # rule 1: domain-restricted, not open web

        if source_id == "medlineplus" and MEDLINEPLUS_EXCLUDED_PATH_FRAGMENT in url:
            return []  # rule 2: same licence exclusion as batch ingestion

        if not self.robots.is_allowed(url, USER_AGENT):
            return []  # rule 2: same robots.txt check as batch ingestion

        try:
            status, body = self.transport(url, USER_AGENT)
        except RuntimeError:
            return []  # unreachable is not the same as disallowed; just skip it
        if status != 200 or not body:
            return []

        sections = clean_html(body)
        return [
            FallbackPassage(source_id=source_id, url=url, heading=section.heading, text=sentence, score=0.0)
            for section in sections
            for sentence in split_sentences(section.text)
            if len(sentence) >= _MIN_SENTENCE_CHARS
        ]

    def _rank(
        self, query: str, passages: Sequence[FallbackPassage], *, top_k: int
    ) -> list[FallbackPassage]:
        """Same cosine-similarity ranking the reviewed index uses
        (``herhealth_data.retrieval.index.PassageIndex.search``), applied to
        this one page's sentences instead of the whole corpus — there is no
        persisted index here to reuse, only the embedder."""
        query_vector = self.embedder.encode([query], is_query=True)[0]
        matrix = self.embedder.encode([p.text for p in passages])
        scores = cosine_similarity(query_vector, matrix)
        order = np.argsort(-scores)[: min(top_k, len(passages))]
        return [
            FallbackPassage(
                source_id=passages[i].source_id,
                url=passages[i].url,
                heading=passages[i].heading,
                text=passages[i].text,
                score=float(scores[i]),
            )
            for i in order
        ]

    def _log_attempt(self, query: str, candidates: Sequence[str]) -> None:
        """Append-only record of every fallback attempt, hit or miss — rule
        7: this is what lets a query that keeps coming up empty become a
        candidate for a properly authored evidence batch later. Never
        raises: a logging failure must not take down the response this
        fallback exists to help produce.
        """
        try:
            self.review_queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self.review_queue_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "logged_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "query": query,
                            "candidate_urls": list(candidates),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass
