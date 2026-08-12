"""The FastAPI application: how the service boots and the one route it has.

:func:`create_app` is a factory rather than a module-level ``app`` so a test can
build an application bound to a throwaway database and never touch the real one.
Pass a :class:`~herhealth_backend.app.db.Database` in and the app uses it as-is;
pass nothing and the lifespan builds one from the environment at start-up and
disposes it at shutdown.

The only endpoint is ``/health``, and it is a real health check: it asks the
database a question and reports 503 if the answer does not come back. A skeleton
that returns 200 because the process is alive tells you nothing you did not
already know from the fact that it answered at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from herhealth_backend.app.config import database_url
from herhealth_backend.app.db import Database

__all__ = ["create_app"]


def create_app(database: Database | None = None) -> FastAPI:
    """Build the application.

    When ``database`` is given the caller owns its lifecycle — the app will not
    dispose it. When it is ``None`` the app creates one from
    :func:`~herhealth_backend.app.config.database_url` on start-up and disposes
    it on shutdown.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_database = getattr(app.state, "database", None) is None
        if owns_database:
            app.state.database = Database(database_url())
        try:
            yield
        finally:
            if owns_database:
                await app.state.database.dispose()

    app = FastAPI(title="HerHealthGPT backend", lifespan=lifespan)
    if database is not None:
        app.state.database = database

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        db: Database = request.app.state.database
        try:
            await db.ping()
        except (SQLAlchemyError, OSError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"}, status_code=200)

    return app
