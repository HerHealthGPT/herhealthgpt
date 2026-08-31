"""HTTP surface for Accounts. One route today: registration.

Kept a thin translation layer on purpose — ``register_user`` is where the
actual decisions live, so it can be tested without an ASGI client. This module
only turns its result and its exceptions into a response.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from herhealth_backend.app.accounts.errors import EmailAlreadyRegistered
from herhealth_backend.app.accounts.password_policy import MAX_LENGTH, PasswordTooWeak
from herhealth_backend.app.accounts.registration import register_user
from herhealth_backend.app.db import Database

__all__ = ["router"]

router = APIRouter(prefix="/accounts", tags=["accounts"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    #: No min_length here — that floor is enforced by check_password_strength
    #: so a weak password gets the specific reasons #8 asks for, not a generic
    #: FastAPI validation error. max_length exists purely so an oversized body
    #: is rejected before it reaches argon2id, which will hash whatever it is
    #: given; check_password_strength enforces the same ceiling independently.
    password: str = Field(max_length=MAX_LENGTH)


class RegisteredUser(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool


@router.post(
    "/register",
    response_model=RegisteredUser,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, request: Request) -> RegisteredUser:
    database: Database = request.app.state.database
    async with database.session() as session:
        try:
            user = await register_user(session, email=payload.email, password=payload.password)
        except PasswordTooWeak as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"reasons": list(exc.reasons)},
            ) from exc
        except EmailAlreadyRegistered as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email address is already registered.",
            ) from exc

    return RegisteredUser(id=user.id, email=user.email, email_verified=user.email_verified)
