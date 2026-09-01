"""``POST /triage/turn`` driven over HTTP, session/message persistence (issue #20 item 6).

Uses the REAL knowledge base, like ``test_triage_cli.py`` — a scripted
decision still has to satisfy ``validate_against_knowledge_base`` against
real ``features.yaml``/``red_flags.yaml`` content, not a fixture. No real
OpenRouter or ``services/model`` call: ``ScriptedReasoningClient`` (already
built for exactly this in ``triage/agent.py``) and a small local
``StaticRetrievalClient`` stand in for both.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from httpx import ASGITransport, AsyncClient

from conftest import RecordingEmailSender
from herhealth_backend.app import Database, create_app
from herhealth_backend.app.accounts.google_identity import UnconfiguredGoogleTokenVerifier
from herhealth_backend.triage.agent import Message, ScriptedReasoningClient, TriageAgent

REPO = Path(__file__).resolve().parents[4]
KNOWLEDGE = REPO / "knowledge"

_A_PASSAGE = RetrievedPassage(
    id="0123456789abcdef",
    passage_type=PassageType.SOURCE_PASSAGE,
    source_id="womenshealth",
    text="Irregular or heavy, painful periods are not normal.",
    citation="womenshealth/menstruation § Menstrual Cycle",
    score=0.7,
)

#: A CONCLUDE decision grounded on _A_PASSAGE, valid against the real
#: knowledge base regardless of which conditions/features exist there.
_A_CONCLUDE_DECISION = TriageDecision(
    type=DecisionType.CONCLUDE,
    action_code=ActionCode.ROUTINE_APPOINTMENT,
    citations=(_A_PASSAGE.id,),
    rationale="testing",
)

#: "pregnancy_status" is a real id in knowledge/features.yaml.
_AN_ASK_DECISION = TriageDecision(
    type=DecisionType.ASK,
    next_feature_id="pregnancy_status",
    question_text="Are you currently pregnant or suspect you might be?",
    citations=(_A_PASSAGE.id,),
    rationale="testing",
)


class StaticRetrievalClient:
    """A ``RetrievalClient`` returning the same fixed passages every call —
    the retrieval-side equivalent of ``ScriptedReasoningClient``."""

    def __init__(self, passages: tuple[RetrievedPassage, ...] = (_A_PASSAGE,)) -> None:
        self._passages = passages
        self.queries: list[str] = []

    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        self.queries.append(query)
        return list(self._passages)


class RecordingReasoningClient:
    """Like ``ScriptedReasoningClient``, but also remembers the ``history``
    it was shown on each call — so a test can confirm a later turn actually
    saw an earlier one, not just that persistence exists."""

    def __init__(self, decisions: tuple[TriageDecision, ...]) -> None:
        self._decisions = list(decisions)
        self.histories: list[list[Message]] = []

    def decide(self, *, system_prompt: str, history, context) -> TriageDecision:
        self.histories.append(list(history))
        return self._decisions.pop(0)


def _scripted_agent(*decisions: TriageDecision) -> TriageAgent:
    base = load_knowledge_base(KNOWLEDGE)
    return TriageAgent(
        base=base,
        reasoning=ScriptedReasoningClient(decisions),
        retrieval=StaticRetrievalClient(),
    )


async def _build_client(database_url: str, agent: TriageAgent) -> AsyncIterator[AsyncClient]:
    """Shared app-building body for ``triage_client`` and any test that
    needs a differently-scripted agent — the same escape hatch
    ``test_health.py`` uses for its unreachable-database case."""
    database = Database(database_url)
    app = create_app(
        database=database,
        session_secret="test-only-session-secret-do-not-use-in-production",
        email_sender=RecordingEmailSender(),
        google_verifier=UnconfiguredGoogleTokenVerifier(),
        triage_agent=agent,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client
    await database.dispose()


@pytest_asyncio.fixture
async def triage_client(database_url: str) -> AsyncIterator[AsyncClient]:
    """Like conftest's ``client``, but with a working ``triage_agent`` —
    the shared fixture's default (built from ``OPENROUTER_API_KEY``, unset
    in tests) always 503s. One scripted CONCLUDE decision by default; a test
    needing a different script uses ``_build_client`` directly instead.
    """
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        yield client


async def _register_and_sign_in(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/accounts/register", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/accounts/sign-in", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 200, response.text


async def test_opening_a_session_creates_one_and_returns_its_id(
    triage_client: AsyncClient,
) -> None:
    await _register_and_sign_in(triage_client, "triage-open@example.com")

    response = await triage_client.post(
        "/triage/turn",
        json={"session_id": None, "message": "I have had irregular periods for 3 months."},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"]
    assert body["decision"]["type"] == "conclude"
    assert body["decision"]["action_code"] == "ROUTINE_APPOINTMENT"


async def test_continuing_a_session_replays_the_prior_turn_to_the_model(
    database_url: str,
) -> None:
    reasoning = RecordingReasoningClient((_AN_ASK_DECISION, _A_CONCLUDE_DECISION))
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(base=base, reasoning=reasoning, retrieval=StaticRetrievalClient())

    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-continue@example.com")

        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        assert opening.status_code == 200, opening.text
        opening_body = opening.json()
        assert opening_body["decision"]["type"] == "ask"
        session_id = opening_body["session_id"]

        second = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "No, I don't think so."},
        )
        assert second.status_code == 200, second.text
        assert second.json()["decision"]["type"] == "conclude"

    # The second call's history must contain everything the first turn
    # produced — her opening message, the assistant's question, and her
    # answer — not just the newest message alone.
    assert len(reasoning.histories) == 2
    second_call_history = reasoning.histories[1]
    contents = [message.content for message in second_call_history]
    assert "I have had irregular periods for 3 months." in contents
    assert "Are you currently pregnant or suspect you might be?" in contents
    assert "No, I don't think so." in contents


async def test_a_second_users_session_id_is_not_found(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-owner@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]
        await client.post("/accounts/sign-out")

        await _register_and_sign_in(client, "triage-intruder@example.com")
        response = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "let me in"},
        )

    assert response.status_code == 404


async def test_continuing_a_concluded_session_is_refused(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-concluded@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]

        response = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "one more thing..."},
        )

    assert response.status_code == 409


async def test_an_empty_message_is_refused(triage_client: AsyncClient) -> None:
    await _register_and_sign_in(triage_client, "triage-empty@example.com")

    response = await triage_client.post(
        "/triage/turn", json={"session_id": None, "message": ""}
    )

    assert response.status_code == 422


async def test_signed_out_is_unauthorized(triage_client: AsyncClient) -> None:
    response = await triage_client.post(
        "/triage/turn",
        json={"session_id": None, "message": "I have had irregular periods for 3 months."},
    )

    assert response.status_code == 401


async def test_unconfigured_triage_is_unavailable(database_url: str) -> None:
    """No ``triage_agent`` passed to ``create_app`` at all — simulating a
    deployment with ``OPENROUTER_API_KEY`` unset, the same state
    ``_build_triage_agent`` in app/main.py produces (returns ``None``) when
    that variable is absent.
    """
    database = Database(database_url)
    app = create_app(
        database=database,
        session_secret="test-only-session-secret-do-not-use-in-production",
        email_sender=RecordingEmailSender(),
        google_verifier=UnconfiguredGoogleTokenVerifier(),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        await _register_and_sign_in(client, "triage-unconfigured@example.com")
        response = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
    await database.dispose()

    assert response.status_code == 503
