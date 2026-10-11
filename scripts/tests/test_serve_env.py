"""Invariants of infra/model/serve.conf, the single source both the native
launcher and the compose file read."""

import re

from helpers import SERVE_ENV, SERVICES, parse_env

SHA = re.compile(r"^[0-9a-f]{40}$")


def test_every_service_declares_its_fields() -> None:
    env = parse_env(SERVE_ENV)
    for service in SERVICES:
        prefix = service.upper()
        for field in ("MODEL", "REVISION", "GPUS", "PORT", "MAX_MODEL_LEN"):
            assert env.get(f"{prefix}_{field}"), f"{prefix}_{field} is missing or empty"


def test_ports_are_distinct_and_avoid_the_backend() -> None:
    env = parse_env(SERVE_ENV)
    ports = [env[f"{s.upper()}_PORT"] for s in SERVICES]
    assert ports == ["8002", "8003", "8004"]
    assert "8000" not in ports  # the backend's default port


def test_no_gpu_is_shared_between_services() -> None:
    env = parse_env(SERVE_ENV)
    seen: list[str] = []
    for service in SERVICES:
        seen.extend(env[f"{service.upper()}_GPUS"].split(","))
    assert sorted(seen) == ["0", "1", "2", "3"]


def test_chat_uses_two_gpus_and_the_agreed_window() -> None:
    env = parse_env(SERVE_ENV)
    assert env["CHAT_GPUS"] == "0,1"
    assert env["CHAT_TP"] == "2"
    assert env["CHAT_MAX_MODEL_LEN"] == "32768"
    assert env["CHAT_ADAPTER_NAME"] == "herhealth"


def test_every_revision_is_pinned() -> None:
    # The retrieval index is only valid against the exact embedding weights
    # that built it, so an unpinned revision is a defect.
    env = parse_env(SERVE_ENV)
    for service in SERVICES:
        key = f"{service.upper()}_REVISION"
        assert SHA.match(env[key]), f"{key} is not a 40-character commit id"
