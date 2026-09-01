"""HTTP surface for Accounts: registration, sessions, email verification.

Kept a thin translation layer on purpose — the use-case modules
(``registration.py``, ``sign_in.py``, ``sessions.py``, ``email_verification.py``)
are where the actual decisions live, so each can be tested without an ASGI
client. Domain exceptions those use cases raise are not caught here: they
propagate to the handlers ``error_handlers.py`` registers once against the
whole app, so this module needs no per-route try/except to keep in sync as
Accounts grows.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from herhealth_backend.app.accounts.cookies import (
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from herhealth_backend.app.accounts.current_user import get_current_user
from herhealth_backend.app.accounts.email_sender import EmailSender
from herhealth_backend.app.accounts.email_verification import (
    request_verification_resend,
    send_verification_code,
    verify_email,
)
from herhealth_backend.app.accounts.errors import InvalidSession
from herhealth_backend.app.accounts.google_identity import GoogleTokenVerifier
from herhealth_backend.app.accounts.google_sign_in import sign_in_with_google
from herhealth_backend.app.accounts.models import User
from herhealth_backend.app.accounts.password_reset import request_password_reset, reset_password
from herhealth_backend.app.accounts.password_reset_policy import CODE_LENGTH as RESET_CODE_LENGTH
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sessions import (
    end_all_sessions,
    end_session,
    get_active_session,
    refresh_session,
)
from herhealth_backend.app.accounts.sign_in import sign_in as sign_in_user
from herhealth_backend.app.accounts.verification_code_policy import CODE_LENGTH
from herhealth_backend.app.db import Database

__all__ = ["router"]

router = APIRouter(prefix="/accounts", tags=["accounts"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    #: No length constraints here, deliberately. FastAPI's default validation-
    #: error response echoes the raw offending value verbatim (Pydantic's
    #: `.errors()` includes it under "input", and `hide_input_in_errors` only
    #: affects the human-readable str() form, not that dict) — so a
    #: schema-level Field(max_length=...) here would leak an oversized
    #: password straight into the 422 body, which is exactly what #8's
    #: "plaintext appears nowhere, including logs" criterion forbids.
    #: check_password_strength enforces both the floor and the ceiling
    #: instead, before hash_password ever runs, and only ever reports static
    #: reason strings — never the password itself.
    password: str


class SignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    #: Fixed-length, unlike RegisterRequest.password above — a code is not a
    #: secret in the same sense (short-lived, single-use, never a credential
    #: on its own), so echoing an oversized value back in a 422 carries none
    #: of that field's risk.
    code: str = Field(min_length=CODE_LENGTH, max_length=CODE_LENGTH)


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class GoogleSignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: str


class RequestPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    #: Fixed-length, like VerifyEmailRequest.code — a code is not a secret in
    #: the same sense a password is, so echoing an oversized value back in a
    #: 422 carries none of RegisterRequest.password's risk.
    code: str = Field(min_length=RESET_CODE_LENGTH, max_length=RESET_CODE_LENGTH)
    #: No length constraints here, deliberately — see RegisterRequest.password's
    #: own comment. check_password_strength enforces both the floor and the
    #: ceiling before hash_password ever runs.
    new_password: str


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool


def _require_refresh_token(request: Request) -> str:
    """The refresh-token cookie, or raise. For the two routes that cannot
    proceed without one — ``sign-out`` deliberately differs: it treats a
    missing cookie as already signed out rather than an error.
    """
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if raw_refresh_token is None:
        raise InvalidSession()
    return raw_refresh_token


@router.post(
    "/register",
    response_model=UserSummary,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, request: Request) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    email_sender: EmailSender = request.app.state.email_sender
    async with database.session() as session:
        user = await register_user(session, email=payload.email, password=payload.password)
        await send_verification_code(session, secret, email_sender, user)

    return UserSummary(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post("/sign-in", response_model=UserSummary)
async def sign_in(payload: SignInRequest, request: Request, response: Response) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        user, access_token, refresh_token = await sign_in_user(
            session, secret, email=payload.email, password=payload.password
        )

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return UserSummary(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post("/sign-in/google", response_model=UserSummary)
async def sign_in_google(
    payload: GoogleSignInRequest, request: Request, response: Response
) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    google_verifier: GoogleTokenVerifier = request.app.state.google_verifier
    async with database.session() as session:
        user, access_token, refresh_token = await sign_in_with_google(
            session, secret, google_verifier, id_token=payload.id_token
        )

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return UserSummary(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(request: Request, response: Response) -> None:
    raw_refresh_token = _require_refresh_token(request)

    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        access_token = await refresh_session(session, secret, raw_refresh_token)
        await session.commit()

    set_auth_cookies(response, access_token=access_token)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(request: Request, response: Response) -> None:
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if raw_refresh_token is not None:
        database: Database = request.app.state.database
        async with database.session() as session:
            await end_session(session, raw_refresh_token)
            await session.commit()
    clear_auth_cookies(response)


@router.post("/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_everywhere(request: Request, response: Response) -> None:
    # Identified by the refresh token, not the access token: a woman whose
    # access token has already expired (15 minutes, unrevocable — see
    # CONTEXT.md) but who still holds a valid refresh token is exactly who
    # most urgently needs this endpoint to work, e.g. right after realising
    # her phone was stolen.
    raw_refresh_token = _require_refresh_token(request)

    database: Database = request.app.state.database
    async with database.session() as session:
        active_session = await get_active_session(session, raw_refresh_token)
        await end_all_sessions(session, active_session.user_id)
        await session.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=UserSummary)
async def me(current_user: User = Depends(get_current_user)) -> UserSummary:  # noqa: B008
    return UserSummary(
        id=current_user.id, email=current_user.email, email_verified=current_user.email_verified
    )


@router.post("/verify-email", response_model=UserSummary)
async def verify_email_route(payload: VerifyEmailRequest, request: Request) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        user = await verify_email(session, secret, email=payload.email, code=payload.code)

    return UserSummary(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post("/verify-email/resend", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(payload: ResendVerificationRequest, request: Request) -> None:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    email_sender: EmailSender = request.app.state.email_sender
    async with database.session() as session:
        await request_verification_resend(session, secret, email_sender, email=payload.email)


@router.post("/reset-password/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_reset_route(
    payload: RequestPasswordResetRequest, request: Request
) -> None:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    email_sender: EmailSender = request.app.state.email_sender
    async with database.session() as session:
        await request_password_reset(session, secret, email_sender, email=payload.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password_route(
    payload: ResetPasswordRequest, request: Request, response: Response
) -> None:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        await reset_password(
            session,
            secret,
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
        )
    # Every session on the account was just ended (#12's fourth criterion) —
    # clear whatever auth cookies this browser happens to be holding too, the
    # same as sign_out does, in case she completed the reset from a device
    # that was still signed in under the password someone else knew.
    clear_auth_cookies(response)
