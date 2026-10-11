"""Shared by the script tests. Nothing here touches the network or a GPU."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SERVE_ENV = REPO / "infra" / "model" / "serve.conf"
SERVICES = ("chat", "embed", "rerank")


def parse_env(path: Path) -> dict[str, str]:
    """Read a KEY=value file, skipping blank lines and comments."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values
