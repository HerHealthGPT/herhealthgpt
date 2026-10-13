"""scripts/serve-models.sh, driven with a stub ``vllm`` so no GPU, model or
network is involved. The stub records its arguments and sleeps."""

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from helpers import REPO, SERVE_ENV, SERVICES, parse_env

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

SCRIPT = REPO / "scripts" / "serve-models.sh"
SHA = "a" * 40

STUB = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$STUB_DIR/args.$CUDA_VISIBLE_DEVICES"
printf '%s\\n' "$HF_HUB_OFFLINE" > "$STUB_DIR/offline.$CUDA_VISIBLE_DEVICES"
exec sleep 300
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class Box:
    """A throwaway stand-in for the campus box: env file, cache, stub binary."""

    root: Path
    env: dict[str, str]

    @property
    def run_dir(self) -> Path:
        return self.root / "run"

    def write_env(self) -> None:
        text = "\n".join(f"{key}={value}" for key, value in self.env.items())
        (self.root / "serve.conf").write_text(text + "\n", encoding="utf-8")

    def add_weights(self, service: str) -> None:
        prefix = service.upper()
        model = self.env[f"{prefix}_MODEL"].replace("/", "--")
        revision = self.env[f"{prefix}_REVISION"]
        (
            Path(self.env["HF_HOME"])
            / "hub"
            / f"models--{model}"
            / "snapshots"
            / revision
        ).mkdir(parents=True)

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.write_env()
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            env={
                **os.environ,
                "SERVE_ENV": str(self.root / "serve.conf"),
                "RUN_DIR": str(self.run_dir),
                "VLLM_BIN": str(self.root / "vllm"),
                "STUB_DIR": str(self.root / "stub"),
            },
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )

    def stub_args(self, gpus: str) -> list[str]:
        path = self.root / "stub" / f"args.{gpus}"
        for _ in range(50):
            if path.is_file() and path.read_text(encoding="utf-8"):
                return path.read_text(encoding="utf-8").splitlines()
            time.sleep(0.1)
        raise AssertionError(f"the stub was never started for GPUs {gpus}")

    def pid(self, service: str) -> int:
        # The pid file holds "<pid> <process start time>".
        return int(
            (self.run_dir / f"{service}.pid").read_text(encoding="utf-8").split()[0]
        )


@pytest.fixture
def box(tmp_path: Path) -> Iterator[Box]:
    env = parse_env(SERVE_ENV)
    env["HF_HOME"] = str(tmp_path / "hf")
    for service in SERVICES:
        env[f"{service.upper()}_REVISION"] = SHA
        env[f"{service.upper()}_PORT"] = str(_free_port())
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    env["CHAT_ADAPTER_DIR"] = str(adapter)
    (tmp_path / "stub").mkdir()
    stub = tmp_path / "vllm"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    made = Box(root=tmp_path, env=env)
    for service in SERVICES:
        made.add_weights(service)
    yield made
    made.run("stop", "all")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_print_chat_carries_the_proven_flags(box: Box) -> None:
    result = box.run("print", "chat")
    assert result.returncode == 0, result.stderr
    args = result.stdout.splitlines()
    assert args[:2] == ["serve", "Qwen/Qwen3.5-9B"]
    for flag in ("--enable-lora", "--disable-custom-all-reduce", "--enforce-eager"):
        assert flag in args
    assert args[args.index("--revision") + 1] == SHA
    assert args[args.index("--tensor-parallel-size") + 1] == "2"
    assert args[args.index("--max-model-len") + 1] == "32768"
    assert args[args.index("--max-lora-rank") + 1] == "16"
    assert args[args.index("--limit-mm-per-prompt") + 1] == '{"image":0,"video":0}'
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert (
        args[args.index("--lora-modules") + 1]
        == f"herhealth={box.env['CHAT_ADAPTER_DIR']}"
    )


def test_print_embed_is_a_pooling_model_under_its_served_name(box: Box) -> None:
    args = box.run("print", "embed").stdout.splitlines()
    assert args[:2] == ["serve", "Qwen/Qwen3-Embedding-4B"]
    assert args[args.index("--runner") + 1] == "pooling"
    assert args[args.index("--convert") + 1] == "embed"
    assert args[args.index("--served-model-name") + 1] == "herhealth-embed"


def test_print_rerank_uses_the_template_and_overrides(box: Box) -> None:
    args = box.run("print", "rerank").stdout.splitlines()
    assert args[:2] == ["serve", "Qwen/Qwen3-Reranker-4B"]
    assert args[args.index("--runner") + 1] == "pooling"
    assert args[args.index("--chat-template") + 1].endswith(
        "infra/model/qwen3_reranker.jinja"
    )
    overrides = args[args.index("--hf-overrides") + 1]
    assert '"is_original_qwen3_reranker":true' in overrides
    assert '"classifier_from_token":["no","yes"]' in overrides


