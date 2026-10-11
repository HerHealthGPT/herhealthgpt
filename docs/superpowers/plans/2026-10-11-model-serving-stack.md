# Model-Serving Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the fine-tuned chat model, `Qwen3-Embedding-4B` and `Qwen3-Reranker-4B` as three vLLM processes on the campus GPU box, defined once and runnable both natively and through Docker Compose.

**Architecture:** One env file (`infra/model/serve.conf`) holds every model id, pinned revision, port, GPU assignment and context length. A bash launcher runs the three processes natively on this box; a compose file defines the same three for a Docker host. A pytest parity test compares the two argument lists so they cannot drift, and a Python smoke script is the acceptance test against the live processes.

**Tech Stack:** vLLM 0.28.0, bash, Docker Compose v2 (validation only), Python 3.12, httpx, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-10-11-model-serving-stack-design.md`

## Global Constraints

- vLLM version is `0.28.0`, native binary at `/home/jovyan/herhealthgpt-venv/bin/vllm`. Do not upgrade it.
- Chat: `Qwen/Qwen3.5-9B` at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, adapter name `herhealth`, adapter folder `herhealth-lora-v2/` in the repo root (gitignored), GPUs `0,1`, port `8002`, window `32768`.
- Embeddings: `Qwen/Qwen3-Embedding-4B`, served name `herhealth-embed`, GPU `2`, port `8003`, window `8192`.
- Reranker: `Qwen/Qwen3-Reranker-4B`, served name `herhealth-rerank`, GPU `3`, port `8004`, window `8192`.
- Every process binds `127.0.0.1` natively. Compose publishes on `127.0.0.1` only.
- These chat flags are mandatory and must appear in both definitions: `--tensor-parallel-size 2`, `--disable-custom-all-reduce`, `--enforce-eager`, `--limit-mm-per-prompt '{"image":0,"video":0}'`, `--max-lora-rank 16`.
- No file, comment, string or commit message may describe the system as diagnosing.
- Tests never hit the network and never need a GPU. They use a stub `vllm` binary and `httpx.MockTransport`.
- **Ask before any network call and before any deletion.** Three need a go-ahead from the repo owner: the first `uv run` (installs from PyPI), deleting `/home/jovyan/.cache/pip`, and downloading the two models from Hugging Face.
- **Disk.** `/home/jovyan` is the only persistent volume and has about 15 GB free. Put the uv environment and cache on the ephemeral disk. Run this in every shell before any `uv` command:

  ```bash
  export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
  ```

- **Commits.** The repo owner has not authorised commits, and the working branch is `main`. Before Task 1, ask once whether to create the branch `feat/model-serving-stack` and commit per task. If the answer is no, skip every "Commit" step and leave the work in the tree.
- Do not touch the backend, the frontend, the database, `infra/compose.prod.yml` or the deploy workflow.

## Review Focus

Conditions the spec implies but does not spell out, most likely first. Each has a test in the task named.

1. **A port is already held** (a leftover vLLM, or the backend on 8000 moved elsewhere): `start` must refuse with the port number and start nothing. Task 2, `test_start_refuses_when_port_already_answers`.
2. **A stale pid file after the pod was culled**: `start` must treat the process as down and start it, not report "already running". Task 2, `test_start_recovers_from_a_stale_pid_file`.
3. **An unpinned or missing model** for one service during `start all`: nothing starts, and the message names the service and the download command. Task 2, `test_start_refuses_unpinned_revision` and `test_start_refuses_when_weights_missing_and_starts_nothing`.
4. **One process is down when the smoke test runs**: the script must still report every other check and exit non-zero, not stop at the first connection error. Task 4, `test_main_reports_every_check_when_one_service_is_down`.
5. **An endpoint answers 200 with an unexpected body**: the check fails with a readable reason, not a traceback. Task 4, `test_chat_malformed_payload_fails_cleanly`.

## File Structure

| File | Responsibility |
|---|---|
| `infra/model/serve.conf` (create) | Single source of model ids, revisions, ports, GPUs, windows |
| `infra/model/qwen3_reranker.jinja` (create) | Scoring prompt template the reranker needs |
| `scripts/serve-models.sh` (create) | Native launcher: `print`, `start`, `stop`, `check`, `clean` |
| `infra/compose.model.yml` (create) | The same three services for a Docker host |
| `scripts/smoke_models.py` (create) | Acceptance checks against live endpoints |
| `scripts/tests/conftest.py`, `helpers.py` (create) | Import paths and shared test helpers |
| `scripts/tests/test_serve_env.py` (create) | Invariants of `serve.conf` |
| `scripts/tests/test_serve_models.py` (create) | Launcher behaviour with a stub `vllm` |
| `scripts/tests/test_compose_parity.py` (create) | Compose matches launcher and `serve.conf` |
| `scripts/tests/test_smoke_models.py` (create) | Smoke checks with mocked HTTP |
| `Makefile` (modify) | Add `scripts` to `lint`, `fmt`, `test` |
| `scripts/setup-uni-vllm.sh` (delete) | Replaced by `serve-models.sh` |
| `docs/runbooks/uni-server-vllm.md`, `README.md` (modify) | Point at the new launcher and layout |

---

### Task 1: The shared env file and the reranker template

**Files:**
- Create: `infra/model/serve.conf`
- Create: `infra/model/qwen3_reranker.jinja`
- Create: `scripts/tests/conftest.py`
- Create: `scripts/tests/helpers.py`
- Create: `scripts/tests/test_serve_env.py`
- Modify: `Makefile` (the `lint`, `fmt` and `test` recipes)

**Interfaces:**
- Consumes: nothing.
- Produces: `infra/model/serve.conf` with keys `VLLM_VERSION`, `HF_HOME`, and for each of `CHAT`, `EMBED`, `RERANK`: `_MODEL`, `_REVISION`, `_GPUS`, `_PORT`, `_MAX_MODEL_LEN`; plus `CHAT_ADAPTER_NAME`, `CHAT_ADAPTER_DIR`, `CHAT_TP`, `EMBED_SERVED_NAME`, `RERANK_SERVED_NAME`. `helpers.parse_env(path: Path) -> dict[str, str]`, `helpers.REPO: Path`, `helpers.SERVE_ENV: Path`.

- [ ] **Step 1: Write the test helpers**

`scripts/tests/conftest.py`:

```python
"""Make ``scripts/`` and this directory importable for the script tests."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for path in (_HERE, _HERE.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
```

`scripts/tests/helpers.py`:

```python
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
```

- [ ] **Step 2: Write the failing test**

`scripts/tests/test_serve_env.py`:

```python
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


def test_chat_revision_is_pinned() -> None:
    assert SHA.match(parse_env(SERVE_ENV)["CHAT_REVISION"])


def test_other_revisions_are_pinned_or_explicitly_unpinned() -> None:
    # Task 5 downloads the two models and replaces UNPINNED with real commits,
    # then tightens this test.
    env = parse_env(SERVE_ENV)
    for key in ("EMBED_REVISION", "RERANK_REVISION"):
        assert env[key] == "UNPINNED" or SHA.match(env[key]), key
```

- [ ] **Step 3: Run the test to verify it fails**

Run (this is the first `uv run`; it installs from PyPI, so get the go-ahead first):

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
uv run pytest scripts/tests/test_serve_env.py -q
```

Expected: FAIL, `FileNotFoundError` for `infra/model/serve.conf`.

- [ ] **Step 4: Create the env file**

`infra/model/serve.conf`:

```
# The single source of truth for the three vLLM processes.
# Read by scripts/serve-models.sh (sourced) and infra/compose.model.yml
# (--env-file). Plain KEY=value only: no quotes, no spaces, no secrets.
# See docs/superpowers/specs/2026-10-11-model-serving-stack-design.md.

VLLM_VERSION=0.28.0

# Where the Hugging Face cache lives on the host. On the campus box this must
# be on /home/jovyan, the only volume that survives a pod restart.
HF_HOME=/home/jovyan/.cache/huggingface

# --- chat: Qwen3.5-9B plus the project's LoRA adapter -----------------------
CHAT_MODEL=Qwen/Qwen3.5-9B
CHAT_REVISION=c202236235762e1c871ad0ccb60c8ee5ba337b9a
CHAT_ADAPTER_NAME=herhealth
# Relative to the repo root, or an absolute path.
CHAT_ADAPTER_DIR=herhealth-lora-v2
# Tensor-parallel size must divide 16 attention heads and 4 key-value heads:
# 1, 2 or 4. Keep CHAT_TP equal to the number of ids in CHAT_GPUS.
CHAT_GPUS=0,1
CHAT_TP=2
CHAT_PORT=8002
# 32,768 leaves room for 5.6 full-length requests in the 183,947-token cache
# measured on 2026-09-17 with --enforce-eager.
CHAT_MAX_MODEL_LEN=32768

# --- embeddings -------------------------------------------------------------
EMBED_MODEL=Qwen/Qwen3-Embedding-4B
EMBED_REVISION=UNPINNED
EMBED_SERVED_NAME=herhealth-embed
EMBED_GPUS=2
EMBED_PORT=8003
EMBED_MAX_MODEL_LEN=8192

# --- reranker ---------------------------------------------------------------
RERANK_MODEL=Qwen/Qwen3-Reranker-4B
RERANK_REVISION=UNPINNED
RERANK_SERVED_NAME=herhealth-rerank
RERANK_GPUS=3
RERANK_PORT=8004
RERANK_MAX_MODEL_LEN=8192
```

- [ ] **Step 5: Create the reranker template**

vLLM's scoring endpoint passes two messages with roles `query` and `document` to this template. Without a template it concatenates the two strings, which is not the prompt `Qwen3-Reranker` was trained on. The wording below is the prompt format from the Qwen3-Reranker model card, laid out as in vLLM's own `qwen3_reranker.jinja` example. Task 5's smoke check 5 is its test.

`infra/model/qwen3_reranker.jinja` (the file must end with the blank line after `</think>`):

```
<|im_start|>system
Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>
<|im_start|>user
<Instruct>: {{ messages | selectattr("role", "eq", "system") | map(attribute="content") | first | default("Given a web search query, retrieve relevant passages that answer the query") }}
<Query>: {{ messages | selectattr("role", "eq", "query") | map(attribute="content") | first }}
<Document>: {{ messages | selectattr("role", "eq", "document") | map(attribute="content") | first }}<|im_end|>
<|im_start|>assistant
<think>

</think>

```

- [ ] **Step 6: Add `scripts` to the Makefile recipes**

In `Makefile`, replace the `lint`, `fmt` and `test` recipe lines so each also covers the scripts:

```make
lint:
	$(UV) run ruff check packages/contracts services/data services/backend services/model scripts/smoke_models.py scripts/tests
	$(UV) run mypy --config-file packages/contracts/pyproject.toml packages/contracts/src

fmt:
	$(UV) run ruff format packages/contracts services/data services/backend services/model scripts/smoke_models.py scripts/tests
	$(UV) run ruff check --fix packages/contracts services/data services/backend services/model scripts/smoke_models.py scripts/tests
```

and in the `test` recipe add `scripts/tests` to the path list:

```make
test:
	$(UV) run --extra ingest pytest packages/contracts/tests services/data/tests services/backend/tests services/model/tests scripts/tests --ignore=services/backend/tests/app -q
```

`scripts/smoke_models.py` does not exist until Task 4, so `make lint` fails on that path until then. That is expected; run ruff on `scripts/tests` directly in this task.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest scripts/tests/test_serve_env.py -q && uv run ruff check scripts/tests`
Expected: `6 passed`, and ruff reports no errors.

- [ ] **Step 8: Commit**

```bash
git add infra/model/serve.conf infra/model/qwen3_reranker.jinja scripts/tests Makefile
git commit -m "feat(infra): add the shared env file for the three vLLM processes"
```

---

### Task 2: The native launcher

**Files:**
- Create: `scripts/serve-models.sh`
- Create: `scripts/tests/test_serve_models.py`

**Interfaces:**
- Consumes: `infra/model/serve.conf` keys from Task 1; `helpers.parse_env`, `helpers.SERVE_ENV`, `helpers.REPO`.
- Produces: `bash scripts/serve-models.sh <command>` where command is one of:
  - `print <chat|embed|rerank>`: prints the `vllm` arguments, one per line, starting with `serve`. Starts nothing.
  - `start [chat|embed|rerank|all]`, `stop [chat|embed|rerank|all]`, `check`, `clean`.
  - Environment overrides: `SERVE_ENV` (env file path), `RUN_DIR` (pid and log directory, default `/home/jovyan/herhealth-serve`), `VLLM_BIN` (default `/home/jovyan/herhealthgpt-venv/bin/vllm`).
  - Exit codes: `0` success, `1` refused, `2` usage error.

- [ ] **Step 1: Write the failing tests**

`scripts/tests/test_serve_models.py`:

```python
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
        (Path(self.env["HF_HOME"]) / "hub" / f"models--{model}" / "snapshots" / revision).mkdir(
            parents=True
        )

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
        return int((self.run_dir / f"{service}.pid").read_text(encoding="utf-8"))


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
    assert args[args.index("--lora-modules") + 1] == f"herhealth={box.env['CHAT_ADAPTER_DIR']}"


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
    assert args[args.index("--chat-template") + 1].endswith("infra/model/qwen3_reranker.jinja")
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest scripts/tests/test_serve_models.py -q`
Expected: every test FAILS, because `bash` cannot open `scripts/serve-models.sh` (exit code 127).

- [ ] **Step 3: Write the launcher**

`scripts/serve-models.sh`:

```bash
#!/usr/bin/env bash
# Start, stop and inspect the three vLLM processes on the campus GPU box.
#
#   bash scripts/serve-models.sh start [chat|embed|rerank|all]
#   bash scripts/serve-models.sh stop  [chat|embed|rerank|all]
#   bash scripts/serve-models.sh check            # report state, change nothing
#   bash scripts/serve-models.sh clean            # stop all, kill leftovers, free the GPUs
#   bash scripts/serve-models.sh print <service>  # the vllm arguments, one per line
#
# Every model id, revision, port and GPU comes from infra/model/serve.conf, the
# same file infra/compose.model.yml reads. This script never downloads: a
# missing model is reported with the command that fetches it.
#
# Design and the reasons for each flag:
# docs/superpowers/specs/2026-10-11-model-serving-stack-design.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVE_ENV="${SERVE_ENV:-$REPO_ROOT/infra/model/serve.conf}"
set -a
# shellcheck disable=SC1090
. "$SERVE_ENV"
set +a

VLLM_BIN="${VLLM_BIN:-/home/jovyan/herhealthgpt-venv/bin/vllm}"
HF_BIN="${VLLM_BIN%/*}/hf"
RUN_DIR="${RUN_DIR:-/home/jovyan/herhealth-serve}"   # persistent volume
HOST="127.0.0.1"   # never the cluster network: reach it via a tunnel or proxy
ALL_SERVICES=(chat embed rerank)
TARGETS=()

# The original Qwen3 reranker is a causal LM scored on its "yes"/"no" logits.
# These keys switch on vLLM's path for it; see
# vllm/model_executor/models/config.py, Qwen3ForSequenceClassificationConfig.
RERANK_OVERRIDES='{"architectures":["Qwen3ForSequenceClassification"],"classifier_from_token":["no","yes"],"is_original_qwen3_reranker":true}'

# field chat PORT  ->  the value of CHAT_PORT
field() {
  local name="${1^^}_$2"
  printf '%s' "${!name}"
}

adapter_dir() {
  case "$CHAT_ADAPTER_DIR" in
    /*) printf '%s' "$CHAT_ADAPTER_DIR" ;;
    *)  printf '%s' "$REPO_ROOT/$CHAT_ADAPTER_DIR" ;;
  esac
}

snapshot_dir() {
  local model
  model="$(field "$1" MODEL)"
  printf '%s/hub/models--%s/snapshots/%s' "$HF_HOME" "${model//\//--}" "$(field "$1" REVISION)"
}

is_sha() { [[ "$1" =~ ^[0-9a-f]{40}$ ]]; }
pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }

running() {
  local file
  file="$(pid_file "$1")"
  [ -f "$file" ] && kill -0 "$(cat "$file")" 2>/dev/null
}

port_open() { (exec 3<>"/dev/tcp/$HOST/$1") 2>/dev/null; }

# The vllm arguments for one service, one per line. infra/compose.model.yml
# must carry the same list; scripts/tests/test_compose_parity.py checks it.
svc_args() {
  case "$1" in
    chat)
      # --disable-custom-all-reduce is MANDATORY: over a broken GPU peer link
      #   the custom all-reduce corrupts activations until the model emits
      #   "!!!!!!!". docs/runbooks/uni-server-vllm.md section 0.1.
      # --limit-mm-per-prompt needs BOTH keys: the base is a multimodal
      #   hybrid, not a text model. Runbook section 0.2.
      # --enforce-eager is what leaves 3.98 GiB per GPU for the token cache.
      printf '%s\n' \
        serve "$CHAT_MODEL" \
        --revision "$CHAT_REVISION" \
        --enable-lora \
        --lora-modules "$CHAT_ADAPTER_NAME=$(adapter_dir)" \
        --max-lora-rank 16 \
        --max-model-len "$CHAT_MAX_MODEL_LEN" \
        --tensor-parallel-size "$CHAT_TP" \
        --disable-custom-all-reduce \
        --enforce-eager \
        --limit-mm-per-prompt '{"image":0,"video":0}' \
        --host "$HOST" --port "$CHAT_PORT"
      ;;
    embed)
      printf '%s\n' \
        serve "$EMBED_MODEL" \
        --revision "$EMBED_REVISION" \
        --served-model-name "$EMBED_SERVED_NAME" \
        --runner pooling \
        --convert embed \
        --max-model-len "$EMBED_MAX_MODEL_LEN" \
        --host "$HOST" --port "$EMBED_PORT"
      ;;
    rerank)
      printf '%s\n' \
        serve "$RERANK_MODEL" \
        --revision "$RERANK_REVISION" \
        --served-model-name "$RERANK_SERVED_NAME" \
        --runner pooling \
        --hf-overrides "$RERANK_OVERRIDES" \
        --chat-template "$REPO_ROOT/infra/model/qwen3_reranker.jinja" \
        --max-model-len "$RERANK_MAX_MODEL_LEN" \
        --host "$HOST" --port "$RERANK_PORT"
      ;;
  esac
}

resolve_targets() {
  case "${1:-all}" in
    all) TARGETS=("${ALL_SERVICES[@]}") ;;
    chat|embed|rerank) TARGETS=("$1") ;;
    *)
      echo "unknown service: $1 (expected chat, embed, rerank or all)" >&2
      exit 2
      ;;
  esac
}

# Every reason a service cannot be started, checked before anything starts.
preflight() {
  local svc="$1" rev model port
  rev="$(field "$svc" REVISION)"
  model="$(field "$svc" MODEL)"
  port="$(field "$svc" PORT)"
  if [ ! -x "$VLLM_BIN" ]; then
    echo "$svc: vllm not found at $VLLM_BIN" >&2
    return 1
  fi
  if running "$svc"; then
    echo "$svc: already running (pid $(cat "$(pid_file "$svc")")) - stop it first" >&2
    return 1
  fi
  if ! is_sha "$rev"; then
    echo "$svc: ${svc^^}_REVISION in $SERVE_ENV is not a pinned commit." >&2
    echo "  fetch the model: HF_HOME=$HF_HOME $HF_BIN download $model" >&2
    echo "  then set it to the directory name under $HF_HOME/hub/models--${model//\//--}/snapshots/" >&2
    return 1
  fi
  if [ ! -d "$(snapshot_dir "$svc")" ]; then
    echo "$svc: weights missing at $(snapshot_dir "$svc")" >&2
    echo "  fetch them: HF_HOME=$HF_HOME $HF_BIN download $model --revision $rev" >&2
    return 1
  fi
  if [ "$svc" = chat ] && [ ! -f "$(adapter_dir)/adapter_config.json" ]; then
    echo "chat: no adapter at $(adapter_dir) (adapter_config.json not found)" >&2
    return 1
  fi
  if port_open "$port"; then
    echo "$svc: port $port already answers - another process holds it" >&2
    return 1
  fi
}

start_one() {
  local svc="$1"
  local -a args
  mapfile -t args < <(svc_args "$svc")
  mkdir -p "$RUN_DIR"
  # HF_HUB_OFFLINE=1: a start never reaches the network.
  # NCCL_* and the sampler switch are the settings the last working serve used.
  nohup env \
    CUDA_VISIBLE_DEVICES="$(field "$svc" GPUS)" \
    HF_HOME="$HF_HOME" \
    HF_HUB_OFFLINE=1 \
    NCCL_P2P_DISABLE=1 \
    NCCL_IB_DISABLE=1 \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-$HOME/.cache/triton}" \
    "$VLLM_BIN" "${args[@]}" > "$RUN_DIR/$svc.log" 2>&1 < /dev/null &
  echo $! > "$(pid_file "$svc")"
  echo "$svc: started (pid $!), log $RUN_DIR/$svc.log"
}

start() {
  local svc failed=0
  resolve_targets "${1:-all}"
  for svc in "${TARGETS[@]}"; do
    preflight "$svc" || failed=1
  done
  if [ "$failed" -ne 0 ]; then
    echo "nothing was started" >&2
    exit 1
  fi
  for svc in "${TARGETS[@]}"; do
    start_one "$svc"
  done
  echo "wait for 'Application startup complete.' in each log, then run: bash scripts/serve-models.sh check"
}

stop_one() {
  local svc="$1" file pid
  file="$(pid_file "$svc")"
  if ! running "$svc"; then
    rm -f "$file"
    echo "$svc: not running"
    return 0
  fi
  pid="$(cat "$file")"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$file"
  echo "$svc: stopped"
}

stop() {
  local svc
  resolve_targets "${1:-all}"
  for svc in "${TARGETS[@]}"; do
    stop_one "$svc"
  done
}

check() {
  local svc port state endpoint weights
  for svc in "${ALL_SERVICES[@]}"; do
    port="$(field "$svc" PORT)"
    if running "$svc"; then
      state="up(pid $(cat "$(pid_file "$svc")"))"
    else
      state="down"
    fi
    if curl -sf --max-time 2 "http://$HOST:$port/v1/models" >/dev/null 2>&1; then
      endpoint="answering"
    else
      endpoint="silent"
    fi
    if [ -d "$(snapshot_dir "$svc")" ]; then
      weights="present"
    else
      weights="MISSING"
    fi
    printf '%-7s process=%s endpoint=%s port=%s gpus=%s weights=%s\n' \
      "$svc" "$state" "$endpoint" "$port" "$(field "$svc" GPUS)" "$weights"
  done
  if [ -f "$(adapter_dir)/adapter_config.json" ]; then
    echo "adapter present at $(adapter_dir)"
  else
    echo "adapter MISSING at $(adapter_dir)"
  fi
  echo "disk    $(df -h --output=avail "$HF_HOME" 2>/dev/null | tail -1 | tr -d ' ' || echo unknown) free under $HF_HOME"
}

clean() {
  stop all
  if pgrep -f 'vllm serve' >/dev/null 2>&1; then
    pkill -f 'vllm serve' || true
    sleep 2
    pkill -9 -f 'vllm serve' 2>/dev/null || true
    echo "killed leftover vllm serve"
  fi
  pkill -9 -f 'VLLM::' 2>/dev/null || true
  # Stale GPU peer-access probe. A wrong entry here is what let the custom
  # all-reduce stay enabled over a broken link. Runbook section 0.1.
  rm -rf "$HOME/.cache/vllm"
  nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader 2>/dev/null || true
}

case "${1:-}" in
  print)
    resolve_targets "${2:-}"
    if [ "${#TARGETS[@]}" -ne 1 ]; then
      echo "print needs exactly one service: chat, embed or rerank" >&2
      exit 2
    fi
    svc_args "${TARGETS[0]}"
    ;;
  start) start "${2:-all}" ;;
  stop)  stop "${2:-all}" ;;
  check) check ;;
  clean) clean ;;
  *)
    echo "usage: serve-models.sh {start|stop} [chat|embed|rerank|all] | check | clean | print <service>" >&2
    exit 2
    ;;
esac
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest scripts/tests/test_serve_models.py -q && bash -n scripts/serve-models.sh`
Expected: `12 passed`, and `bash -n` prints nothing.

If `shellcheck` is installed (`command -v shellcheck`), also run `shellcheck scripts/serve-models.sh` and fix anything it reports. It is not installed on the campus box.

- [ ] **Step 5: Commit**

```bash
git add scripts/serve-models.sh scripts/tests/test_serve_models.py
git commit -m "feat(infra): add the native launcher for the three vLLM processes"
```

---

### Task 3: The compose file and the parity test

**Files:**
- Create: `infra/compose.model.yml`
- Create: `scripts/tests/test_compose_parity.py`

**Interfaces:**
- Consumes: `infra/model/serve.conf` (Task 1); `bash scripts/serve-models.sh print <service>` (Task 2).
- Produces: `infra/compose.model.yml` with services named `chat`, `embed`, `rerank`. Started on a Docker host with `docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf up -d`.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_compose_parity.py`:

```python
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
            "docker", "compose", "-f", str(COMPOSE), "--env-file", str(SERVE_ENV),
            "config", "--format", "json",
        ],
        capture_output=True,
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
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


@pytest.mark.parametrize("service", SERVICES)
def test_compose_command_matches_the_launcher(config: dict[str, Any], service: str) -> None:
    definition = config["services"][service]
    assert definition["entrypoint"] == ["vllm"]
    assert _normalise(definition["command"]) == _normalise(_launcher_args(service))


@pytest.mark.parametrize("service", SERVICES)
def test_compose_reserves_the_gpus_serve_env_names(config: dict[str, Any], service: str) -> None:
    env = parse_env(SERVE_ENV)
    devices = config["services"][service]["deploy"]["resources"]["reservations"]["devices"]
    assert len(devices) == 1
    assert devices[0]["driver"] == "nvidia"
    assert devices[0]["device_ids"] == env[f"{service.upper()}_GPUS"].split(",")


@pytest.mark.parametrize("service", SERVICES)
def test_compose_publishes_on_localhost_only(config: dict[str, Any], service: str) -> None:
    port = parse_env(SERVE_ENV)[f"{service.upper()}_PORT"]
    ports = config["services"][service]["ports"]
    assert len(ports) == 1
    assert ports[0]["host_ip"] == "127.0.0.1"
    assert str(ports[0]["published"]) == port
    assert str(ports[0]["target"]) == port


@pytest.mark.parametrize("service", SERVICES)
def test_compose_pins_the_image_and_never_downloads(config: dict[str, Any], service: str) -> None:
    definition = config["services"][service]
    assert definition["image"] == "vllm/vllm-openai:v" + parse_env(SERVE_ENV)["VLLM_VERSION"]
    assert definition["environment"]["HF_HUB_OFFLINE"] == "1"
    assert definition["ipc"] == "host"
    assert "healthcheck" in definition
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest scripts/tests/test_compose_parity.py -q`
Expected: 12 errors from the `config` fixture, with stderr saying `infra/compose.model.yml` does not exist.

- [ ] **Step 3: Write the compose file**

`infra/compose.model.yml`:

```yaml
# The three vLLM processes, for a host with Docker and the NVIDIA container
# toolkit. Start with:
#
#   docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf up -d
#
# The campus box cannot run this: it is an unprivileged pod with no Docker
# daemon, so there the same processes are started natively by
# scripts/serve-models.sh. Both read infra/model/serve.conf, and
# scripts/tests/test_compose_parity.py fails if the argument lists differ.
#
# device_ids cannot be interpolated from a comma-separated variable, so they
# are written out here and the same test checks them against *_GPUS.
#
# Nothing downloads at start-up: the Hugging Face cache is mounted read-only
# and HF_HUB_OFFLINE=1. Fetch the models on the host first.

name: herhealth-models

x-vllm: &vllm
  image: vllm/vllm-openai:v${VLLM_VERSION}
  entrypoint: ["vllm"]
  ipc: host   # shared memory between vLLM's worker processes
  restart: unless-stopped

services:
  chat:
    <<: *vllm
    command:
      - serve
      - ${CHAT_MODEL}
      - --revision
      - ${CHAT_REVISION}
      - --enable-lora
      - --lora-modules
      - ${CHAT_ADAPTER_NAME}=/adapters/herhealth
      - --max-lora-rank
      - "16"
      - --max-model-len
      - "${CHAT_MAX_MODEL_LEN}"
      - --tensor-parallel-size
      - "${CHAT_TP}"
      # Mandatory. See docs/runbooks/uni-server-vllm.md section 0.1.
      - --disable-custom-all-reduce
      - --enforce-eager
      # Both keys. The base is a multimodal hybrid. Runbook section 0.2.
      - --limit-mm-per-prompt
      - '{"image":0,"video":0}'
      - --host
      - 0.0.0.0
      - --port
      - "${CHAT_PORT}"
    environment:
      HF_HOME: /hf
      HF_HUB_OFFLINE: "1"
      NCCL_P2P_DISABLE: "1"
      NCCL_IB_DISABLE: "1"
      VLLM_USE_FLASHINFER_SAMPLER: "0"
    volumes:
      - ${HF_HOME}:/hf:ro
      - ../${CHAT_ADAPTER_DIR}:/adapters/herhealth:ro
    ports:
      - "127.0.0.1:${CHAT_PORT}:${CHAT_PORT}"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0", "1"]
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${CHAT_PORT}/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 600s

  embed:
    <<: *vllm
    command:
      - serve
      - ${EMBED_MODEL}
      - --revision
      - ${EMBED_REVISION}
      - --served-model-name
      - ${EMBED_SERVED_NAME}
      - --runner
      - pooling
      - --convert
      - embed
      - --max-model-len
      - "${EMBED_MAX_MODEL_LEN}"
      - --host
      - 0.0.0.0
      - --port
      - "${EMBED_PORT}"
    environment:
      HF_HOME: /hf
      HF_HUB_OFFLINE: "1"
    volumes:
      - ${HF_HOME}:/hf:ro
    ports:
      - "127.0.0.1:${EMBED_PORT}:${EMBED_PORT}"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["2"]
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${EMBED_PORT}/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 300s

  rerank:
    <<: *vllm
    command:
      - serve
      - ${RERANK_MODEL}
      - --revision
      - ${RERANK_REVISION}
      - --served-model-name
      - ${RERANK_SERVED_NAME}
      - --runner
      - pooling
      - --hf-overrides
      - '{"architectures":["Qwen3ForSequenceClassification"],"classifier_from_token":["no","yes"],"is_original_qwen3_reranker":true}'
      - --chat-template
      - /templates/qwen3_reranker.jinja
      - --max-model-len
      - "${RERANK_MAX_MODEL_LEN}"
      - --host
      - 0.0.0.0
      - --port
      - "${RERANK_PORT}"
    environment:
      HF_HOME: /hf
      HF_HUB_OFFLINE: "1"
    volumes:
      - ${HF_HOME}:/hf:ro
      - ./model/qwen3_reranker.jinja:/templates/qwen3_reranker.jinja:ro
    ports:
      - "127.0.0.1:${RERANK_PORT}:${RERANK_PORT}"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["3"]
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${RERANK_PORT}/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 300s
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest scripts/tests/test_compose_parity.py -q`
Expected: `12 passed`.

If `test_compose_command_matches_the_launcher` fails, the assertion diff shows the first differing argument. Fix whichever side departs from the Global Constraints; do not loosen `_normalise`.

- [ ] **Step 5: Validate the file the way a user would**

Run: `docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf config --quiet && echo valid`
Expected: `valid`.

- [ ] **Step 6: Commit**

```bash
git add infra/compose.model.yml scripts/tests/test_compose_parity.py
git commit -m "feat(infra): add a compose definition of the model-serving stack"
```

---

### Task 4: The smoke script

**Files:**
- Create: `scripts/smoke_models.py`
- Create: `scripts/tests/test_smoke_models.py`

**Interfaces:**
- Consumes: `infra/model/serve.conf` keys (Task 1). `herhealth_contracts.decision.TriageDecision` for the structured-output schema, imported only when the probe runs.
- Produces: `uv run python scripts/smoke_models.py [--env PATH] [--skip-structured]`. Exit code `0` when every check passes, `1` otherwise. The structured-output probe is reported but never changes the exit code. Functions: `load_env(path) -> dict[str, str]`, `looks_corrupted(text) -> bool`, `check_health`, `check_models`, `check_chat`, `check_embeddings`, `check_rerank`, `probe_structured`, each returning `CheckResult(name: str, ok: bool, detail: str)`, and `main(argv=None, *, transport=None) -> int`.

- [ ] **Step 1: Write the failing tests**

`scripts/tests/test_smoke_models.py`:

```python
"""scripts/smoke_models.py against a mocked HTTP layer. No process, GPU or
network is involved."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import smoke_models
from helpers import SERVE_ENV

