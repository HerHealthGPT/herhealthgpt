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

# An optional bearer key for all three servers, needed as soon as anything
# outside this machine can reach them. It lives in an untracked file and is
# handed to vLLM through VLLM_API_KEY, never as an argument, so it appears in
# neither `print`, the process list nor the logs. No file, or an empty value,
# means no key is required, which is the local default.
MODELS_KEY_FILE="${MODELS_KEY_FILE:-$REPO_ROOT/infra/envs/models.env}"
MODELS_API_KEY=""
if [ -f "$MODELS_KEY_FILE" ]; then
  MODELS_API_KEY="$(sed -n 's/^HERHEALTH_MODELS_API_KEY=//p' "$MODELS_KEY_FILE" | tail -1)"
fi
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

# A pid file holds "<pid> <start time>". The start time (field 22 of
# /proc/<pid>/stat, in clock ticks since boot) is what tells our process from
# an unrelated one that was later given the same pid: the files live on the
# persistent volume, and after a pod restart their numbers are reused within
# minutes. Without it, `stop` and `clean` would kill a stranger.
proc_start() {
  # Everything up to the last ")" is the command name, which may hold spaces.
  sed 's/^.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'
}

pid_of() { awk 'NR==1 {print $1}' "$(pid_file "$1")" 2>/dev/null; }

running() {
  local file pid start
  file="$(pid_file "$1")"
  [ -f "$file" ] || return 1
  read -r pid start < "$file" || true
  [ -n "${pid:-}" ] && [ -n "${start:-}" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [ "$(proc_start "$pid")" = "$start" ]
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
    echo "$svc: already running (pid $(pid_of "$svc")) - stop it first" >&2
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
    VLLM_API_KEY="$MODELS_API_KEY" \
    TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-$HOME/.cache/triton}" \
    "$VLLM_BIN" "${args[@]}" > "$RUN_DIR/$svc.log" 2>&1 < /dev/null &
  echo "$! $(proc_start $!)" > "$(pid_file "$svc")"
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
  pid="$(pid_of "$svc")"
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
      state="up(pid $(pid_of "$svc"))"
    else
      state="down"
    fi
    if curl -sf --max-time 2 -H "Authorization: Bearer ${MODELS_API_KEY:-none}" \
      "http://$HOST:$port/v1/models" >/dev/null 2>&1; then
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
