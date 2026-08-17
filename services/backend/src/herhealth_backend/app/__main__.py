"""Run the backend: ``python -m herhealth_backend.app``.

A thin entry point so the service can be started by hand for local development
and manual testing. It reads its database URL from ``HERHEALTH_DATABASE_URL``
(see ``infra/envs/backend.env.example``) and serves on ``127.0.0.1:8000``.

The non-obvious part is the Windows event loop. psycopg's async mode refuses the
``ProactorEventLoop``, and uvicorn hard-codes exactly that loop on Windows via
its own loop factory — so setting a policy is not enough, because ``uvicorn.run``
would override it. Instead we drive ``Server.serve`` on a selector loop of our
own. On the Linux deploy target this is the ordinary path; the branch only
changes anything on a Windows dev box. Reload is off: the reloader re-execs into
a worker that would not inherit any of this.
"""

from __future__ import annotations

import asyncio

from herhealth_backend.app.eventloop import use_selector_loop_on_windows

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    import uvicorn

    use_selector_loop_on_windows()

    config = uvicorn.Config(
        "herhealth_backend.app.main:create_app",
        factory=True,
        host=HOST,
        port=PORT,
    )
    server = uvicorn.Server(config)
    # Run the serve coroutine on the loop our policy creates, rather than
    # Server.run(), which would build uvicorn's own ProactorEventLoop on Windows.
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
