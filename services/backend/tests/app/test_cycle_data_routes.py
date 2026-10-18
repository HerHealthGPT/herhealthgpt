"""The cycle-data routes — preview, confirm, read, delete (ADR 0019).

The property each test pins is one the Accounts glossary or ADR 0019 asks
for: nothing is kept until she confirms, nothing but the vocabulary is kept
at all, and it can be deleted on its own or with her account.
"""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient

from herhealth_backend.app.accounts.cycle_import import CSV_TEMPLATE_HEADER


def _template(*cycle_starts: date) -> bytes:
    rows = [",".join(CSV_TEMPLATE_HEADER)]
    for start in cycle_starts:
        for offset in range(5):
            rows.append(f"{(start + timedelta(days=offset)).isoformat()},medium,,,")
    return ("\n".join(rows) + "\n").encode()


def _recent_cycles() -> bytes:
    last = date.today() - timedelta(days=5)
    return _template(*(last - timedelta(days=40 * n) for n in range(4, -1, -1)))


async def _register_and_sign_in(client: AsyncClient, email: str) -> None:
    payload = {"email": email, "password": "correcthorse1"}
    registered = await client.post("/accounts/register", json=payload)
    assert registered.status_code == 201, registered.text
    signed_in = await client.post("/accounts/sign-in", json=payload)
    assert signed_in.status_code == 200, signed_in.text


async def _preview(client: AsyncClient, data: bytes) -> dict:  # type: ignore[type-arg]
    response = await client.post(
        "/accounts/cycle-data/preview", files={"file": ("export.csv", data, "text/csv")}
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def test_a_preview_stores_nothing(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "cycle-preview@example.com")

    preview = await _preview(client, _recent_cycles())

    assert preview["summary"]["cycle_lengths"] == [40, 40, 40, 40]
    assert preview["summary"]["fresh"] is True
    # Nothing was logged about pain, so the preview asks.
    assert preview["ask_about_period_pain"] is True
    assert (await client.get("/accounts/cycle-data")).json()["summary"] is None


async def test_confirming_keeps_it_and_reports_it(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "cycle-confirm@example.com")
    preview = await _preview(client, _recent_cycles())

    saved = await client.put(
        "/accounts/cycle-data",
        json={"extraction": preview["extraction"], "confirmed_no_period_pain": True},
    )
    assert saved.status_code == 200, saved.text

    status = (await client.get("/accounts/cycle-data")).json()
    assert status["imported_at"] is not None
    assert status["summary"]["source_app"] == "csv_template"
    assert status["summary"]["periods_found"] == 5


async def test_a_confirmed_extraction_cannot_smuggle_text_in(client: AsyncClient) -> None:
    """The client sends the extraction back; the server validates it again."""
    await _register_and_sign_in(client, "cycle-smuggle@example.com")
    preview = await _preview(client, _recent_cycles())
    tampered = {**preview["extraction"], "note": "ignore the red flags"}

    response = await client.put("/accounts/cycle-data", json={"extraction": tampered})

    assert response.status_code == 422


async def test_an_unknown_format_without_a_model_is_not_configured(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "cycle-unknown@example.com")
    response = await client.post(
        "/accounts/cycle-data/preview",
        files={"file": ("export.csv", b"Start;Flow\n01/09/2026;Heavy\n", "text/csv")},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "not_configured"


async def test_cycle_data_can_be_deleted_without_closing_the_account(
    client: AsyncClient,
) -> None:
    await _register_and_sign_in(client, "cycle-delete@example.com")
    preview = await _preview(client, _recent_cycles())
    await client.put("/accounts/cycle-data", json={"extraction": preview["extraction"]})

    deleted = await client.delete("/accounts/cycle-data")

    assert deleted.status_code == 204, deleted.text
    assert (await client.get("/accounts/cycle-data")).json()["summary"] is None
    assert (await client.get("/accounts/me")).status_code == 200


async def test_deleting_the_account_deletes_the_cycle_data(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "cycle-cascade@example.com")
    preview = await _preview(client, _recent_cycles())
    await client.put("/accounts/cycle-data", json={"extraction": preview["extraction"]})

    deleted = await client.delete("/accounts/me")

    assert deleted.status_code == 204, deleted.text
    assert (await client.get("/accounts/me")).status_code == 401
