#!/usr/bin/env bash
# Re-provision the fine-tuned model on the university JupyterHub VM after a wipe.
#
# The container filesystem resets every time the server is culled or restarted;
# only the home volume survives. This script puts the venv and the ~20 GB of
# weights on that volume and is safe to re-run — each step checks first and
# skips what is already there, so after a wipe it restores whatever is missing
# and nothing else.
#
#   bash setup-uni-vllm.sh          # install + download + start
#   bash setup-uni-vllm.sh --check  # report state, change nothing
#   bash setup-uni-vllm.sh --stop   # stop the server
#   bash setup-uni-vllm.sh --clean  # kill leftover vLLM (any pid) and free the GPU
#
# Full context, including how to reach the port from your laptop and how to
# point the backend at it: docs/runbooks/uni-server-vllm.md
#
# The adapter is PHRASING-ONLY. It must not choose an action code or stand in
# for a triage decision — see docs/runbooks/dev-vllm-lora-endpoint.md §6.

set -euo pipefail

PERSIST="${PERSIST:-/home/jovyan}"          # override if home is not the volume
# The 2026-09-09 working session ran from herhealthgpt-venv; vllm-env is the
# older name and is kept as a fallback so an existing box still resolves.
if [ -x "$PERSIST/herhealthgpt-venv/bin/vllm" ]; then
  VENV="${VENV:-$PERSIST/herhealthgpt-venv}"
else
  VENV="${VENV:-$PERSIST/vllm-env}"
fi
export HF_HOME="${HF_HOME:-$PERSIST/.cache/huggingface}"
BASE_MODEL="Qwen/Qwen3.5-9B"
ADAPTER_HF="herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2"
ADAPTER_LOCAL="$PERSIST/models/herhealth-lora-v2"   # what 2026-09-06 actually served
ADAPTER_NAME="herhealth"                     # must match HERHEALTH_VLLM_MODEL
PORT="${PORT:-8000}"                         # verified bind; 8002 was empty
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"       # 4096 is too small for the triage prompt
LOG="$PERSIST/vllm.log"
PIDFILE="$PERSIST/vllm.pid"

say() { printf '\n== %s\n' "$*"; }

running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

check() {
  say "state"
  echo "persist dir : $PERSIST ($(df -h --output=avail "$PERSIST" | tail -1 | tr -d ' ') free)"
  echo "HF_HOME     : $HF_HOME"
  echo "venv        : $([ -x "$VENV/bin/vllm" ] && echo present || echo MISSING)"
  echo "hf token    : $([ -f "$HF_HOME/token" ] && echo present || echo MISSING)"
  echo "base weights: $(du -sh "$HF_HOME/hub/models--Qwen--Qwen3.5-9B" 2>/dev/null | cut -f1 || echo MISSING)"
  echo "adapter     : $(du -sh "$ADAPTER_LOCAL" 2>/dev/null | cut -f1 \
    || du -sh "$HF_HOME/hub/models--herhealthgpt--qwen3.5-9b-herhealth-enfrar-lora-v2" 2>/dev/null | cut -f1 \
    || echo MISSING)"
  echo "server      : $(running && echo "up (pid $(cat "$PIDFILE"))" || echo down)"
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 \
    && echo "endpoint    : answering on 127.0.0.1:$PORT" \
    || echo "endpoint    : not answering on 127.0.0.1:$PORT"
}

stop() {
  if running; then
    kill "$(cat "$PIDFILE")" || true
    rm -f "$PIDFILE"
    echo "stopped pidfile process"
  else
    echo "no pidfile process"
  fi
}

clean() {
  stop
  if pgrep -f 'vllm serve' >/dev/null 2>&1; then
    pkill -f 'vllm serve' || true
    sleep 2
    pkill -9 -f 'vllm serve' 2>/dev/null || true
    echo "killed leftover vllm serve"
  fi
  pkill -9 -f 'VLLM::' 2>/dev/null || true
  # Stale GPU peer-access probe. Cheap to rebuild, and a wrong entry here is
  # what let custom all-reduce stay enabled over a broken P2P link — the cause
  # of both the !!!!!!! output and the 23-hour startup deadlock.
  # See docs/runbooks/uni-server-vllm.md section 0.1.
  rm -rf "$HOME/.cache/vllm"
  nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || true
}

