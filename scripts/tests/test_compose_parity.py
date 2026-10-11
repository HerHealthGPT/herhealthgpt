"""infra/compose.model.yml must describe the same three processes as
scripts/serve-models.sh. ``docker compose config`` needs the docker CLI but
no daemon, so this runs on the campus box."""

import json
import shutil
import subprocess
from pathlib import PurePosixPath
from typing import Any

import pytest
from helpers import REPO, SERVE_ENV, SERVICES, parse_env

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or shutil.which("bash") is None,
    reason="needs the docker CLI and bash",
)

COMPOSE = REPO / "infra" / "compose.model.yml"


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "--env-file",
            str(SERVE_ENV),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    loaded: dict[str, Any] = json.loads(result.stdout)
    return loaded


def _normalise(args: list[str]) -> list[str]:
    """Blank out the three values that legitimately differ between a native
    process and a container: the bind host, and two host paths."""
    out: list[str] = []
    previous = ""
    for arg in args:
        if previous == "--host":
            arg = "<host>"
        elif previous == "--lora-modules":
            arg = arg.split("=", 1)[0] + "=<adapter>"
        elif previous == "--chat-template":
            arg = PurePosixPath(arg).name
        out.append(arg)
        previous = arg if arg.startswith("--") else ""
    return out


def _launcher_args(service: str) -> list[str]:
    result = subprocess.run(
        ["bash", str(REPO / "scripts" / "serve-models.sh"), "print", service],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


@pytest.mark.parametrize("service", SERVICES)
def test_compose_command_matches_the_launcher(
    config: dict[str, Any], service: str
) -> None:
    definition = config["services"][service]
    assert definition["entrypoint"] == ["vllm"]
    assert _normalise(definition["command"]) == _normalise(_launcher_args(service))


@pytest.mark.parametrize("service", SERVICES)
def test_compose_reserves_the_gpus_serve_env_names(
    config: dict[str, Any], service: str
) -> None:
    env = parse_env(SERVE_ENV)
    devices = config["services"][service]["deploy"]["resources"]["reservations"][
        "devices"
    ]
    assert len(devices) == 1
    assert devices[0]["driver"] == "nvidia"
    assert devices[0]["device_ids"] == env[f"{service.upper()}_GPUS"].split(",")


@pytest.mark.parametrize("service", SERVICES)
def test_compose_publishes_on_localhost_only(
    config: dict[str, Any], service: str
) -> None:
    port = parse_env(SERVE_ENV)[f"{service.upper()}_PORT"]
    ports = config["services"][service]["ports"]
    assert len(ports) == 1
    assert ports[0]["host_ip"] == "127.0.0.1"
    assert str(ports[0]["published"]) == port
    assert str(ports[0]["target"]) == port


@pytest.mark.parametrize("service", SERVICES)
def test_compose_pins_the_image_and_never_downloads(
    config: dict[str, Any], service: str
) -> None:
    definition = config["services"][service]
    assert (
        definition["image"]
        == "vllm/vllm-openai:v" + parse_env(SERVE_ENV)["VLLM_VERSION"]
    )
    assert definition["environment"]["HF_HUB_OFFLINE"] == "1"
    assert definition["ipc"] == "host"
    assert "healthcheck" in definition
