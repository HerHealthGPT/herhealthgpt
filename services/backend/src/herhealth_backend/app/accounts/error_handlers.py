"""Central mapping from Accounts domain exceptions to HTTP responses.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from herhealth_backend.app.accounts.errors import (
    EmailAlreadyRegistered,
    GoogleEmailNotVerified,
    GoogleSignInNotConfigured,
    GoogleTokenInvalid,
    IncorrectPasswordResetCode,
    IncorrectVerificationCode,
    InvalidAccessToken,
    InvalidCredentials,
    InvalidDisplayName,
    InvalidSession,
    NoPasswordCredential,
    PasswordResetCodeExpired,
    TooManyPasswordResetRequests,
    TooManySignInAttempts,
    TooManyVerificationRequests,
    VerificationCodeExpired,
)
from herhealth_backend.app.accounts.password_policy import PasswordTooWeak

__all__ = ["register_error_handlers"]

logger = logging.getLogger(__name__)

_USER_FACING_UNAVAILABLE = "Service temporarily unavailable. Try again shortly."
_USER_FACING_ERROR = "Something went wrong. Please try again."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    async def _database_unavailable(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        logger.exception("database error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": _USER_FACING_UNAVAILABLE},
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (HTTPException, RequestValidationError)):
            raise exc
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": _USER_FACING_ERROR},
        )

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

    @app.exception_handler(IncorrectVerificationCode)
    async def _incorrect_verification_code(
        request: Request, exc: IncorrectVerificationCode
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "That code is incorrect."},
        )

    @app.exception_handler(VerificationCodeExpired)
    async def _verification_code_expired(
        request: Request, exc: VerificationCodeExpired
    ) -> JSONResponse:
        # The one place #10 asks for a message that reads differently from a
        # wrong-code response — see VerificationCodeExpired's own docstring
        # for why the four cases it covers all read the same as each other.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "This code has expired. Request a new one."},
        )

    @app.exception_handler(TooManyVerificationRequests)
    async def _too_many_verification_requests(
        request: Request, exc: TooManyVerificationRequests
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many attempts. Try again later."},
        )

    @app.exception_handler(GoogleTokenInvalid)
    async def _google_token_invalid(request: Request, exc: GoogleTokenInvalid) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Your Google sign-in could not be verified."},
        )

    @app.exception_handler(GoogleEmailNotVerified)
    async def _google_email_not_verified(
        request: Request, exc: GoogleEmailNotVerified
    ) -> JSONResponse:
        # Deliberately says nothing about *how* to sign into this address —
        # an account this exception fires for is not necessarily a password
        # one (google_sign_in.py's own new-user branch can create a
        # Google-only, still-unverified account), so "use your password"
        # would sometimes be advice with no way to follow it.
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    "This address is already registered, and Google did not confirm you control it."
                )
            },
        )

    @app.exception_handler(GoogleSignInNotConfigured)
    async def _google_sign_in_not_configured(
        request: Request, exc: GoogleSignInNotConfigured
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Signing in with Google is not available yet."},
        )

    @app.exception_handler(NoPasswordCredential)
    async def _no_password_credential(request: Request, exc: NoPasswordCredential) -> JSONResponse:
        # #12's own framing: say so plainly rather than leave her looping
        # between a reset screen and a sign-in screen that each point at the
        # other. See NoPasswordCredential's own docstring for why this is
        # the one deliberate exception to "look the same as an unknown address".
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "This account signs in with Google. There is no password to reset."},
        )

    @app.exception_handler(IncorrectPasswordResetCode)
    async def _incorrect_password_reset_code(
        request: Request, exc: IncorrectPasswordResetCode
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "That code is incorrect."},
        )

    @app.exception_handler(PasswordResetCodeExpired)
    async def _password_reset_code_expired(
        request: Request, exc: PasswordResetCodeExpired
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "This code has expired. Request a new one."},
        )

    @app.exception_handler(TooManyPasswordResetRequests)
    async def _too_many_password_reset_requests(
        request: Request, exc: TooManyPasswordResetRequests
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many attempts. Try again later."},
        )

    @app.exception_handler(InvalidDisplayName)
    async def _invalid_display_name(
        request: Request, exc: InvalidDisplayName
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Name must be between 1 and 80 characters."},
        )