Handler = Callable[[httpx.Request], httpx.Response]

CHAT = "http://127.0.0.1:8002"
EMBED = "http://127.0.0.1:8003"
RERANK = "http://127.0.0.1:8004"


def _json(payload: object, status: int = 200) -> Handler:
    return lambda request: httpx.Response(status, json=payload)


def _transport(routes: dict[tuple[str, int, str], Handler]) -> httpx.MockTransport:
    """Routes keyed by (method, port, path). Anything else refuses the
    connection, which is what a process that is down looks like."""

    def handler(request: httpx.Request) -> httpx.Response:
        route = routes.get((request.method, request.url.port or 0, request.url.path))
        if route is None:
            raise httpx.ConnectError("connection refused", request=request)
        return route(request)

    return httpx.MockTransport(handler)


def _client(routes: dict[tuple[str, int, str], Handler]) -> httpx.Client:
    return httpx.Client(transport=_transport(routes))


def _chat_reply(text: str) -> Handler:
    return _json({"choices": [{"message": {"content": text}, "finish_reason": "stop"}]})


def _rerank(relevant: float, irrelevant: float) -> Handler:
    return _json(
        {
            "results": [
                {"index": 1, "relevance_score": irrelevant},
                {"index": 0, "relevance_score": relevant},
            ]
        }
    )


