"""Central mapping from Accounts domain exceptions to HTTP responses.

Registered once against the app (see ``app/main.py``), rather than
reimplemented as a try/except in every route. The alternative already needed
five separate except clauses across two routes for #8 and #9 combined, and
every new Accounts use case (email verification, password reset, Google
linking) would otherwise need its own route author to remember to add one
more — a mistake that surfaces as a bare 500 instead of the intended 4xx, and
is easy to miss in review since nothing forces the two to change together.
Registering the exception here instead means a route (or a dependency, like
``current_user.get_current_user``) only has to raise the domain exception and
stop — no status code or wording chosen at the call site.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from herhealth_backend.app.accounts.errors import (
    EmailAlreadyRegistered,
    InvalidAccessToken,
    InvalidCredentials,
    InvalidSession,
    TooManySignInAttempts,
)
from herhealth_backend.app.accounts.password_policy import PasswordTooWeak

__all__ = ["register_error_handlers"]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PasswordTooWeak)
    async def _password_too_weak(request: Request, exc: PasswordTooWeak) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": {"reasons": list(exc.reasons)}},
        )

    @app.exception_handler(EmailAlreadyRegistered)
    async def _email_already_registered(
        request: Request, exc: EmailAlreadyRegistered
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "This email address is already registered."},
        )

    @app.exception_handler(InvalidCredentials)
    async def _invalid_credentials(request: Request, exc: InvalidCredentials) -> JSONResponse:
        # Deliberately identical whether the address is unknown or the
        # password is wrong — see sign_in.py.
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Incorrect email address or password."},
        )

    @app.exception_handler(TooManySignInAttempts)
    async def _too_many_sign_in_attempts(
        request: Request, exc: TooManySignInAttempts
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many attempts. Try again later."},
        )

    @app.exception_handler(InvalidSession)
    async def _invalid_session(request: Request, exc: InvalidSession) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Not signed in."},
        )

    @app.exception_handler(InvalidAccessToken)
    async def _invalid_access_token(request: Request, exc: InvalidAccessToken) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Not signed in."},
        )
