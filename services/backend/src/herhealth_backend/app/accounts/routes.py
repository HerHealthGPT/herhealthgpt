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
from datetime import date, datetime

from anyio import to_thread
from fastapi import APIRouter, Depends, Request, Response, UploadFile, status
from herhealth_contracts.cycle import CycleExtraction
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from herhealth_backend.app.accounts.account_deletion import delete_user_account
from herhealth_backend.app.accounts.cookies import (
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from herhealth_backend.app.accounts.current_user import get_current_user
from herhealth_backend.app.accounts.cycle_import import (
    MAX_UPLOAD_BYTES,
    ModelCycleExtractor,
    clear_cycle_data,
    cycle_data_for,
    extract_cycle_data,
    save_cycle_data,
    stored_extraction,
)
from herhealth_backend.app.accounts.email_sender import EmailSender
from herhealth_backend.app.accounts.email_verification import (
    request_verification_resend,
    send_verification_code,
    verify_email,
)
from herhealth_backend.app.accounts.errors import CycleImportFailed, InvalidSession
from herhealth_backend.app.accounts.google_identity import GoogleTokenVerifier
from herhealth_backend.app.accounts.google_sign_in import sign_in_with_google
from herhealth_backend.app.accounts.models import User
from herhealth_backend.app.accounts.password_reset import request_password_reset, reset_password
from herhealth_backend.app.accounts.password_reset_policy import CODE_LENGTH as RESET_CODE_LENGTH
from herhealth_backend.app.accounts.profile import (
    clear_health_note,
    health_note_for,
    update_date_of_birth,
    update_display_name,
    update_health_note,
)
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.accounts.sessions import (
    end_all_sessions,
    end_session,
    get_active_session,
    refresh_session,
    start_session,
)
from herhealth_backend.app.accounts.sign_in import sign_in as sign_in_user
from herhealth_backend.app.accounts.verification_code_policy import CODE_LENGTH
from herhealth_backend.app.db import Database
from herhealth_backend.triage.age_bands import age_band_for
from herhealth_backend.triage.cycle_data import prefill, summarize

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
    display_name: str | None = None
    #: Null for accounts created before migration 0009, which is what the
    #: frontend keys the "we still need this" prompt off. New sign-ups always
    #: have one — see ADR 0015 on why the column is nullable regardless.
    date_of_birth: date | None = None
    #: Derived from date_of_birth at response time, never stored: a stored
    #: band would be wrong the morning after a birthday, and 45 is the
    #: boundary features.yaml says separates perimenopause from PCOS.
    age_band: str | None = None
    #: Whether she has written a health note, not the note itself. The
    #: content is only sent by GET /accounts/health-note, so it does not ride
    #: along on every /me poll the app makes.
    has_health_note: bool = False

    #: Whether the two mandatory profile fields — display name and date of
    #: birth — are both set.
    #:
    #: Computed here rather than in the client so one definition of
    #: "complete" governs every caller. The frontend gates on it: an account
    #: without both is sent to the profile step and cannot reach the chat,
    #: which is what makes the fields mandatory rather than merely requested.
    #: Accounts created before they existed therefore complete their profile
    #: on next sign-in.
    #:
    #: The health note is deliberately NOT part of this. It is optional by
    #: design, and blocking on free-text clinical background would pressure
    #: people into writing something to get past a wall.
    profile_complete: bool = False


class UpdateProfileRequest(BaseModel):
    """Every field is optional, and *omitting* one leaves it untouched.

    ``display_name`` used to be the exception: an absent key meant "clear
    it". That made any request setting only a date of birth erase the name
    as a side effect — harmless while nothing collected a name, and a
    data-loss bug the moment the profile step started to. Now every field
    is governed by ``model_fields_set``.

    Clearing still works and is unchanged for callers that meant it:
    ``display_name`` sent *explicitly* as ``null`` clears the name, which is
    what the settings form has always sent.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    date_of_birth: date | None = None
    health_note: str | None = None


class HealthNoteResponse(BaseModel):
    content: str | None = None


class UpdateHealthNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Null or blank clears it — see profile.normalize_health_note.
    content: str | None = None


def _user_summary(user: User, *, has_health_note: bool = False) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified,
        display_name=user.display_name,
        date_of_birth=user.date_of_birth,
        age_band=(
            age_band_for(user.date_of_birth, today=date.today())
            if user.date_of_birth is not None
            else None
        ),
        has_health_note=has_health_note,
        profile_complete=user.display_name is not None and user.date_of_birth is not None,
    )


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

    return _user_summary(user)


@router.post("/sign-in", response_model=UserSummary)
async def sign_in(payload: SignInRequest, request: Request, response: Response) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        user, access_token, refresh_token = await sign_in_user(
            session, secret, email=payload.email, password=payload.password
        )

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return _user_summary(user)


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
    return _user_summary(user)


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
async def me(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserSummary:
    database: Database = request.app.state.database
    async with database.session() as session:
        note = await health_note_for(session, current_user.id)
    return _user_summary(current_user, has_health_note=note is not None)


@router.patch("/me", response_model=UserSummary)
async def update_me(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserSummary:
    """Update whichever profile fields the request actually names.

    Every field is touched only when the request actually names it, so the
    profile step can set a name and a date together, the settings form can
    edit one without disturbing the other, and neither can silently wipe a
    field it never mentioned. See ``UpdateProfileRequest``.
    """
    database: Database = request.app.state.database
    named = payload.model_fields_set
    async with database.session() as session:
        updated = current_user
        if "display_name" in named:
            updated = await update_display_name(
                session, current_user.id, display_name=payload.display_name
            )
        if "date_of_birth" in named and payload.date_of_birth is not None:
            updated = await update_date_of_birth(
                session,
                current_user.id,
                date_of_birth=payload.date_of_birth,
                today=date.today(),
            )
        if "health_note" in named:
            await update_health_note(session, current_user.id, content=payload.health_note)
        note = await health_note_for(session, current_user.id)
    return _user_summary(updated, has_health_note=note is not None)


@router.get("/health-note", response_model=HealthNoteResponse)
async def get_health_note(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> HealthNoteResponse:
    """Her note's text. A separate route from ``/me`` so unverified clinical
    free text is fetched only when something is actually going to show it."""
    database: Database = request.app.state.database
    async with database.session() as session:
        note = await health_note_for(session, current_user.id)
    return HealthNoteResponse(content=note.content if note is not None else None)


@router.put("/health-note", response_model=HealthNoteResponse)
async def put_health_note(
    payload: UpdateHealthNoteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> HealthNoteResponse:
    database: Database = request.app.state.database
    async with database.session() as session:
        stored = await update_health_note(session, current_user.id, content=payload.content)
    return HealthNoteResponse(content=stored)


@router.delete("/health-note", status_code=status.HTTP_204_NO_CONTENT)
async def delete_health_note(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete the note on its own, without closing her account — the property
    ``services/backend/CONTEXT.md`` asks of anything clinical kept for her."""
    database: Database = request.app.state.database
    async with database.session() as session:
        await clear_health_note(session, current_user.id)


class CycleDataSummary(BaseModel):
    """What her data adds up to, for the preview and for Settings."""

    source_app: str
    last_entry: date
    days_since_last_entry: int
    #: False once the last entry is older than the freshness window: nothing
    #: is pre-filled until she uploads a newer export.
    fresh: bool
    periods_found: int
    cycle_lengths: list[int]
    period_durations: list[int]
    #: The feature values this data will answer, so the preview can show her.
    will_answer: dict[str, str]


class CycleDataPreview(BaseModel):
    extraction: CycleExtraction
    summary: CycleDataSummary
    #: No pain was logged at all, so the preview asks whether that is because
    #: she does not get period pain. Only her "yes" can answer a feature.
    ask_about_period_pain: bool


class SaveCycleDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: CycleExtraction
    confirmed_no_period_pain: bool = False


class CycleDataStatus(BaseModel):
    imported_at: datetime | None = None
    summary: CycleDataSummary | None = None


def _cycle_summary(
    request: Request, extraction: CycleExtraction, *, confirmed_no_period_pain: bool
) -> CycleDataSummary:
    summary = summarize(
        extraction, today=date.today(), confirmed_no_period_pain=confirmed_no_period_pain
    )
    agent = getattr(request.app.state, "triage_agent", None)
    return CycleDataSummary(
        source_app=summary.source_app,
        last_entry=summary.last_entry,
        days_since_last_entry=summary.days_since_last_entry,
        fresh=summary.fresh,
        periods_found=len(summary.periods),
        cycle_lengths=list(summary.cycle_lengths),
        period_durations=list(summary.period_durations),
        will_answer=prefill(summary, agent.base) if agent is not None else {},
    )


@router.post("/cycle-data/preview", response_model=CycleDataPreview)
async def preview_cycle_data(
    file: UploadFile,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> CycleDataPreview:
    """Read an uploaded export and show what was found. Stores nothing.

    The file is read here and dropped; FastAPI removes its spooled copy when
    the request ends. She confirms with PUT /accounts/cycle-data, sending the
    extraction back, and only then is anything kept (ADR 0019).
    """
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise CycleImportFailed("too_large")
    extractor: ModelCycleExtractor | None = getattr(request.app.state, "cycle_extractor", None)
    extraction = await to_thread.run_sync(
        lambda: extract_cycle_data(file.file, extractor=extractor)
    )
    summary = _cycle_summary(request, extraction, confirmed_no_period_pain=False)
    pain_logged = any(
        day.pain_intensity is not None or {"cramps", "pelvic_pain"} & set(day.symptoms)
        for day in extraction.days
    )
    return CycleDataPreview(
        extraction=extraction,
        summary=summary,
        ask_about_period_pain=not pain_logged and summary.fresh,
    )


@router.put("/cycle-data", response_model=CycleDataStatus)
async def put_cycle_data(
    payload: SaveCycleDataRequest,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> CycleDataStatus:
    """Keep what she confirmed, replacing any earlier import. The extraction
    is validated again on the way in, so the server stores only what the
    schema can express, not whatever a client sends."""
    database: Database = request.app.state.database
    async with database.session() as session:
        row = await save_cycle_data(
            session,
            current_user.id,
            extraction=payload.extraction,
            confirmed_no_period_pain=payload.confirmed_no_period_pain,
        )
    return CycleDataStatus(
        imported_at=row.imported_at,
        summary=_cycle_summary(
            request,
            payload.extraction,
            confirmed_no_period_pain=payload.confirmed_no_period_pain,
        ),
    )


@router.get("/cycle-data", response_model=CycleDataStatus)
async def get_cycle_data(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> CycleDataStatus:
    database: Database = request.app.state.database
    async with database.session() as session:
        row = await cycle_data_for(session, current_user.id)
    extraction = stored_extraction(row) if row is not None else None
    if row is None or extraction is None:
        return CycleDataStatus()
    return CycleDataStatus(
        imported_at=row.imported_at,
        summary=_cycle_summary(
            request, extraction, confirmed_no_period_pain=row.confirmed_no_period_pain
        ),
    )


@router.delete("/cycle-data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cycle_data(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Delete it on its own, without closing her account — the **Cycle data**
    term in ``services/backend/CONTEXT.md``."""
    database: Database = request.app.state.database
    async with database.session() as session:
        await clear_cycle_data(session, current_user.id)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> None:
    """Permanently delete the signed-in user and all of her data.

    Every auth session ends when the user row is removed; clear this browser's
    cookies so access stops on the next request rather than when the short-
    lived access token happens to expire.
    """
    database: Database = request.app.state.database
    async with database.session() as session:
        await delete_user_account(session, current_user.id)
        await session.commit()
    clear_auth_cookies(response)


@router.post("/verify-email", response_model=UserSummary)
async def verify_email_route(
    payload: VerifyEmailRequest, request: Request, response: Response
) -> UserSummary:
    database: Database = request.app.state.database
    secret: str = request.app.state.session_secret
    async with database.session() as session:
        user = await verify_email(session, secret, email=payload.email, code=payload.code)

    # Proof of control over the inbox is enough to start a session — she
    # should not have to re-enter the password she chose minutes ago.
    async with database.session() as session:
        access_token, refresh_token = await start_session(session, secret, user)
        await session.commit()

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return _user_summary(user)


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