def _healthy_routes() -> dict[tuple[str, int, str], Handler]:
    ok = lambda request: httpx.Response(200)  # noqa: E731
    return {
        ("GET", 8002, "/health"): ok,
        ("GET", 8003, "/health"): ok,
        ("GET", 8004, "/health"): ok,
        ("GET", 8002, "/v1/models"): _json(
            {"data": [{"id": "Qwen/Qwen3.5-9B"}, {"id": "herhealth"}]}
        ),
        ("POST", 8002, "/v1/chat/completions"): _chat_reply("A calendar shows the date."),
        ("POST", 8003, "/v1/embeddings"): _json(
            {"data": [{"embedding": [0.6, 0.8]}, {"embedding": [1.0, 0.0]}, {"embedding": [0.0, 1.0]}]}
        ),
        ("POST", 8004, "/v1/rerank"): _rerank(0.93, 0.02),
    }


@pytest.mark.parametrize(
    ("text", "corrupted"),
    [
        ("", True),
        ("   \n", True),
        ("!!!!!!!!!!!", True),
        ("! ! ! ! !", True),
        ("Yes!", False),
        ("A calendar shows the date.", False),
        ("التقويم يعرض التاريخ.", False),
    ],
)
def test_looks_corrupted(text: str, corrupted: bool) -> None:
    assert smoke_models.looks_corrupted(text) is corrupted


