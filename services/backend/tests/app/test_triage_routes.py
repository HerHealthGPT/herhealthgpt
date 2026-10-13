"""``POST /triage/turn`` driven over HTTP, session/message persistence (issue #20 item 6).

Uses the REAL knowledge base, like ``test_triage_cli.py`` — a scripted
decision still has to satisfy ``validate_against_knowledge_base`` against
real ``features.yaml``/``red_flags.yaml`` content, not a fixture. No real
OpenRouter or retrieval call: ``ScriptedReasoningClient`` (already
built for exactly this in ``triage/agent.py``) and a small local
``StaticRetrievalClient`` stand in for both.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from httpx import ASGITransport, AsyncClient

from conftest import RecordingEmailSender
from herhealth_backend.app import Database, create_app
from herhealth_backend.app.accounts.google_identity import UnconfiguredGoogleTokenVerifier
from herhealth_backend.app.triage.routes import _mark_rejected, _served_by_payload
from herhealth_backend.triage.agent import (
    AttemptOutcome,
    Message,
    ReasoningAttempt,
    ReasoningResult,
    ScriptedReasoningClient,
    TriageAgent,
)
from herhealth_backend.triage.demo_clients import MvpDemoReasoningClient
from herhealth_backend.triage.vocabulary import ClosedVocabularyViolation

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

    name = "recording"

    def __init__(self, decisions: tuple[TriageDecision, ...]) -> None:
        self._decisions = list(decisions)
        self.histories: list[list[Message]] = []

    def decide(self, *, system_prompt: str, history, context) -> ReasoningResult:
        self.histories.append(list(history))
        return ReasoningResult(
            decision=self._decisions.pop(0),
            attempts=(ReasoningAttempt(client=self.name, outcome=AttemptOutcome.OK),),
        )


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


_A_DECLINE_DECISION = TriageDecision(
    type=DecisionType.DECLINE,
    rationale="This tool covers women's reproductive health only.",
)

#: An informational answer grounded on _A_PASSAGE — ADR 0016. No action
#: code, no matching conditions, and its text lives in answer_text.
_AN_INFORM_DECISION = TriageDecision(
    type=DecisionType.INFORM,
    answer_text=(
        "Our sources describe irregular periods as common and treatable.\n\n"
        "That is general information, not an assessment of anything you are "
        "experiencing."
    ),
    citations=(_A_PASSAGE.id,),
    rationale="She asked what the condition is, having reported no symptom.",
)


async def test_a_declined_message_leaves_the_session_open(database_url: str) -> None:
    """An off-scope question must cost her nothing (ADR 0014). Unlike a
    CONCLUDE, a DECLINE does not close the consultation, so the next turn
    is accepted rather than 409'd — and it carries no action code or
    citation to render."""
    async for client in _build_client(
        database_url, _scripted_agent(_A_DECLINE_DECISION, _A_CONCLUDE_DECISION)
    ):
        await _register_and_sign_in(client, "triage-decline@example.com")

        declined = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "who won world cup 2026"},
        )
        assert declined.status_code == 200, declined.text
        decision = declined.json()["decision"]
        assert decision["type"] == "decline"
        assert decision["action_code"] is None
        assert decision["citations"] == []
        assert decision["cited_passages"] == []
        session_id = declined.json()["session_id"]

        # The session is still hers to continue — the point of the change.
        followed_up = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "sorry — my periods are irregular."},
        )
        assert followed_up.status_code == 200, followed_up.text
        assert followed_up.json()["decision"]["type"] == "conclude"

        listed = await client.get("/triage/sessions")

    assert listed.status_code == 200, listed.text


async def test_an_informational_answer_leaves_the_session_open(database_url: str) -> None:
    """An in-scope question answered rather than triaged (ADR 0016). Like a
    DECLINE and unlike a CONCLUDE it does not close the consultation, so she
    carries on talking afterwards — and it carries no urgency level, while
    still showing the sources it was drawn from."""
    async for client in _build_client(
        database_url, _scripted_agent(_AN_INFORM_DECISION, _A_CONCLUDE_DECISION)
    ):
        await _register_and_sign_in(client, "triage-inform@example.com")

        informed = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "what are irregular periods, exactly?"},
        )
        assert informed.status_code == 200, informed.text
        decision = informed.json()["decision"]
        assert decision["type"] == "inform"
        assert decision["answer_text"].startswith("Our sources describe")
        # No urgency, and nothing named as hers — both enforced by schema.
        assert decision["action_code"] is None
        assert decision["matching_conditions"] == []
        assert decision["red_flag_id"] is None
        # Grounded, and resolved to a real passage so the UI can show it.
        assert decision["citations"] == [_A_PASSAGE.id]
        assert len(decision["cited_passages"]) == 1
        session_id = informed.json()["session_id"]

        # The consultation is still open — the point of the shape.
        followed_up = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "mine have been off for 3 months."},
        )
        assert followed_up.status_code == 200, followed_up.text
        assert followed_up.json()["decision"]["type"] == "conclude"

        transcript = await client.get(f"/triage/sessions/{session_id}")

    assert transcript.status_code == 200, transcript.text
    messages = transcript.json()["messages"]
    # answer_text is what was stored as the assistant's message, so a reopened
    # conversation shows the answer rather than the rationale behind it.
    answered = next(m for m in messages if m["decision"] and m["decision"]["type"] == "inform")
    assert answered["content"].startswith("Our sources describe")


async def test_demo_mode_answers_an_informational_question(database_url: str) -> None:
    """The offline path too, so the inform shape is exercisable without
    OpenRouter."""
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(
        base=base,
        reasoning=MvpDemoReasoningClient(),
        retrieval=StaticRetrievalClient(),
    )

    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-demo-inform@example.com")
        response = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "what is pcos?"},
        )

    assert response.status_code == 200, response.text
    decision = response.json()["decision"]
    assert decision["type"] == "inform"
    assert decision["action_code"] is None
    assert decision["answer_text"]
    assert decision["citations"] == [_A_PASSAGE.id]


async def test_demo_mode_declines_an_off_scope_message(database_url: str) -> None:
    """The offline path too, so the decline is exercisable without OpenRouter."""
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(
        base=base,
        reasoning=MvpDemoReasoningClient(),
        retrieval=StaticRetrievalClient(),
    )

    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-demo-decline@example.com")
        response = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "who won world cup 2026"},
        )

    assert response.status_code == 200, response.text
    decision = response.json()["decision"]
    assert decision["type"] == "decline"
    assert decision["action_code"] is None
    assert decision["citations"] == []


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


async def test_unconfigured_triage_is_unavailable(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``HERHEALTH_TRIAGE_MODE=off`` — triage routes return 503."""
    monkeypatch.setenv("HERHEALTH_TRIAGE_MODE", "off")
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


