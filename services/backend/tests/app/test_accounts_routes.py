"""``POST /accounts/register`` driven over HTTP, the acceptance criteria made executable."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient, Response

from herhealth_backend.app import Database, create_app
from herhealth_backend.app.accounts.google_identity import (
    GoogleIdentity,
    UnconfiguredGoogleTokenVerifier,
)
from herhealth_backend.app.accounts.password_reset_throttle import (
    MAX_SENDS as MAX_PASSWORD_RESET_SENDS,
)
from herhealth_backend.app.accounts.sign_in_throttle import MAX_FAILURES
from herhealth_backend.app.accounts.verification_send_throttle import MAX_SENDS


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


async def test_register_sends_a_verification_code(client: AsyncClient, email_sender) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "register-sends-code@example.com", "password": "correcthorse1"},
    )

    code = email_sender.code_for("register-sends-code@example.com")
    assert len(code) == 6 and code.isdigit()


async def test_verify_email_with_the_correct_code_marks_it_verified(
    client: AsyncClient, email_sender
) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "verify-success@example.com", "password": "correcthorse1"},
    )
    code = email_sender.code_for("verify-success@example.com")

    response = await client.post(
        "/accounts/verify-email", json={"email": "verify-success@example.com", "code": code}
    )

    assert response.status_code == 200
    assert response.json()["email_verified"] is True


async def test_verify_email_with_the_wrong_code_is_refused(
    client: AsyncClient, email_sender
) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "verify-wrong-code@example.com", "password": "correcthorse1"},
    )
    code = email_sender.code_for("verify-wrong-code@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    response = await client.post(
        "/accounts/verify-email",
        json={"email": "verify-wrong-code@example.com", "code": wrong_code},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "That code is incorrect."


async def test_verify_email_a_used_code_reads_as_expired_not_incorrect(
    client: AsyncClient, email_sender
) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "verify-replay@example.com", "password": "correcthorse1"},
    )
    code = email_sender.code_for("verify-replay@example.com")
    await client.post(
        "/accounts/verify-email", json={"email": "verify-replay@example.com", "code": code}
    )

    replayed = await client.post(
        "/accounts/verify-email", json={"email": "verify-replay@example.com", "code": code}
    )

    assert replayed.status_code == 400
    assert replayed.json()["detail"] == "This code has expired. Request a new one."


async def test_resend_verification_code_sends_a_new_code(
    client: AsyncClient, email_sender
) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "resend-success@example.com", "password": "correcthorse1"},
    )
    old_code = email_sender.code_for("resend-success@example.com")

    response = await client.post(
        "/accounts/verify-email/resend", json={"email": "resend-success@example.com"}
    )

    assert response.status_code == 204
    new_code = email_sender.code_for("resend-success@example.com")
    verify_with_old_code = await client.post(
        "/accounts/verify-email", json={"email": "resend-success@example.com", "code": old_code}
    )
    assert verify_with_old_code.status_code == 400
    verify_with_new_code = await client.post(
        "/accounts/verify-email", json={"email": "resend-success@example.com", "code": new_code}
    )
    assert verify_with_new_code.status_code == 200


async def test_resend_verification_code_for_an_unknown_address_looks_like_success(
    client: AsyncClient, email_sender
) -> None:
    """#10's ninth criterion: resend must not be usable to confirm an
    address is registered — an unknown address gets the same response as a
    real one, and nothing is actually sent.
    """
    response = await client.post(
        "/accounts/verify-email/resend", json={"email": "resend-unknown@example.com"}
    )

    assert response.status_code == 204
    assert email_sender.sent == []


async def test_repeated_resend_requests_are_rate_limited(
    client: AsyncClient, email_sender
) -> None:
    await client.post(
        "/accounts/register",
        json={"email": "resend-lockout@example.com", "password": "correcthorse1"},
    )

    # Registration itself already sent one code; use up the rest of the budget.
    for _ in range(MAX_SENDS - 1):
        response = await client.post(
            "/accounts/verify-email/resend", json={"email": "resend-lockout@example.com"}
        )
        assert response.status_code == 204

    locked_out = await client.post(
        "/accounts/verify-email/resend", json={"email": "resend-lockout@example.com"}
    )
    assert locked_out.status_code == 429


async def test_sign_in_google_on_an_unknown_address_creates_a_user(
    client: AsyncClient, google_verifier
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="route-google-sub-1", email="route-new-google@example.com", email_verified=True
    )

    response = await client.post("/accounts/sign-in/google", json={"id_token": "whatever"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "route-new-google@example.com"
    assert body["email_verified"] is True
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    me = await client.get("/accounts/me")
    assert me.json()["email"] == "route-new-google@example.com"


async def test_sign_in_google_with_an_invalid_token_is_unauthorized(client: AsyncClient) -> None:
    # The client fixture's google_verifier starts with no identity configured,
    # so any token is treated as invalid.
    response = await client.post("/accounts/sign-in/google", json={"id_token": "garbage"})

    assert response.status_code == 401


async def test_sign_in_google_without_email_verified_is_refused(
    client: AsyncClient, google_verifier
) -> None:
    """An address that already has an account (verified or not — this one
    is left unverified by registering and stopping there) must not be
    touched when Google does not assert it controls the address.
    """
    await client.post(
        "/accounts/register",
        json={"email": "route-careful@example.com", "password": "correcthorse1"},
    )

    google_verifier.identity = GoogleIdentity(
        sub="route-google-sub-2", email="route-careful@example.com", email_verified=False
    )

    response = await client.post("/accounts/sign-in/google", json={"id_token": "whatever"})

    assert response.status_code == 409


async def _register_and_verify(client: AsyncClient, email_sender, email: str) -> None:
    await _register(client, email)
    code = email_sender.code_for(email)
    response = await client.post("/accounts/verify-email", json={"email": email, "code": code})
    assert response.status_code == 200


async def test_reset_password_request_sends_a_code_for_a_verified_address(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-request-success@example.com")

    response = await client.post(
        "/accounts/reset-password/request", json={"email": "reset-request-success@example.com"}
    )

    assert response.status_code == 204
    code = email_sender.password_reset_code_for("reset-request-success@example.com")
    assert len(code) == 6 and code.isdigit()


async def test_reset_password_request_for_an_unknown_address_looks_like_success(
    client: AsyncClient, email_sender
) -> None:
    response = await client.post(
        "/accounts/reset-password/request", json={"email": "reset-request-unknown@example.com"}
    )

    assert response.status_code == 204
    assert email_sender.password_reset_sent == []


async def test_reset_password_request_for_an_unverified_address_looks_like_success(
    client: AsyncClient, email_sender
) -> None:
    await _register(client, "reset-request-unverified@example.com")

    response = await client.post(
        "/accounts/reset-password/request", json={"email": "reset-request-unverified@example.com"}
    )

    assert response.status_code == 204
    assert email_sender.password_reset_sent == []


async def test_reset_password_request_for_a_google_only_account_says_so(
    client: AsyncClient, google_verifier
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="route-google-sub-reset", email="reset-request-google@example.com", email_verified=True
    )
    await client.post("/accounts/sign-in/google", json={"id_token": "whatever"})

    response = await client.post(
        "/accounts/reset-password/request", json={"email": "reset-request-google@example.com"}
    )

    assert response.status_code == 409
    assert "Google" in response.json()["detail"]


async def test_reset_password_request_for_an_unverified_google_only_account_looks_like_success(
    client: AsyncClient, google_verifier
) -> None:
    google_verifier.identity = GoogleIdentity(
        sub="route-google-sub-reset-unverified",
        email="reset-request-google-unverified@example.com",
        email_verified=False,
    )
    await client.post("/accounts/sign-in/google", json={"id_token": "whatever"})

    response = await client.post(
        "/accounts/reset-password/request",
        json={"email": "reset-request-google-unverified@example.com"},
    )

    assert response.status_code == 204


async def test_reset_password_requests_are_rate_limited(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-request-lockout@example.com")

    for _ in range(MAX_PASSWORD_RESET_SENDS):
        response = await client.post(
            "/accounts/reset-password/request", json={"email": "reset-request-lockout@example.com"}
        )
        assert response.status_code == 204

    locked_out = await client.post(
        "/accounts/reset-password/request", json={"email": "reset-request-lockout@example.com"}
    )
    assert locked_out.status_code == 429


async def test_reset_password_with_the_correct_code_replaces_the_password(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-complete-success@example.com")
    await client.post(
        "/accounts/reset-password/request", json={"email": "reset-complete-success@example.com"}
    )
    code = email_sender.password_reset_code_for("reset-complete-success@example.com")

    response = await client.post(
        "/accounts/reset-password",
        json={
            "email": "reset-complete-success@example.com",
            "code": code,
            "new_password": "brandnewpassword1",
        },
    )
    assert response.status_code == 204

    old_password_sign_in = await client.post(
        "/accounts/sign-in",
        json={"email": "reset-complete-success@example.com", "password": "correcthorse1"},
    )
    assert old_password_sign_in.status_code == 401

    new_password_sign_in = await client.post(
        "/accounts/sign-in",
        json={"email": "reset-complete-success@example.com", "password": "brandnewpassword1"},
    )
    assert new_password_sign_in.status_code == 200


async def test_reset_password_ends_every_existing_session(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-ends-sessions@example.com")
    sign_in_response = await client.post(
        "/accounts/sign-in",
        json={"email": "reset-ends-sessions@example.com", "password": "correcthorse1"},
    )
    refresh_token = sign_in_response.cookies["refresh_token"]

    await client.post(
        "/accounts/reset-password/request", json={"email": "reset-ends-sessions@example.com"}
    )
    code = email_sender.password_reset_code_for("reset-ends-sessions@example.com")
    await client.post(
        "/accounts/reset-password",
        json={
            "email": "reset-ends-sessions@example.com",
            "code": code,
            "new_password": "brandnewpassword1",
        },
    )

    refresh_after_reset = await client.post(
        "/accounts/refresh", headers={"Cookie": f"refresh_token={refresh_token}"}
    )
    assert refresh_after_reset.status_code == 401


async def test_reset_password_with_the_wrong_code_is_refused(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-wrong-code@example.com")
    await client.post(
        "/accounts/reset-password/request", json={"email": "reset-wrong-code@example.com"}
    )
    code = email_sender.password_reset_code_for("reset-wrong-code@example.com")
    wrong_code = "0" * 6 if code != "0" * 6 else "1" * 6

    response = await client.post(
        "/accounts/reset-password",
        json={
            "email": "reset-wrong-code@example.com",
            "code": wrong_code,
            "new_password": "brandnewpassword1",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "That code is incorrect."


async def test_reset_password_a_used_code_reads_as_expired_not_incorrect(
    client: AsyncClient, email_sender
) -> None:
    await _register_and_verify(client, email_sender, "reset-replay@example.com")
    await client.post(
        "/accounts/reset-password/request", json={"email": "reset-replay@example.com"}
    )
    code = email_sender.password_reset_code_for("reset-replay@example.com")
    await client.post(
        "/accounts/reset-password",
        json={
            "email": "reset-replay@example.com",
            "code": code,
            "new_password": "brandnewpassword1",
        },
    )

    replayed = await client.post(
        "/accounts/reset-password",
        json={
            "email": "reset-replay@example.com",
            "code": code,
            "new_password": "anotherbrandnewpassword1",
        },
    )

    assert replayed.status_code == 400
    assert replayed.json()["detail"] == "This code has expired. Request a new one."


async def test_google_sign_in_not_configured_is_service_unavailable(database_url: str) -> None:
    """A deployment with no ``HERHEALTH_GOOGLE_CLIENT_ID`` set gets an
    ``UnconfiguredGoogleTokenVerifier`` (see ``main.py``'s ``_build_google_verifier``)
    rather than the app failing to boot over an optional feature — exercised
    directly here since httpx's ``ASGITransport`` never runs the app's own
    lifespan, the same reason the ``client`` fixture always passes every
    piece of state in explicitly rather than letting the app construct it.
    """
    database = Database(database_url)
    app = create_app(
        database=database,
        session_secret="test-only-session-secret-do-not-use",
        google_verifier=UnconfiguredGoogleTokenVerifier(),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as unconfigured_client:
        response = await unconfigured_client.post(
            "/accounts/sign-in/google", json={"id_token": "whatever"}
        )
    await database.dispose()

    assert response.status_code == 503