def test_load_env_reads_the_real_file() -> None:
    env = smoke_models.load_env(SERVE_ENV)
    assert env["CHAT_PORT"] == "8002"
    assert env["EMBED_SERVED_NAME"] == "herhealth-embed"


def test_health_ok_and_down() -> None:
    client = _client({("GET", 8002, "/health"): lambda r: httpx.Response(200)})
    assert smoke_models.check_health(client, CHAT).ok
    down = smoke_models.check_health(client, EMBED)
    assert not down.ok
    assert "connection refused" in down.detail


def test_models_reports_a_missing_adapter() -> None:
    client = _client({("GET", 8002, "/v1/models"): _json({"data": [{"id": "Qwen/Qwen3.5-9B"}]})})
    result = smoke_models.check_models(client, CHAT, ["Qwen/Qwen3.5-9B", "herhealth"])
    assert not result.ok
    assert "herhealth" in result.detail


def test_chat_ok() -> None:
    client = _client({("POST", 8002, "/v1/chat/completions"): _chat_reply("Bonjour.")})
    assert smoke_models.check_chat(client, CHAT, "herhealth", "fr", "Bonjour ?").ok


def test_chat_flags_the_corruption_signature() -> None:
    client = _client({("POST", 8002, "/v1/chat/completions"): _chat_reply("!!!!!!!!!!!!")})
    result = smoke_models.check_chat(client, CHAT, "herhealth", "en", "Hello?")
    assert not result.ok
    assert "corrupted" in result.detail


