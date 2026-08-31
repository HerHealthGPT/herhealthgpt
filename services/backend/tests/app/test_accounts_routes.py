"""``POST /accounts/register`` driven over HTTP, the acceptance criteria made executable."""

from __future__ import annotations

from httpx import AsyncClient, Response

from herhealth_backend.app.accounts.sign_in_throttle import MAX_FAILURES


async def test_register_returns_the_created_user(client: AsyncClient) -> None:
    response = await client.post(
        "/accounts/register",
        json={"email": "route-success@example.com", "password": "correcthorse1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "route-success@example.com"
    assert body["email_verified"] is False
    assert "id" in body


async def test_register_response_never_contains_the_password(client: AsyncClient) -> None:
    response = await client.post(
        "/accounts/register",
        json={"email": "route-no-password@example.com", "password": "correcthorse1"},
    )

    assert "correcthorse1" not in response.text
    assert "password" not in response.json()


async def test_register_duplicate_address_is_refused(client: AsyncClient) -> None:
    payload = {"email": "route-duplicate@example.com", "password": "correcthorse1"}
    first = await client.post("/accounts/register", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/accounts/register",
        json={"email": "ROUTE-DUPLICATE@EXAMPLE.COM", "password": "anotherpassword1"},
    )
    assert second.status_code == 409
    # No hint of the existing user's verification state or anything else about her.
    assert "verified" not in second.text.lower()


async def test_register_weak_password_is_refused_with_a_reason(client: AsyncClient) -> None:
    response = await client.post(
        "/accounts/register",
        json={"email": "route-weak-password@example.com", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reasons"]


async def test_register_rejects_a_malformed_email(client: AsyncClient) -> None:
    response = await client.post(
        "/accounts/register",
        json={"email": "not-an-email", "password": "correcthorse1"},
    )

    assert response.status_code == 422


async def test_register_oversized_password_is_rejected_without_echoing_it(
    client: AsyncClient,
) -> None:
    """A too-long password is refused by check_password_strength, the same as a
    too-short one — never by a schema-level Field constraint, which would have
    FastAPI echo the raw value into the 422 body. Guards against that leak
    coming back if a length cap is ever added to RegisterRequest directly.
    """
    oversized_password = "a1" * 200  # comfortably past MAX_LENGTH (256)
    response = await client.post(
        "/accounts/register",
        json={"email": "route-oversized-password@example.com", "password": oversized_password},
    )

    assert response.status_code == 422
    assert oversized_password not in response.text


async def _register(client: AsyncClient, email: str, password: str = "correcthorse1") -> None:
    response = await client.post("/accounts/register", json={"email": email, "password": password})
    assert response.status_code == 201


def _cookie_attributes(response: Response, cookie_name: str) -> str:
    """The raw ``Set-Cookie`` header text for ``cookie_name``, lower-cased.

    httpx's parsed ``response.cookies`` drops attributes like HttpOnly and
    Secure, so the flags #9 cares about have to be read off the raw header.
    """
    for header_value in response.headers.get_list("set-cookie"):
        if header_value.split("=", 1)[0] == cookie_name:
            return header_value.lower()
    raise AssertionError(f"No Set-Cookie header for {cookie_name!r}")


async def test_sign_in_with_correct_credentials_returns_the_user_and_sets_cookies(
    client: AsyncClient,
) -> None:
    await _register(client, "sign-in-success@example.com")

    response = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-in-success@example.com", "password": "correcthorse1"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "sign-in-success@example.com"

    access_cookie = _cookie_attributes(response, "access_token")
    refresh_cookie = _cookie_attributes(response, "refresh_token")
    for cookie in (access_cookie, refresh_cookie):
        assert "httponly" in cookie
        assert "secure" in cookie


async def test_a_subsequent_request_identifies_the_signed_in_user(client: AsyncClient) -> None:
    await _register(client, "sign-in-then-me@example.com")
    await client.post(
        "/accounts/sign-in",
        json={"email": "sign-in-then-me@example.com", "password": "correcthorse1"},
    )

    response = await client.get("/accounts/me")

    assert response.status_code == 200
    assert response.json()["email"] == "sign-in-then-me@example.com"


async def test_me_without_a_session_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/accounts/me")

    assert response.status_code == 401


async def test_sign_in_with_an_unknown_address_and_a_wrong_password_look_the_same(
    client: AsyncClient,
) -> None:
    await _register(client, "sign-in-known@example.com")

    wrong_password = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-in-known@example.com", "password": "wrongpassword1"},
    )
    unknown_address = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-in-unknown@example.com", "password": "wrongpassword1"},
    )

    assert wrong_password.status_code == unknown_address.status_code == 401
    assert wrong_password.json() == unknown_address.json()


async def test_repeated_failed_sign_ins_are_blocked(client: AsyncClient) -> None:
    await _register(client, "sign-in-lockout@example.com")

    for _ in range(MAX_FAILURES):
        response = await client.post(
            "/accounts/sign-in",
            json={"email": "sign-in-lockout@example.com", "password": "wrongpassword1"},
        )
        assert response.status_code == 401

    locked_out = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-in-lockout@example.com", "password": "correcthorse1"},
    )
    assert locked_out.status_code == 429


async def test_refresh_exchanges_a_valid_refresh_token_for_a_new_access_token(
    client: AsyncClient,
) -> None:
    await _register(client, "refresh-success@example.com")
    await client.post(
        "/accounts/sign-in",
        json={"email": "refresh-success@example.com", "password": "correcthorse1"},
    )

    response = await client.post("/accounts/refresh")

    assert response.status_code == 204
    assert "access_token" in response.cookies
    # The refreshed access token still identifies the same user.
    me = await client.get("/accounts/me")
    assert me.json()["email"] == "refresh-success@example.com"


async def test_refresh_without_a_session_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/accounts/refresh")

    assert response.status_code == 401


async def test_sign_out_ends_the_session_so_it_cannot_be_refreshed_again(
    client: AsyncClient,
) -> None:
    await _register(client, "sign-out-success@example.com")
    await client.post(
        "/accounts/sign-in",
        json={"email": "sign-out-success@example.com", "password": "correcthorse1"},
    )

    sign_out_response = await client.post("/accounts/sign-out")
    assert sign_out_response.status_code == 204

    refresh_after_sign_out = await client.post("/accounts/refresh")
    assert refresh_after_sign_out.status_code == 401


async def test_sign_out_everywhere_ends_every_session_for_the_user(client: AsyncClient) -> None:
    await _register(client, "sign-out-everywhere@example.com")

    first_sign_in = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-out-everywhere@example.com", "password": "correcthorse1"},
    )
    first_refresh_token = first_sign_in.cookies["refresh_token"]

    second_sign_in = await client.post(
        "/accounts/sign-in",
        json={"email": "sign-out-everywhere@example.com", "password": "correcthorse1"},
    )
    second_refresh_token = second_sign_in.cookies["refresh_token"]

    # The client's cookie jar now holds the second sign-in's session; use it
    # to sign out everywhere while explicitly re-checking the first session.
    sign_out_everywhere = await client.post("/accounts/sign-out-everywhere")
    assert sign_out_everywhere.status_code == 204

    first_session_refresh = await client.post(
        "/accounts/refresh", headers={"Cookie": f"refresh_token={first_refresh_token}"}
    )
    assert first_session_refresh.status_code == 401

    second_session_refresh = await client.post(
        "/accounts/refresh", headers={"Cookie": f"refresh_token={second_refresh_token}"}
    )
    assert second_session_refresh.status_code == 401
