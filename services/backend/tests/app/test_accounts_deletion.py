"""``DELETE /accounts/me`` — issue #14 account deletion acceptance tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from herhealth_contracts.decision import DecisionType, TriageDecision
from herhealth_contracts.knowledge import ActionCode
from herhealth_contracts.loading import load_knowledge_base
from herhealth_contracts.retrieval import PassageType, RetrievedPassage
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from conftest import RecordingEmailSender
from herhealth_backend.app import Database, create_app
from herhealth_backend.app.accounts.google_identity import UnconfiguredGoogleTokenVerifier
from herhealth_backend.app.accounts.models import (
    Credential,
    EmailVerificationCode,
    PasswordResetCode,
    PasswordResetSend,
    Session,
    SignInFailure,
    User,
    VerificationCodeSend,
)
from herhealth_backend.app.triage.models import ConsultationSession, Message
from herhealth_backend.triage.agent import ScriptedReasoningClient, TriageAgent

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

_A_CONCLUDE_DECISION = TriageDecision(
    type=DecisionType.CONCLUDE,
    action_code=ActionCode.ROUTINE_APPOINTMENT,
    citations=(_A_PASSAGE.id,),
    rationale="testing",
)


class StaticRetrievalClient:
    def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]:
        return [_A_PASSAGE]


def _scripted_agent() -> TriageAgent:
    base = load_knowledge_base(KNOWLEDGE)
    return TriageAgent(
        base=base,
        reasoning=ScriptedReasoningClient((_A_CONCLUDE_DECISION,)),
        retrieval=StaticRetrievalClient(),
    )


async def _build_client(database_url: str) -> AsyncIterator[AsyncClient]:
    database = Database(database_url)
    app = create_app(
        database=database,
        session_secret="test-only-session-secret-do-not-use-in-production",
        email_sender=RecordingEmailSender(),
        google_verifier=UnconfiguredGoogleTokenVerifier(),
        triage_agent=_scripted_agent(),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client
    await database.dispose()


async def _register_and_sign_in(client: AsyncClient, email: str) -> uuid.UUID:
    response = await client.post(
        "/accounts/register", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 201, response.text
    user_id = uuid.UUID(response.json()["id"])
    response = await client.post(
        "/accounts/sign-in", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 200, response.text
    return user_id


@pytest_asyncio.fixture
async def deletion_client(database_url: str) -> AsyncIterator[AsyncClient]:
    async for client in _build_client(database_url):
        yield client


async def _count_for_user(session, model, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(model).where(model.user_id == user_id)
    return await session.scalar(stmt)


async def _count_messages_for_user(session, user_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(ConsultationSession, Message.session_id == ConsultationSession.id)
        .where(ConsultationSession.user_id == user_id)
    )


async def test_delete_account_removes_every_user_referencing_row(
    database_url: str, deletion_client: AsyncClient
) -> None:
    email = "delete-account-all@example.com"
    user_id = await _register_and_sign_in(deletion_client, email)

    # Populate email-indexed throttle tables.
    await deletion_client.post(
        "/accounts/sign-in",
        json={"email": email, "password": "wrong-password-1"},
    )

    opening = await deletion_client.post(
        "/triage/turn",
        json={"session_id": None, "message": "I have had irregular periods for 3 months."},
    )
    assert opening.status_code == 200, opening.text

    response = await deletion_client.delete("/accounts/me")
    assert response.status_code == 204, response.text

    me = await deletion_client.get("/accounts/me")
    assert me.status_code == 401

    database = Database(database_url)
    async with database.session() as session:
        user_count = await session.scalar(
            select(func.count()).select_from(User).where(User.id == user_id)
        )
        assert user_count == 0
        assert await _count_for_user(session, Credential, user_id) == 0
        assert await _count_for_user(session, Session, user_id) == 0
        assert await _count_for_user(session, EmailVerificationCode, user_id) == 0
        assert await _count_for_user(session, PasswordResetCode, user_id) == 0
        assert await _count_for_user(session, ConsultationSession, user_id) == 0
        assert await _count_messages_for_user(session, user_id) == 0
        assert (
            await session.scalar(
                select(func.count()).select_from(SignInFailure).where(SignInFailure.email == email)
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(VerificationCodeSend)
                .where(VerificationCodeSend.email == email)
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(PasswordResetSend)
                .where(PasswordResetSend.email == email)
            )
            == 0
        )
    await database.dispose()


async def test_delete_account_requires_authentication(deletion_client: AsyncClient) -> None:
    response = await deletion_client.delete("/accounts/me")
    assert response.status_code == 401