def test_chat_malformed_payload_fails_cleanly() -> None:
    client = _client({("POST", 8002, "/v1/chat/completions"): _json({"error": "boom"})})
    result = smoke_models.check_chat(client, CHAT, "herhealth", "en", "Hello?")
    assert not result.ok
    assert "unexpected response" in result.detail


def test_embeddings_ok_reports_the_width() -> None:
    client = _client(_healthy_routes())
    result = smoke_models.check_embeddings(client, EMBED, "herhealth-embed", ["a", "b", "c"])
    assert result.ok
    assert "width=2" in result.detail


def test_embeddings_rejects_ragged_widths() -> None:
    client = _client(
        {("POST", 8003, "/v1/embeddings"): _json({"data": [{"embedding": [1.0]}, {"embedding": [1.0, 2.0]}]})}
    )
    result = smoke_models.check_embeddings(client, EMBED, "herhealth-embed", ["a", "b"])
    assert not result.ok
    assert "widths differ" in result.detail


def test_embeddings_rejects_non_finite_values() -> None:
    body = b'{"data": [{"embedding": [NaN, 1.0]}]}'
    client = _client({("POST", 8003, "/v1/embeddings"): lambda r: httpx.Response(200, content=body)})
    result = smoke_models.check_embeddings(client, EMBED, "herhealth-embed", ["a"])
    assert not result.ok
    assert "non-finite" in result.detail


def test_rerank_ok_when_the_relevant_passage_scores_higher() -> None:
    client = _client({("POST", 8004, "/v1/rerank"): _rerank(0.9, 0.1)})
    assert smoke_models.check_rerank(client, RERANK, "herhealth-rerank", "en", "q", "rel", "irr").ok


def test_rerank_fails_when_the_order_is_wrong() -> None:
    client = _client({("POST", 8004, "/v1/rerank"): _rerank(0.1, 0.9)})
    result = smoke_models.check_rerank(client, RERANK, "herhealth-rerank", "ar", "q", "rel", "irr")
    assert not result.ok
    assert "0.1" in result.detail and "0.9" in result.detail


def test_structured_probe_pass() -> None:
    routes = {
        ("POST", 8002, "/v1/chat/completions"): _chat_reply('{"type": "ask", "rationale": "x"}'),
        ("GET", 8002, "/health"): lambda r: httpx.Response(200),
    }
    result = smoke_models.probe_structured(_client(routes), CHAT, "herhealth", {"type": "object"})
    assert result.ok
    assert result.detail.startswith("PASS")


