"""Setting and clearing the two auth cookies on a response.

Both are ``httponly``, so a script running in the page can never read them
(#9's third acceptance criterion), and ``secure``, so neither is ever sent
over plain HTTP. ``samesite="lax"`` rather than ``"strict"``: strict would
drop the cookie on the first request after following a link into the app
from outside it — an email link, a bookmark — which is a real path this
service should not break.

The refresh token cookie is scoped to ``/accounts``: only the sign-in,
refresh, sign-out and sign-out-everywhere routes ever need to see it, and
narrowing its path keeps it out of every other request the browser makes.
The access token cookie needs the full ``/`` path — any route across the
service may sit behind :func:`~herhealth_backend.app.accounts.current_user.get_current_user`.
"""

from __future__ import annotations

from fastapi import Response

from herhealth_backend.app.accounts.session_policy import ACCESS_TOKEN_TTL, REFRESH_TOKEN_TTL
from herhealth_backend.app.config import cookie_secure

__all__ = ["ACCESS_TOKEN_COOKIE", "REFRESH_TOKEN_COOKIE", "set_auth_cookies", "clear_auth_cookies"]

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

_REFRESH_TOKEN_COOKIE_PATH = "/accounts"


def set_auth_cookies(
    response: Response, *, access_token: str, refresh_token: str | None = None
) -> None:
    """Set the access-token cookie, and the refresh-token cookie if given.

    ``refresh_token`` is omitted on a plain refresh — that endpoint reuses the
    existing refresh token rather than rotating it, so there is nothing new
    to set.
    """
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    if refresh_token is not None:
        response.set_cookie(
            REFRESH_TOKEN_COOKIE,
            refresh_token,
            max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
            httponly=True,
            secure=cookie_secure(),
            samesite="lax",
            path=_REFRESH_TOKEN_COOKIE_PATH,
        )


def clear_auth_cookies(response: Response) -> None:
    """Remove both auth cookies, on sign-out and sign-out-everywhere."""
    secure = cookie_secure()
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", secure=secure)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=_REFRESH_TOKEN_COOKIE_PATH, secure=secure)
