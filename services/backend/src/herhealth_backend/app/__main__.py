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

The other non-obvious part is ``logging.basicConfig``. Without it, nothing in
this process's default (unconfigured) logging hierarchy has a handler at
INFO — ``ConsoleEmailSender`` (#10) would log a verification code and it
would go nowhere, silently, defeating the point of a *console* sender. One
call here, the process's one true entry point, is enough for every module
that just calls ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from herhealth_backend.app.eventloop import use_selector_loop_on_windows

# Loopback by default, so running this by hand on a dev box exposes nothing
# to the network. A container must bind 0.0.0.0 or nothing outside it can
# reach the port, so both are read from the environment and the Dockerfile
# sets them — rather than the image overriding a hard-coded literal.
HOST = os.environ.get("HERHEALTH_HOST", "127.0.0.1")
PORT = int(os.environ.get("HERHEALTH_PORT", "8000"))


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
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