def test_structured_probe_fail_when_the_reply_is_not_json() -> None:
    routes = {
        ("POST", 8002, "/v1/chat/completions"): _chat_reply("Sure, here you go"),
        ("GET", 8002, "/health"): lambda r: httpx.Response(200),
    }
    result = smoke_models.probe_structured(_client(routes), CHAT, "herhealth", {"type": "object"})
    assert not result.ok
    assert result.detail.startswith("FAIL")


def test_structured_probe_crash_when_the_engine_is_gone_afterwards() -> None:
    routes = {("POST", 8002, "/v1/chat/completions"): _json({"error": "engine dead"}, status=500)}
    result = smoke_models.probe_structured(_client(routes), CHAT, "herhealth", {"type": "object"})
    assert not result.ok
    assert result.detail.startswith("CRASH")


def test_main_exits_zero_when_everything_answers(capsys: pytest.CaptureFixture[str]) -> None:
    transport = _transport(_healthy_routes())
    code = smoke_models.main(["--env", str(SERVE_ENV), "--skip-structured"], transport=transport)
    assert code == 0
    assert "FAIL" not in capsys.readouterr().out


def test_main_reports_every_check_when_one_service_is_down(
    capsys: pytest.CaptureFixture[str],
) -> None:
    routes = _healthy_routes()
    del routes[("GET", 8004, "/health")]
    del routes[("POST", 8004, "/v1/rerank")]
    transport = _transport(routes)
    code = smoke_models.main(["--env", str(SERVE_ENV), "--skip-structured"], transport=transport)
    out = capsys.readouterr().out
    assert code == 1
    assert out.count("rerank") >= 4  # health plus three languages, all reported
    assert "ok    chat en" in out  # the healthy services were still checked


def test_main_fails_on_a_missing_env_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        smoke_models.main(["--env", str(tmp_path / "absent.env")])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest scripts/tests/test_smoke_models.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'smoke_models'`.

- [ ] **Step 3: Write the smoke script**

`scripts/smoke_models.py`:

```python
"""Acceptance check for the three vLLM processes.

    uv run python scripts/smoke_models.py
    uv run python scripts/smoke_models.py --skip-structured

Exit code 0 means every check passed. The structured-output probe is reported
separately and never changes the exit code: it exists to find out whether
schema-constrained decoding works on this hardware, where it crashed the
engine on 2026-09-08.

The fixture sentences are deliberately not about health. They test that the
models answer, embed and rank in three languages, and assert nothing clinical.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = REPO_ROOT / "infra" / "model" / "serve.conf"
HOST = "127.0.0.1"

#: Generation on these cards is slow; the first call also compiles LoRA kernels.
TIMEOUT_SECONDS = 300.0

CHAT_PROMPTS = {
    "en": "Answer in one short sentence: what is a calendar used for?",
    "fr": "Réponds en une phrase courte : à quoi sert un calendrier ?",
    "ar": "أجب بجملة قصيرة واحدة: ما فائدة التقويم؟",
}

#: language -> (query, relevant passage, irrelevant passage)
RERANK_CASES = {
    "en": (
        "What time does the library open?",
        "The library opens at nine every morning.",
        "Tomatoes grow best in warm weather.",
    ),
    "fr": (
        "À quelle heure ouvre la bibliothèque ?",
        "La bibliothèque ouvre à neuf heures chaque matin.",
        "Les tomates poussent mieux par temps chaud.",
    ),
    "ar": (
        "متى تفتح المكتبة؟",
        "تفتح المكتبة في الساعة التاسعة كل صباح.",
        "تنمو الطماطم بشكل أفضل في الطقس الدافئ.",
    ),
}

_FAILURES = (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def load_env(path: Path) -> dict[str, str]:
    """Read a KEY=value file, skipping blank lines and comments."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def looks_corrupted(text: str) -> bool:
    """True for an empty reply or one that is mostly ``!``.

    A run of ``!`` is token 0, which the sampler emits when the logits are
    NaN. See docs/runbooks/uni-server-vllm.md section 0.1.
    """
    compact = "".join(text.split())
    if not compact:
        return True
    return compact.count("!") / len(compact) > 0.5


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return str(error) or type(error).__name__
    return f"unexpected response ({type(error).__name__}: {error})"


def _guarded(name: str, body: Callable[[], CheckResult]) -> CheckResult:
    """Run one check and turn any transport or shape error into a failed
    result, so one dead service never hides the state of the others."""
    try:
        return body()
    except _FAILURES as error:
        return CheckResult(name, False, _describe(error))


def check_health(client: httpx.Client, base_url: str) -> CheckResult:
    name = f"health {base_url}"

    def body() -> CheckResult:
        client.get(f"{base_url}/health").raise_for_status()
        return CheckResult(name, True, "answering")

    return _guarded(name, body)


def check_models(client: httpx.Client, base_url: str, expected: Sequence[str]) -> CheckResult:
    name = f"models {base_url}"

    def body() -> CheckResult:
        response = client.get(f"{base_url}/v1/models")
        response.raise_for_status()
        served = {entry["id"] for entry in response.json()["data"]}
        missing = [model for model in expected if model not in served]
        if missing:
            return CheckResult(name, False, f"not served: {', '.join(missing)}")
        return CheckResult(name, True, ", ".join(expected))

    return _guarded(name, body)


def _chat(client: httpx.Client, base_url: str, payload: dict[str, object]) -> str:
    response = client.post(f"{base_url}/v1/chat/completions", json=payload)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("message content is not text")
    return content


def check_chat(
    client: httpx.Client, base_url: str, model: str, language: str, prompt: str
) -> CheckResult:
    name = f"chat {language}"

    def body() -> CheckResult:
        reply = _chat(
            client,
            base_url,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 64,
                "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        if looks_corrupted(reply):
            return CheckResult(name, False, f"corrupted or empty reply: {reply[:40]!r}")
        return CheckResult(name, True, reply.strip()[:80])

    return _guarded(name, body)


def check_embeddings(
    client: httpx.Client, base_url: str, model: str, texts: Sequence[str]
) -> CheckResult:
    name = "embeddings"

    def body() -> CheckResult:
        response = client.post(
            f"{base_url}/v1/embeddings", json={"model": model, "input": list(texts)}
        )
        response.raise_for_status()
        vectors = [entry["embedding"] for entry in response.json()["data"]]
        if len(vectors) != len(texts):
            return CheckResult(name, False, f"{len(vectors)} vectors for {len(texts)} inputs")
        widths = {len(vector) for vector in vectors}
        if len(widths) != 1 or 0 in widths:
            return CheckResult(name, False, f"widths differ or are empty: {sorted(widths)}")
        if not all(math.isfinite(value) for vector in vectors for value in vector):
            return CheckResult(name, False, "non-finite value in an embedding")
        return CheckResult(name, True, f"width={widths.pop()}")

    return _guarded(name, body)


def check_rerank(
    client: httpx.Client,
    base_url: str,
    model: str,
    language: str,
    query: str,
    relevant: str,
    irrelevant: str,
) -> CheckResult:
    name = f"rerank {language}"

    def body() -> CheckResult:
        response = client.post(
            f"{base_url}/v1/rerank",
            json={"model": model, "query": query, "documents": [relevant, irrelevant]},
        )
        response.raise_for_status()
        scores = {entry["index"]: float(entry["relevance_score"]) for entry in response.json()["results"]}
        detail = f"relevant={scores[0]:.4g} irrelevant={scores[1]:.4g}"
        return CheckResult(name, scores[0] > scores[1], detail)

    return _guarded(name, body)


def probe_structured(
    client: httpx.Client, base_url: str, model: str, schema: dict[str, object]
) -> CheckResult:
    """One schema-constrained request. PASS, FAIL or CRASH.

    CRASH means the engine stopped answering ``/health`` afterwards, which is
    the 2026-09-08 failure. Restart chat before doing anything else.
    """
    name = "structured-output"
    outcome = "FAIL"
    detail = ""
    try:
        reply = _chat(
            client,
            base_url,
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Reply only with JSON that matches the schema."},
                    {"role": "user", "content": "I would like to ask a question."},
                ],
                "max_tokens": 512,
                "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "triage_decision", "schema": schema},
                },
            },
        )
        parsed = json.loads(reply)
        if isinstance(parsed, dict):
            outcome, detail = "PASS", f"keys: {', '.join(sorted(parsed))}"
        else:
            detail = "reply was JSON but not an object"
    except _FAILURES as error:
        detail = _describe(error)
    if not check_health(client, base_url).ok:
        outcome = "CRASH"
        detail = f"engine no longer answers /health ({detail})"
    return CheckResult(name, outcome == "PASS", f"{outcome}: {detail}")


