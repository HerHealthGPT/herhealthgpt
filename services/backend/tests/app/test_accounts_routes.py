"""``POST /accounts/register`` driven over HTTP, the acceptance criteria made executable."""

from __future__ import annotations

from httpx import AsyncClient


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