async def test_demo_mode_triage_works_without_openrouter(database_url: str) -> None:
    """HERHEALTH_TRIAGE_MODE=demo wires offline clients — the local-MVP path."""
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(
        base=base,
        reasoning=MvpDemoReasoningClient(),
        retrieval=StaticRetrievalClient(),
    )

    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-demo@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "My periods have been irregular for months."},
        )
        assert opening.status_code == 200, opening.text
        assert opening.json()["decision"]["type"] == "ask"
        session_id = opening.json()["session_id"]

        follow_up = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "No, I am not pregnant."},
        )
        assert follow_up.status_code == 200, follow_up.text
        assert follow_up.json()["decision"]["type"] == "conclude"


async def test_demo_mode_escalates_persistent_bleeding(database_url: str) -> None:
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(
        base=base,
        reasoning=MvpDemoReasoningClient(),
        retrieval=StaticRetrievalClient(),
    )

    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-bleeding@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "The bleeding does not stop."},
        )
        assert opening.status_code == 200, opening.text
        assert opening.json()["decision"]["type"] == "ask"
        assert "heavy" in opening.json()["decision"]["question_text"].lower()
        session_id = opening.json()["session_id"]

        follow_up = await client.post(
            "/triage/turn",
            json={"session_id": session_id, "message": "I am soaking through pads every hour."},
        )
        assert follow_up.status_code == 200, follow_up.text
        body = follow_up.json()["decision"]
        assert body["type"] == "conclude"
        assert body["action_code"] == "URGENT_SAME_DAY"
        assert body["matching_conditions"] == []
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-list@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        assert opening.status_code == 200, opening.text

        response = await client.get("/triage/sessions")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "concluded"
    assert "irregular periods" in body[0]["preview"]