def _decision_schema() -> dict[str, object]:
    from herhealth_contracts.decision import TriageDecision

    return TriageDecision.model_json_schema()


def _print(result: CheckResult) -> None:
    print(f"{'ok  ' if result.ok else 'FAIL'}  {result.name}  {result.detail}")


def main(
    argv: Sequence[str] | None = None, *, transport: httpx.BaseTransport | None = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--skip-structured", action="store_true")
    args = parser.parse_args(argv)
    if not args.env.is_file():
        parser.error(f"no env file at {args.env}")
    env = load_env(args.env)

    chat = f"http://{HOST}:{env['CHAT_PORT']}"
    embed = f"http://{HOST}:{env['EMBED_PORT']}"
    rerank = f"http://{HOST}:{env['RERANK_PORT']}"
    adapter = env["CHAT_ADAPTER_NAME"]

    results: list[CheckResult] = []
    with httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        for label, url in (("chat", chat), ("embed", embed), ("rerank", rerank)):
            health = check_health(client, url)
            results.append(CheckResult(f"health {label}", health.ok, health.detail))
        results.append(check_models(client, chat, [env["CHAT_MODEL"], adapter]))
        for language, prompt in CHAT_PROMPTS.items():
            results.append(check_chat(client, chat, adapter, language, prompt))
        results.append(
            check_embeddings(
                client, embed, env["EMBED_SERVED_NAME"], [case[1] for case in RERANK_CASES.values()]
            )
        )
        for language, (query, relevant, irrelevant) in RERANK_CASES.items():
            results.append(
                check_rerank(
                    client, rerank, env["RERANK_SERVED_NAME"], language, query, relevant, irrelevant
                )
            )
        for result in results:
            _print(result)
        if not args.skip_structured:
            print("--- structured-output probe (does not affect the exit code)")
            _print(probe_structured(client, chat, adapter, _decision_schema()))

    failed = [result for result in results if not result.ok]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest scripts/tests/test_smoke_models.py -q`
Expected: `24 passed` (seven of them are the `test_looks_corrupted` cases).

- [ ] **Step 5: Lint and run the whole script suite**

Run: `uv run ruff check scripts/smoke_models.py scripts/tests && uv run ruff format --check scripts/smoke_models.py scripts/tests && uv run pytest scripts/tests -q`
Expected: no ruff errors, and `54 passed`. If `ruff format --check` reports files, run `uv run ruff format scripts/smoke_models.py scripts/tests` and re-run the tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_models.py scripts/tests/test_smoke_models.py
git commit -m "feat(infra): add a smoke test for the three vLLM endpoints"
```

---

### Task 5: Bring the stack up on the campus box

This task changes the machine, not just the repo. **Stop and get the repo owner's explicit go-ahead before Step 1 and before Step 2.**

**Files:**
- Modify: `infra/model/serve.conf` (the two `UNPINNED` values)
- Modify: `scripts/tests/test_serve_env.py` (tighten the revision test)

**Interfaces:**
- Consumes: `scripts/serve-models.sh` (Task 2), `scripts/smoke_models.py` (Task 4).
- Produces: three running processes; real commits in `EMBED_REVISION` and `RERANK_REVISION`; a recorded smoke result and structured-output outcome for Task 6.

- [ ] **Step 1: Free disk space (needs go-ahead: deletes 3.7 GB)**

```bash
df -h /home/jovyan | tail -1
du -sh /home/jovyan/.cache/pip
rm -rf /home/jovyan/.cache/pip
df -h /home/jovyan | tail -1
```

Expected: free space on `/home/jovyan` rises from about 15 GB to about 18 GB. If it is below 17 GB afterwards, stop and report; the two models need about 16 GB.

- [ ] **Step 2: Download the two models (needs go-ahead: network, about 16 GB)**

```bash
export HF_HOME=/home/jovyan/.cache/huggingface
/home/jovyan/herhealthgpt-venv/bin/hf download Qwen/Qwen3-Embedding-4B
df -h /home/jovyan | tail -1
```

Expected: the download completes and at least 9 GB remains free. If less remains, stop and report before the second download.

```bash
/home/jovyan/herhealthgpt-venv/bin/hf download Qwen/Qwen3-Reranker-4B
df -h /home/jovyan | tail -1
```

If either download asks for a token or returns 401/403, stop and report: the spec assumed both repositories are public.

- [ ] **Step 3: Pin the revisions**

```bash
ls /home/jovyan/.cache/huggingface/hub/models--Qwen--Qwen3-Embedding-4B/snapshots/
ls /home/jovyan/.cache/huggingface/hub/models--Qwen--Qwen3-Reranker-4B/snapshots/
```

Each prints one 40-character commit id. In `infra/model/serve.conf`, replace `EMBED_REVISION=UNPINNED` and `RERANK_REVISION=UNPINNED` with those two ids.

Then, in `scripts/tests/test_serve_env.py`, replace `test_chat_revision_is_pinned` and `test_other_revisions_are_pinned_or_explicitly_unpinned` with one stricter test:

```python
def test_every_revision_is_pinned() -> None:
    # The retrieval index is only valid against the exact embedding weights
    # that built it, so an unpinned revision is a defect.
    env = parse_env(SERVE_ENV)
    for service in SERVICES:
        key = f"{service.upper()}_REVISION"
        assert SHA.match(env[key]), f"{key} is not a 40-character commit id"
```

Run: `uv run pytest scripts/tests -q`
Expected: `53 passed`.

- [ ] **Step 4: Start the three processes**

```bash
bash scripts/serve-models.sh clean
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
bash scripts/serve-models.sh start all
```

Expected: `clean` leaves every GPU at about 0 MiB, and `start` prints three `started (pid …)` lines.

Wait for all three, up to 20 minutes:

```bash
timeout 1200 bash -c 'for p in 8002 8003 8004; do until curl -sf --max-time 2 "http://127.0.0.1:$p/health" >/dev/null; do sleep 10; done; echo "$p up"; done'
bash scripts/serve-models.sh check
```

Expected: `8002 up`, `8003 up`, `8004 up`, and `check` shows `process=up(...) endpoint=answering` for all three.

If one never comes up, read its log: `tail -60 /home/jovyan/herhealth-serve/<service>.log`.
- Chat: compare against `docs/runbooks/uni-server-vllm.md` sections 0.1 to 0.3.
- Reranker rejecting its overrides: the keys are read in `/home/jovyan/herhealthgpt-venv/lib/python3.12/site-packages/vllm/model_executor/models/config.py`, class `Qwen3ForSequenceClassificationConfig`. Report the log lines to the repo owner; do not guess at other values.

- [ ] **Step 5: Confirm the chat window and text-only mode from the log**

```bash
grep -E 'KV cache size|text-only|Model loading took' /home/jovyan/herhealth-serve/chat.log
```

Expected: a line containing `Maximum concurrency for 32,768 tokens per request` with a value near `5.6x`, and `running in text-only mode`.

- [ ] **Step 6: Run the smoke test without the probe**

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
uv run python scripts/smoke_models.py --skip-structured; echo "exit=$?"
```

Expected: eleven `ok` lines, `11 of 11 checks passed`, `exit=0`. Save the full output for Task 6. Note the `width=` value on the embeddings line; step 2 of the project needs it.

If a `rerank` line fails with the relevant score lower than the irrelevant one while the process is healthy, the scoring template is the suspect. Report it; do not edit the template by trial and error.

- [ ] **Step 7: Run the structured-output probe**

```bash
uv run python scripts/smoke_models.py; echo "exit=$?"
bash scripts/serve-models.sh check
```

Record the probe line (`PASS`, `FAIL` or `CRASH`) for Task 6. If it is `CRASH`, or `check` shows chat as down or silent, restore chat and confirm it:

```bash
bash scripts/serve-models.sh clean
bash scripts/serve-models.sh start all
timeout 1200 bash -c 'for p in 8002 8003 8004; do until curl -sf --max-time 2 "http://127.0.0.1:$p/health" >/dev/null; do sleep 10; done; echo "$p up"; done'
uv run python scripts/smoke_models.py --skip-structured; echo "exit=$?"
```

- [ ] **Step 8: Commit**

```bash
git add infra/model/serve.conf scripts/tests/test_serve_env.py
git commit -m "chore(infra): pin the embedding and reranker revisions"
```

---

### Task 6: Replace the old launcher and update the docs

**Files:**
- Delete: `scripts/setup-uni-vllm.sh`
- Modify: `docs/runbooks/uni-server-vllm.md`
- Modify: `README.md` (the campus-serve section near line 680)

**Interfaces:**
- Consumes: the smoke output and probe result recorded in Task 5.
- Produces: nothing other tasks rely on.

- [ ] **Step 1: Delete the old launcher**

```bash
git rm scripts/setup-uni-vllm.sh
```

If commits were declined, use `rm scripts/setup-uni-vllm.sh` instead.

- [ ] **Step 2: Add the new layout to the top of the runbook**

In `docs/runbooks/uni-server-vllm.md`, insert this section immediately before the line `## 0. Start the server (copy-paste)`. Replace the two fenced result blocks with the real output saved in Task 5, verbatim.

````markdown
## Current layout: three processes (since 2026-10-11)

Sections 0 to 5 below describe the single-process serve as it ran before
2026-10-11. They are kept for their diagnosis notes (0.1 and 0.2 still
apply in full). The commands in this section replace theirs.

| Process | Model | GPUs | Port |
|---|---|---|---|
| chat | `Qwen/Qwen3.5-9B` + `herhealth` adapter | 0, 1 | 8002 |
| embed | `Qwen/Qwen3-Embedding-4B` | 2 | 8003 |
| rerank | `Qwen/Qwen3-Reranker-4B` | 3 | 8004 |

Every value comes from `infra/model/serve.conf`. The adapter is read from
`herhealth-lora-v2/` in the repo root.

```bash
bash scripts/serve-models.sh clean        # stop everything, free the GPUs
bash scripts/serve-models.sh start all    # or: start chat | embed | rerank
bash scripts/serve-models.sh check        # state of all three
bash scripts/serve-models.sh stop all
```

Logs and pid files are in `/home/jovyan/herhealth-serve/`. The launcher
never downloads; if a model is missing it prints the command that fetches it.

Acceptance test, with the three processes up:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
uv run python scripts/smoke_models.py --skip-structured
```

Last run on this box:

```
<paste the output of Task 5 Step 6 here>
```

Schema-constrained decoding, which crashed the engine on 2026-09-08, was
retested with `uv run python scripts/smoke_models.py`. Result:

```
<paste the structured-output line of Task 5 Step 7 here>
```

On a host with Docker and the NVIDIA container toolkit, the same three
processes start with:

```bash
docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf up -d
```

That file is validated on this box with `docker compose config` only. This
pod has no Docker daemon, so it has never been started here.

After a pod restart the processes are gone and nothing restarts them:
run `start all` again. Keep a JupyterLab tab open while testing, or idle
culling will stop the pod.
````

- [ ] **Step 3: Fix the three references to the old script in the runbook**

Replace:

```markdown
**If the venv or adapter directory is missing**, run
`bash scripts/setup-uni-vllm.sh` from a clone on the VM (§4–§5). Keep the
JupyterLab tab open — idle culling is what "I closed the machine" usually is.
```

with:

```markdown
**If a model or the adapter is missing**, `bash scripts/serve-models.sh check`
says which, and `start` prints the command that fetches it. Keep the
JupyterLab tab open — idle culling is what "I closed the machine" usually is.
```

Replace:

```markdown
`scripts/setup-uni-vllm.sh` in this repo does §2–§4 idempotently — after a
wipe, re-running it skips whatever survived. The prose below is what it does
and why, so you can debug it when a step fails.
```

with:

```markdown
`scripts/serve-models.sh` starts and stops the processes. It does not install
vLLM or download models; §2–§4 below are the manual steps for that after a
wipe, and why each one is needed.
```

In the troubleshooting table, replace the cell text
``Server culled, container reset. Re-run `scripts/setup-uni-vllm.sh`; it skips whatever survived.``
with
``Server culled, container reset. Run `bash scripts/serve-models.sh check`, restore whatever it reports missing (§2–§4), then `start all`.``

- [ ] **Step 4: Record that the 8192 window is superseded**

In the same runbook, insert this paragraph immediately before the line `## 1. Check what the VM gives you`:

```markdown
**Superseded 2026-10-11: the window is now 32,768.** vLLM's log of the
2026-09-17 serve shows 3.98 GiB per GPU left for the token cache, holding
183,947 tokens, so a 32,768 window still fits 5.6 full-length requests at
once. That depends on `--enforce-eager`; with CUDA graphs enabled the cache
shrinks to 78,568 tokens. The reasoning above for why 4096 is too small
still holds.
```

- [ ] **Step 5: Update the README**

In `README.md`, replace the table row

```markdown
| `--max-model-len 8192` | The triage prompt is ~3,200–3,600 tokens before retrieval; 4096 leaves no room to generate (runbook §0.3) |
```

with

```markdown
| `--max-model-len 32768` | Set in `infra/model/serve.conf`. The token cache holds 183,947 tokens with `--enforce-eager`, so this fits 5.6 full-length requests (runbook §0.3) |
```

and replace

````markdown
First-time install after a wipe:

```bash
bash scripts/setup-uni-vllm.sh --clean
bash scripts/setup-uni-vllm.sh
bash scripts/setup-uni-vllm.sh --check
```
````

with

````markdown
Start the chat, embedding and reranker processes (ports 8002, 8003, 8004):

```bash
bash scripts/serve-models.sh clean
bash scripts/serve-models.sh start all
bash scripts/serve-models.sh check
```

After a wipe, restore vLLM and the models first: `docs/runbooks/uni-server-vllm.md`.
````

- [ ] **Step 6: Verify nothing still points at the old script**

Run: `grep -rn 'setup-uni-vllm' --exclude-dir=.git --exclude-dir=graphify-out --exclude-dir=node_modules . | grep -v 'docs/superpowers/'`
Expected: no output. (`docs/superpowers/` is excluded because the spec and this plan name the old script on purpose.)

- [ ] **Step 7: Run every check**

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
uv run pytest scripts/tests -q
uv run ruff check scripts/smoke_models.py scripts/tests
python3 scripts/check_repo_hygiene.py
docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf config --quiet && echo valid
```

Expected: `53 passed`, no ruff errors, the hygiene check passes, and `valid`.

- [ ] **Step 8: Commit**

```bash
git add -A scripts/setup-uni-vllm.sh docs/runbooks/uni-server-vllm.md README.md
git commit -m "docs(infra): point the campus runbook at the three-process launcher"
```

---

## Done when

- `bash scripts/serve-models.sh check` shows all three processes up and answering on this box.
- `uv run python scripts/smoke_models.py --skip-structured` exits 0.
- The structured-output probe result is written into the runbook.
- `docker compose ... config --quiet` succeeds.
- `infra/model/serve.conf` carries three 40-character revisions.
- `scripts/setup-uni-vllm.sh` is gone and nothing outside `docs/superpowers/` refers to it.
