"""Run the retrieval service: ``python -m herhealth_model``.

Serves on ``127.0.0.1:8001`` — 8000 is the backend's port (see
``herhealth_backend.app.__main__``), and the two are separate processes.
Unlike the backend, this has no async PostgreSQL driver, so plain
``uvicorn.run`` needs no Windows event-loop workaround.
"""

from __future__ import annotations

import logging
import os

# See the backend entry point: loopback by hand, 0.0.0.0 in a container,
# chosen by the environment rather than baked in.
HOST = os.environ.get("HERHEALTH_HOST", "127.0.0.1")
PORT = int(os.environ.get("HERHEALTH_PORT", "8001"))


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    uvicorn.run("herhealth_model.app:create_app", factory=True, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