async def test_get_session_returns_transcript(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-get@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]

        response = await client.get(f"/triage/sessions/{session_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == session_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["decision"]["type"] == "conclude"


async def test_get_someone_elses_session_is_not_found(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-get-owner@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]
        await client.post("/accounts/sign-out")

        await _register_and_sign_in(client, "triage-get-intruder@example.com")
        response = await client.get(f"/triage/sessions/{session_id}")

    assert response.status_code == 404


async def test_delete_session_removes_it_from_the_list(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-delete@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]

        response = await client.delete(f"/triage/sessions/{session_id}")
        assert response.status_code == 204, response.text

        listed = await client.get("/triage/sessions")
        assert listed.status_code == 200, listed.text
        assert listed.json() == []

        missing = await client.get(f"/triage/sessions/{session_id}")
        assert missing.status_code == 404


async def test_delete_someone_elses_session_is_not_found(database_url: str) -> None:
    async for client in _build_client(database_url, _scripted_agent(_A_CONCLUDE_DECISION)):
        await _register_and_sign_in(client, "triage-delete-owner@example.com")
        opening = await client.post(
            "/triage/turn",
            json={"session_id": None, "message": "I have had irregular periods for 3 months."},
        )
        session_id = opening.json()["session_id"]
        await client.post("/accounts/sign-out")

        await _register_and_sign_in(client, "triage-delete-intruder@example.com")
        response = await client.delete(f"/triage/sessions/{session_id}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Attribution (migration 0010): which backend actually answered
# ---------------------------------------------------------------------------


async def test_a_turn_reports_and_stores_the_backend_that_answered(
    database_url: str,
) -> None:
    """``served_by`` reaches both the response and the row.

    Both matter and for different reasons: the response is what a live
    experiment reads, the row is what the write-up is reconstructed from
    weeks later.
    """
    base = load_knowledge_base(KNOWLEDGE)
    agent = TriageAgent(
        base=base,
        reasoning=ScriptedReasoningClient([_A_CONCLUDE_DECISION], name="vllm:herhealth"),
        retrieval=StaticRetrievalClient(),
    )
    async for client in _build_client(database_url, agent):
        await _register_and_sign_in(client, "triage-servedby@example.com")

        response = await client.post(
            "/triage/turn", json={"session_id": None, "message": "irregular periods"}
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["served_by"]["final"] == "vllm:herhealth"
        assert body["served_by"]["attempts"] == [
            {"client": "vllm:herhealth", "outcome": "ok", "detail": None}
        ]

        # And it survives a reload, which is the point of the column.
        detail = await client.get(f"/triage/sessions/{body['session_id']}")
        assert detail.status_code == 200, detail.text
        assistant = [m for m in detail.json()["messages"] if m["role"] == "assistant"]
        assert assistant[0]["served_by"]["final"] == "vllm:herhealth"

        # Her own message carries no attribution — nothing answered it.
        user_messages = [m for m in detail.json()["messages"] if m["role"] == "user"]
        assert user_messages[0]["served_by"] is None


def test_a_turn_the_server_threw_away_is_not_counted_as_a_success() -> None:
    """``_mark_rejected`` is what stops the adapter's success rate being
    inflated by turns this layer refused.

    The client returned a schema-valid decision, so its own trail says ``ok``.
    The route then rejected it for naming something outside the closed
    vocabulary and retried the whole turn. Left as ``ok``, that call would be
    counted as the backend having answered usefully, which it did not.
    """
    trail = (
        ReasoningAttempt("vllm:herhealth", AttemptOutcome.UNREACHABLE, "refused"),
        ReasoningAttempt("openrouter:base", AttemptOutcome.OK),
    )
    marked = _mark_rejected(trail, ClosedVocabularyViolation("menopause is not a condition"))

    # Only the successful call is relabelled — the earlier failure keeps its
    # own reason, which is a different fact about a different backend.
    assert [(a.client, a.outcome) for a in marked] == [
        ("vllm:herhealth", AttemptOutcome.UNREACHABLE),
        ("openrouter:base", AttemptOutcome.REJECTED),
    ]
    assert marked[0].detail == "refused"
    assert marked[1].detail == "menopause is not a condition"


def test_served_by_names_the_last_backend_that_succeeded() -> None:
    payload = _served_by_payload(
        (
            ReasoningAttempt("vllm:herhealth", AttemptOutcome.REJECTED, "bad feature id"),
            ReasoningAttempt("openrouter:base", AttemptOutcome.OK),
        )
    )
    assert payload is not None
    assert payload["final"] == "openrouter:base"
    assert [a["outcome"] for a in payload["attempts"]] == ["rejected", "ok"]


def test_no_attempts_reports_unknown_rather_than_a_default() -> None:
    """A client predating this contract reports nothing. That turn is
    unattributable, and saying so is the honest answer — inventing the
    configured default would put a number in the report that nothing
    measured."""
    assert _served_by_payload(()) is None
