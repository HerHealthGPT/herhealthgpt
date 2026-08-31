"""The health endpoint, driven over HTTP against a real database.

These are the "the service boots and talks to Postgres" acceptance criteria made
executable. The first test drives the running application over ASGI rather than
calling the handler directly, so it exercises routing and response handling too.
The second points the app at a database that is not there and asserts the check
reports the failure instead of hiding it — a health check that cannot fail is
not a health check.
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from herhealth_backend.app import Database, create_app


async def test_health_ok_when_database_answers(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_unavailable_when_database_is_unreachable() -> None:
    # Port 1 has nothing listening, so the round-trip cannot complete.
    database = Database("postgresql+psycopg://nobody:nobody@127.0.0.1:1/absent")
    app = create_app(database=database)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    await database.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