adapter_arg() {
  if [ -d "$ADAPTER_LOCAL" ]; then
    echo "$ADAPTER_LOCAL"
  else
    echo "$ADAPTER_HF"
  fi
}

case "${1:-}" in
  --check) check; exit 0 ;;
  --stop)  stop;  exit 0 ;;
  --clean) clean; exit 0 ;;
esac

say "0. the GPU"
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv || {
  echo "No GPU visible. vLLM cannot serve this model here."
  echo "Use HERHEALTH_TRIAGE_MODE=openrouter instead — the app works without the adapter."
  exit 1
}

say "1. persistent HF_HOME"
mkdir -p "$HF_HOME"
grep -q 'HF_HOME' "$PERSIST/.bashrc" 2>/dev/null \
  || echo "export HF_HOME=$HF_HOME" >> "$PERSIST/.bashrc"
echo "HF_HOME=$HF_HOME (pinned in .bashrc so weights never land in the ephemeral layer)"

say "2. venv"
if [ -x "$VENV/bin/vllm" ]; then
  echo "already present — skipping (survived the wipe)"
else
  python -m venv "$VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --upgrade pip
  pip install vllm huggingface_hub
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

say "3. Hugging Face login"
if [ -f "$HF_HOME/token" ]; then
  echo "token present in HF_HOME — skipping"
else
  echo "The adapter repo is private. Paste a READ token for the herhealthgpt org."
  echo "It is stored only in $HF_HOME/token — never commit it or echo it into a notebook."
  huggingface-cli login
fi

say "4. weights (resumable; seconds when the cache survived)"
huggingface-cli download "$BASE_MODEL"
huggingface-cli download "$ADAPTER_HF"

say "5. serve"
if running; then
  echo "already running (pid $(cat "$PIDFILE")) — stop it first with --stop"
else
  # Local adapter path wins when present (2026-09-06 session).
  # --max-lora-rank 16 matches the adapter's r=16.
  # --disable-custom-all-reduce is MANDATORY here: P2P is broken on these A16s,
  #   and without it every TP all-reduce silently corrupts activations until the
  #   logits are NaN and the sampler emits token 0 ("!") forever. It also
  #   deadlocks startup. Runbook section 0.1.
  # --limit-mm-per-prompt needs BOTH image and video at 0 — the base is a
  #   multimodal hybrid, not a text model. Runbook section 0.2.
  # --max-model-len 8192 fits the triage prompt; 4096 does not. Section 0.3.
  # 127.0.0.1 is deliberate — reach it via the hub proxy or a tunnel, never by
  # exposing an unauthenticated model to the cluster network.
  LORA="$(adapter_arg)"
  echo "lora module : $ADAPTER_NAME=$LORA"
  nohup env \
    NCCL_P2P_DISABLE=1 \
    NCCL_IB_DISABLE=1 \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    NCCL_DEBUG=INFO \
    TRITON_CACHE_DIR="$PERSIST/.cache/triton" \
    HF_HOME="$HF_HOME" \
    vllm serve "$BASE_MODEL" \
    --enable-lora \
    --lora-modules "$ADAPTER_NAME=$LORA" \
    --max-lora-rank 16 \
    --max-model-len "$MAX_MODEL_LEN" \
    --tensor-parallel-size 2 \
    --disable-custom-all-reduce \
    --enforce-eager \
    --limit-mm-per-prompt '{"image":0,"video":0}' \
    --host 127.0.0.1 --port "$PORT" \
    > "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  echo "started (pid $(cat "$PIDFILE")), logging to $LOG"
fi

cat <<'NEXT'

Next:
  tail -f /home/jovyan/vllm.log        # wait for "Application startup complete."
  curl -s http://127.0.0.1:8000/v1/models   # must list the base model and "herhealth"

Then expose the port and point the backend at it —
docs/runbooks/uni-server-vllm.md §6 and §7.

Idle culling stops the JupyterHub server, and that kills this process. Keep a
JupyterLab tab open while testing.
NEXT