def test_start_launches_each_service_on_its_own_gpus(box: Box) -> None:
    result = box.run("start", "all")
    assert result.returncode == 0, result.stderr
    assert box.stub_args("0,1")[1] == "Qwen/Qwen3.5-9B"
    assert box.stub_args("2")[1] == "Qwen/Qwen3-Embedding-4B"
    assert box.stub_args("3")[1] == "Qwen/Qwen3-Reranker-4B"
    assert (box.root / "stub" / "offline.2").read_text(encoding="utf-8").strip() == "1"
    for service in SERVICES:
        assert _alive(box.pid(service))


def test_start_refuses_when_weights_missing_and_starts_nothing(box: Box) -> None:
    shutil.rmtree(Path(box.env["HF_HOME"]) / "hub" / "models--Qwen--Qwen3-Reranker-4B")
    result = box.run("start", "all")
    assert result.returncode == 1
    assert "rerank: weights missing" in result.stderr
    assert "download Qwen/Qwen3-Reranker-4B" in result.stderr
    assert not (box.run_dir / "chat.pid").exists()


def test_start_refuses_unpinned_revision(box: Box) -> None:
    box.env["EMBED_REVISION"] = "UNPINNED"
    result = box.run("start", "embed")
    assert result.returncode == 1
    assert "EMBED_REVISION" in result.stderr
    assert "not a pinned commit" in result.stderr


def test_start_refuses_when_port_already_answers(box: Box) -> None:
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", int(box.env["CHAT_PORT"])))
        holder.listen()
        result = box.run("start", "chat")
    assert result.returncode == 1
    assert f"port {box.env['CHAT_PORT']} already answers" in result.stderr
    assert not (box.run_dir / "chat.pid").exists()


def test_start_recovers_from_a_stale_pid_file(box: Box) -> None:
    dead = subprocess.Popen(["true"])
    dead.wait()
    box.run_dir.mkdir()
    (box.run_dir / "embed.pid").write_text(str(dead.pid), encoding="utf-8")
    result = box.run("start", "embed")
    assert result.returncode == 0, result.stderr
    assert box.pid("embed") != dead.pid
    assert _alive(box.pid("embed"))


@pytest.mark.parametrize(
    "recorded_start", ["", " 1"], ids=["no-start-time", "wrong-start-time"]
)
def test_a_pid_file_naming_another_live_process_is_stale(
    box: Box, recorded_start: str
) -> None:
    # After a pod restart the pid files survive on the persistent volume and
    # their numbers get reused by unrelated processes. `stop` must not kill
    # one of those, and `start` must not mistake it for a running service.
    bystander = subprocess.Popen(["sleep", "60"])
    try:
        box.run_dir.mkdir()
        (box.run_dir / "embed.pid").write_text(
            f"{bystander.pid}{recorded_start}\n", encoding="utf-8"
        )

        stopped = box.run("stop", "embed")
        assert stopped.returncode == 0
        assert "embed: not running" in stopped.stdout
        time.sleep(0.5)
        assert bystander.poll() is None, "stop killed a process that is not ours"

        (box.run_dir / "embed.pid").write_text(
            f"{bystander.pid}{recorded_start}\n", encoding="utf-8"
        )
        started = box.run("start", "embed")
        assert started.returncode == 0, started.stderr
        assert box.pid("embed") != bystander.pid
    finally:
        bystander.kill()
        bystander.wait()


def test_start_refuses_a_service_that_is_already_running(box: Box) -> None:
    assert box.run("start", "embed").returncode == 0
    result = box.run("start", "embed")
    assert result.returncode == 1
    assert "already running" in result.stderr


def test_stop_terminates_the_process(box: Box) -> None:
    box.run("start", "embed")
    pid = box.pid("embed")
    result = box.run("stop", "embed")
    assert result.returncode == 0
    assert not _alive(pid)
    assert not (box.run_dir / "embed.pid").exists()


def test_check_reports_every_service_when_nothing_runs(box: Box) -> None:
    result = box.run("check")
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    for service in SERVICES:
        line = next(text for text in lines if text.startswith(service))
        assert "process=down" in line
        assert "endpoint=silent" in line
        assert "weights=present" in line


def test_unknown_service_is_a_usage_error(box: Box) -> None:
    result = box.run("start", "vision")
    assert result.returncode == 2
    assert "unknown service: vision" in result.stderr
