"""Date of birth and the optional health note — ADR 0015.

Split into pure validation (no database) and the HTTP surface, because the
validation rules are the part that decides what the reasoning model is later
told about her age, and those deserve to be readable without a container.
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from herhealth_backend.app.accounts.errors import InvalidDateOfBirth, InvalidHealthNote
from herhealth_backend.app.accounts.profile import (
    MAX_HEALTH_NOTE_LENGTH,
    MIN_AGE_YEARS,
    normalize_health_note,
    validate_date_of_birth,
)

TODAY = date(2026, 9, 6)


def test_a_plausible_date_of_birth_is_accepted() -> None:
    born = date(1994, 3, 17)
    assert validate_date_of_birth(born, today=TODAY) == born


def test_a_future_date_of_birth_is_refused() -> None:
    with pytest.raises(InvalidDateOfBirth):
        validate_date_of_birth(date(2027, 1, 1), today=TODAY)


def test_the_day_she_turns_thirteen_is_accepted_and_the_day_before_is_not() -> None:
    """The floor is exact rather than approximate — a year-arithmetic bug here
    locks out a user who is old enough, or admits one who is not."""
    thirteenth_birthday = date(TODAY.year - MIN_AGE_YEARS, TODAY.month, TODAY.day)
    assert validate_date_of_birth(thirteenth_birthday, today=TODAY) == thirteenth_birthday

    with pytest.raises(InvalidDateOfBirth):
        validate_date_of_birth(
            date(TODAY.year - MIN_AGE_YEARS, TODAY.month, TODAY.day + 1), today=TODAY
        )


def test_a_mistyped_year_is_refused_rather_than_banded_as_oldest() -> None:
    """1902 for 1992 would otherwise pass silently and land her in 55_plus."""
    with pytest.raises(InvalidDateOfBirth):
        validate_date_of_birth(date(1902, 5, 4), today=TODAY)


def test_a_blank_health_note_clears_rather_than_storing_empty() -> None:
    assert normalize_health_note(None) is None
    assert normalize_health_note("") is None
    assert normalize_health_note("   \n  ") is None


def test_a_health_note_keeps_her_own_line_breaks() -> None:
    """Unlike a display name, this is not reflowed — she may type a list, and
    collapsing it would be us editing what she told us."""
    assert normalize_health_note("  PCOS since 2019\nlow iron  ") == "PCOS since 2019\nlow iron"


def test_an_oversized_health_note_is_refused() -> None:
    with pytest.raises(InvalidHealthNote):
        normalize_health_note("x" * (MAX_HEALTH_NOTE_LENGTH + 1))


async def _register_and_sign_in(client: AsyncClient, email: str) -> None:
    payload = {"email": email, "password": "correcthorse1"}
    registered = await client.post("/accounts/register", json=payload)
    assert registered.status_code == 201, registered.text
    signed_in = await client.post("/accounts/sign-in", json=payload)
    assert signed_in.status_code == 200, signed_in.text


async def test_me_reports_no_date_of_birth_before_one_is_given(client: AsyncClient) -> None:
    """What the frontend keys its "we still need this" prompt off. Accounts
    predating migration 0009 look exactly like this, deliberately."""
    await _register_and_sign_in(client, "profile-empty@example.com")

    response = await client.get("/accounts/me")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date_of_birth"] is None
    assert body["age_band"] is None
    assert body["has_health_note"] is False


async def test_setting_a_date_of_birth_returns_its_derived_band(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "profile-dob@example.com")

    response = await client.patch("/accounts/me", json={"date_of_birth": "1994-03-17"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date_of_birth"] == "1994-03-17"
    # Derived at response time, not stored — see UserSummary.age_band.
    assert body["age_band"] in {"30_to_39", "20_to_29"}


async def test_an_implausible_date_of_birth_is_refused_over_http(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "profile-bad-dob@example.com")

    response = await client.patch("/accounts/me", json={"date_of_birth": "2020-01-01"})

    assert response.status_code == 400, response.text
    assert str(MIN_AGE_YEARS) in response.json()["detail"]


async def test_a_health_note_round_trips_and_is_not_on_me(client: AsyncClient) -> None:
    """``/me`` reports only whether a note exists; the text needs its own
    request, so unverified clinical free text is not on every poll."""
    await _register_and_sign_in(client, "profile-note@example.com")

    written = await client.put("/accounts/health-note", json={"content": "PCOS since 2019"})
    assert written.status_code == 200, written.text
    assert written.json()["content"] == "PCOS since 2019"

    summary = await client.get("/accounts/me")
    assert summary.json()["has_health_note"] is True
    assert "PCOS" not in summary.text

    fetched = await client.get("/accounts/health-note")
    assert fetched.json()["content"] == "PCOS since 2019"


async def test_a_health_note_can_be_deleted_without_closing_the_account(
    client: AsyncClient,
) -> None:
    """The property services/backend/CONTEXT.md asks of anything clinical
    kept for her: deletable independently of the account."""
    await _register_and_sign_in(client, "profile-note-delete@example.com")
    await client.put("/accounts/health-note", json={"content": "low iron"})

    deleted = await client.delete("/accounts/health-note")
    assert deleted.status_code == 204, deleted.text

    assert (await client.get("/accounts/health-note")).json()["content"] is None
    still_signed_in = await client.get("/accounts/me")
    assert still_signed_in.status_code == 200
    assert still_signed_in.json()["has_health_note"] is False


async def test_editing_only_the_note_does_not_wipe_the_date_of_birth(
    client: AsyncClient,
) -> None:
    """Why UpdateProfileRequest consults model_fields_set: display_name has
    always treated an absent key as "clear it", and the fields added in 0009
    must not inherit that."""
    await _register_and_sign_in(client, "profile-partial@example.com")
    await client.patch("/accounts/me", json={"date_of_birth": "1990-06-01"})

    response = await client.patch("/accounts/me", json={"health_note": "endometriosis"})

    assert response.status_code == 200, response.text
    assert response.json()["date_of_birth"] == "1990-06-01"
    assert response.json()["has_health_note"] is True


async def test_deleting_the_account_removes_the_health_note(client: AsyncClient) -> None:
    """The FK cascades. Without it a deleted user would leave clinical free
    text behind, which is exactly what CONTEXT.md's Deletion term forbids."""
    await _register_and_sign_in(client, "profile-cascade@example.com")
    await client.put("/accounts/health-note", json={"content": "fibroids"})

    deleted = await client.delete("/accounts/me")

    assert deleted.status_code == 204, deleted.text
    assert (await client.get("/accounts/me")).status_code == 401
