"""Resolve ICD-11 identifiers for the conditions, via the WHO ICD API.

``conditions.yaml`` carries ``icd11: TODO_VERIFY`` on every clinical row because
codes recalled from a language model are unreliable, and a wrong identifier is
worse than an absent one — it looks authoritative. This module fills them from
the only source that can settle it.

**Identifiers only.** WHO ICD terms are non-commercial, so we store the code and
the matched title and nothing else. No definitions, no patient-facing text. Same
rule as UMLS.

**Proposes, never assumes.** A search returns ranked candidates, and a ranked
list is not a decision. The command prints proposals for a human to read and
only writes them with ``--apply``. Where the top match is weak or ambiguous the
condition keeps ``TODO_VERIFY``, because an unfilled field is honest and a wrong
code is not.

This is the second module that opens a socket, after ``ingest.fetch``. The
reason is that the OAuth2 token exchange is a form-encoded POST, which the
GET-only ``Transport`` cannot express. Both network functions here are injected
the same way, so tests stay offline.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from herhealth_data.ingest.fetch import _ssl_context

__all__ = [
    "IcdError",
    "IcdProposal",
    "fetch_token",
    "propose_codes",
    "search_icd",
]

TOKEN_URL: Final[str] = "https://icdaccessmanagement.who.int/connect/token"

#: PINNED, deliberately. The API also serves a "latest release" alias, but a
#: code that can shift between runs is not a stable identifier, which is the
#: only reason we want one. Bumping this is a decision to be made and recorded,
#: not something that should happen because a year rolled over. Available
#: releases are listed at https://id.who.int/icd/release/11/mms.
ICD_RELEASE: Final[str] = "2026-01"

#: The Mortality and Morbidity Statistics linearisation — the coded one. The
#: foundation layer (/icd/entity/search) is richer but its entities have no
#: billing codes, and a code is what makes the identifier useful downstream.
SEARCH_URL: Final[str] = f"https://id.who.int/icd/release/11/{ICD_RELEASE}/mms/search"
SCOPE: Final[str] = "icdapi_access"
TIMEOUT: Final[float] = 30.0

#: Below this the top hit is not trusted and the condition keeps TODO_VERIFY.
#: The API returns a 0-100 relevance score; anything mediocre is ambiguous, and
#: ambiguity is exactly what this project must not resolve by guessing.
MIN_SCORE: Final[float] = 0.4


class IcdError(RuntimeError):
    """The ICD API could not be used."""


@dataclass(frozen=True, slots=True)
class IcdProposal:
    """A candidate code for one condition. Not yet a decision."""

    condition_id: str
    query: str
    code: str | None
    title: str | None
    score: float
    alternatives: tuple[tuple[str, str], ...] = ()

    @property
    def is_confident(self) -> bool:
        return self.code is not None and self.score >= MIN_SCORE

    def describe(self) -> str:
        if not self.is_confident:
            reason = "no match" if self.code is None else f"weak match ({self.score:.2f})"
            return f"  {self.condition_id:<30} TODO_VERIFY   -- {reason}, left unfilled"
        line = f"  {self.condition_id:<30} {self.code:<12} {self.title} ({self.score:.2f})"
        if self.alternatives:
            others = "; ".join(f"{c} {t}" for c, t in self.alternatives[:2])
            line += f"\n  {'':<30} also considered: {others}"
        return line


#: ``(client_id, client_secret) -> access token``. Injected so tests are offline.
TokenFetcher = Callable[[str, str], str]

#: ``(term, token) -> parsed search response``. Injected for the same reason.
Searcher = Callable[[str, str], dict[str, object]]


def fetch_token(client_id: str, client_secret: str) -> str:
    """Exchange client credentials for an access token."""
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": SCOPE,
            "grant_type": "client_credentials",
        }
    ).encode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=_ssl_context()) as response:
            payload = json.loads(response.read())
    except Exception as error:  # noqa: BLE001 - reported, not swallowed
        raise IcdError(f"could not obtain an ICD token: {error}") from error

    token = payload.get("access_token")
    if not isinstance(token, str):
        raise IcdError("ICD token response contained no access_token")
    return token


def search_icd(term: str, token: str) -> dict[str, object]:
    """Search the ICD-11 MMS linearisation for a term."""
    query = urllib.parse.urlencode({"q": term, "flatResults": "true", "useFlexisearch": "false"})
    request = urllib.request.Request(
        f"{SEARCH_URL}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Accept-Language": "en",
            "API-Version": "v2",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=_ssl_context()) as response:
            result: dict[str, object] = json.loads(response.read())
            return result
    except Exception as error:  # noqa: BLE001
        raise IcdError(f"ICD search failed for {term!r}: {error}") from error


def _strip_markup(title: str) -> str:
    """Search results wrap matched words in em tags."""
    return title.replace("<em class='found'>", "").replace("</em>", "").strip()


def propose_codes(
    conditions: Sequence[tuple[str, str]],
    token: str,
    searcher: Searcher = search_icd,
) -> list[IcdProposal]:
    """One proposal per condition, in the order given.

    ``conditions`` is ``(condition_id, query)`` — the query is the condition's
    label, or a better search term where the label carries our own wording.
    """
    proposals: list[IcdProposal] = []
    for condition_id, query in conditions:
        payload = searcher(query, token)
        entities = payload.get("destinationEntities") or []
        if not isinstance(entities, list) or not entities:
            proposals.append(IcdProposal(condition_id, query, None, None, 0.0))
            continue

        ranked: list[tuple[str, str, float]] = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            code = entity.get("theCode")
            title = entity.get("title")
            score = entity.get("score", 0.0)
            if isinstance(code, str) and isinstance(title, str):
                ranked.append((code, _strip_markup(title), float(score or 0.0)))

        if not ranked:
            proposals.append(IcdProposal(condition_id, query, None, None, 0.0))
            continue

        best_code, best_title, best_score = ranked[0]
        proposals.append(
            IcdProposal(
                condition_id=condition_id,
                query=query,
                code=best_code,
                title=best_title,
                score=best_score,
                alternatives=tuple((c, t) for c, t, _ in ranked[1:4]),
            )
        )
    return proposals


def credentials_from_env() -> tuple[str, str]:
    """Read credentials. They live in a gitignored env file, never in the repo."""
    client_id = os.environ.get("WHO_ICD_CLIENT_ID", "").strip()
    secret = os.environ.get("WHO_ICD_CLIENT_SECRET", "").strip()
    if not client_id or not secret:
        raise IcdError(
            "WHO_ICD_CLIENT_ID and WHO_ICD_CLIENT_SECRET are not set. "
            "Copy infra/envs/data.env.example to infra/envs/data.env and fill them in."
        )
    return client_id, secret
