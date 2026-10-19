"""The kept-files routes — upload, list, download, delete (ADR 0020).

Each test pins a property ADR 0020 asks for: only her own files are ever
visible to her, only the kinds the import reads are accepted, a file past
its 30 days is neither listed nor served and is then removed from the disk,
and deleting her account removes her files with it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update

from herhealth_backend.app import Database
from herhealth_backend.app.accounts.models import StoredFile
from herhealth_backend.app.accounts.stored_files import FileStore, purge_expired

CSV = b"date,flow,symptoms,pain_intensity,pregnancy_test\n2026-10-01,heavy,cramps,,\n"


async def _register_and_sign_in(client: AsyncClient, email: str) -> None:
    payload = {"email": email, "password": "correcthorse1"}
    registered = await client.post("/accounts/register", json=payload)
    assert registered.status_code == 201, registered.text
    signed_in = await client.post("/accounts/sign-in", json=payload)
    assert signed_in.status_code == 200, signed_in.text


async def _upload(client: AsyncClient, name: str = "cycle.csv", data: bytes = CSV) -> dict:  # type: ignore[type-arg]
    response = await client.post("/accounts/files", files={"file": (name, data, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


async def test_a_kept_file_is_listed_and_downloads_as_it_was(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "files-roundtrip@example.com")

    kept = await _upload(client)

    assert kept["filename"] == "cycle.csv"
    assert kept["size_bytes"] == len(CSV)
    expires = datetime.fromisoformat(kept["expires_at"])
    created = datetime.fromisoformat(kept["created_at"])
    assert expires - created == timedelta(days=30)
    listed = (await client.get("/accounts/files")).json()
    assert [f["id"] for f in listed] == [kept["id"]]
    download = await client.get(f"/accounts/files/{kept['id']}")
    assert download.status_code == 200
    assert download.content == CSV
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["cache-control"] == "no-store"


async def test_a_file_of_another_kind_is_refused(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "files-kind@example.com")

    response = await client.post(
        "/accounts/files", files={"file": ("page.html", b"<html></html>", "text/html")}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_type"
    assert (await client.get("/accounts/files")).json() == []


async def test_she_cannot_see_or_delete_someone_elses_file(client: AsyncClient) -> None:
    await _register_and_sign_in(client, "files-owner@example.com")
    kept = await _upload(client)
    client.cookies.clear()
    await _register_and_sign_in(client, "files-other@example.com")

    assert (await client.get("/accounts/files")).json() == []
    assert (await client.get(f"/accounts/files/{kept['id']}")).status_code == 404
    assert (await client.delete(f"/accounts/files/{kept['id']}")).status_code == 404


async def test_deleting_a_file_removes_it_from_the_disk(
    client: AsyncClient, file_store: FileStore
) -> None:
    await _register_and_sign_in(client, "files-delete@example.com")
    kept = await _upload(client)
    on_disk = list(file_store.root.rglob(kept["id"]))
    assert len(on_disk) == 1

    assert (await client.delete(f"/accounts/files/{kept['id']}")).status_code == 204

    assert not on_disk[0].exists()
    assert (await client.get("/accounts/files")).json() == []


async def test_a_file_past_its_date_is_hidden_then_removed(
    client: AsyncClient, file_store: FileStore, database_url: str
) -> None:
    await _register_and_sign_in(client, "files-expiry@example.com")
    kept = await _upload(client)
    database = Database(database_url)
    try:
        async with database.session() as session:
            await session.execute(
                update(StoredFile)
                .where(StoredFile.filename == "cycle.csv", StoredFile.id == kept["id"])
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()

        assert (await client.get("/accounts/files")).json() == []
        assert (await client.get(f"/accounts/files/{kept['id']}")).status_code == 404

        async with database.session() as session:
            assert await purge_expired(session, file_store) >= 1
    finally:
        await database.dispose()
    assert list(file_store.root.rglob(kept["id"])) == []


async def test_deleting_her_account_removes_her_files(
    client: AsyncClient, file_store: FileStore
) -> None:
    await _register_and_sign_in(client, "files-account@example.com")
    kept = await _upload(client)
    assert list(file_store.root.rglob(kept["id"]))

    assert (await client.delete("/accounts/me")).status_code == 204

    assert list(file_store.root.rglob(kept["id"])) == []
