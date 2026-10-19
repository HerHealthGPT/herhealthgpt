#!/usr/bin/env bash
# Publish the campus model servers to production through Cloudflare quick
# tunnels, and tell production where they are.
#
#   scripts/tunnel-models.sh start     open a tunnel to the chat and embedding servers
#   scripts/tunnel-models.sh status    show the tunnels and their public addresses
#   scripts/tunnel-models.sh publish   store the addresses and the key in GitHub, then redeploy
#   scripts/tunnel-models.sh stop      close the tunnels
#   scripts/tunnel-models.sh watch     keep them up and published (runs until stopped)
#   scripts/tunnel-models.sh unwatch   stop a running watch
#
# Why it exists: the pod accepts no inbound connections, so the link has to be
# opened from this side. A quick tunnel gives each server a public HTTPS
# address that CHANGES every time the tunnel restarts, which is why `publish`
# has to be run again after every `start`.
#
# `watch` does that unattended. A tunnel survives network drops by itself
# (cloudflared reconnects); what breaks the link is the process dying, after
# which the address is gone. Every WATCH_INTERVAL seconds `watch` checks each
# tunnel from the public side with the key, restarts one whose process has
# died or that failed WATCH_FAILURES checks in a row (one failure is usually a
# DNS hiccup), and publishes again whenever an address no longer matches what
# GitHub holds, which redeploys production. Start it with
#   nohup scripts/tunnel-models.sh watch >/dev/null 2>&1 &
# It cannot survive the pod restarting; neither can the model servers.
#
# What it exposes: the two servers become reachable from the internet, guarded
# only by the bearer key in infra/envs/models.env. `start` refuses to run
# without that key. Cloudflare cuts a request off at 100 seconds.
#
# The reranker is not tunnelled: it is off by default (HERHEALTH_RERANK).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
set -a; . "$REPO_ROOT/infra/model/serve.conf"; set +a

RUN_DIR="${RUN_DIR:-/home/jovyan/herhealth-serve}"
CLOUDFLARED="${CLOUDFLARED:-$RUN_DIR/bin/cloudflared}"
KEY_FILE="${MODELS_KEY_FILE:-$REPO_ROOT/infra/envs/models.env}"
SERVICES=(chat embed)

port_of() { local name="${1^^}_PORT"; printf '%s' "${!name}"; }
log_of() { printf '%s/tunnel-%s.log' "$RUN_DIR" "$1"; }
pid_of() { printf '%s/tunnel-%s.pid' "$RUN_DIR" "$1"; }
url_of() { { grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$(log_of "$1")" 2>/dev/null || true; } | tail -1; }
alive() { [ -f "$(pid_of "$1")" ] && kill -0 "$(cat "$(pid_of "$1")")" 2>/dev/null; }
WATCH_PID="$RUN_DIR/tunnel-watch.pid"
WATCH_LOG="$RUN_DIR/tunnel-watch.log"

models_key() {
  [ -f "$KEY_FILE" ] && sed -n 's/^HERHEALTH_MODELS_API_KEY=//p' "$KEY_FILE" | tail -1
}

open_tunnel() {
  : > "$(log_of "$1")"
  nohup "$CLOUDFLARED" tunnel --no-autoupdate --url "http://127.0.0.1:$(port_of "$1")" \
    > "$(log_of "$1")" 2>&1 < /dev/null &
  echo "$!" > "$(pid_of "$1")"
}

start() {
  local key svc code
  key="$(models_key || true)"
  if [ -z "$key" ]; then
    echo "refusing: no key in $KEY_FILE. A tunnel to servers without a key is an open endpoint." >&2
    exit 1
  fi
  [ -x "$CLOUDFLARED" ] || { echo "cloudflared not found at $CLOUDFLARED" >&2; exit 1; }
  for svc in "${SERVICES[@]}"; do
    # The server must already refuse a request that has no key.
    code="$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "http://127.0.0.1:$(port_of "$svc")/v1/models" || true)"
    if [ "$code" != 401 ]; then
      echo "refusing: the $svc server answered $code without a key (expected 401). Restart it with scripts/serve-models.sh." >&2
      exit 1
    fi
    if alive "$svc"; then
      echo "$svc: tunnel already running"
      continue
    fi
    open_tunnel "$svc"
  done
  for svc in "${SERVICES[@]}"; do
    for _ in $(seq 1 30); do
      [ -n "$(url_of "$svc")" ] && break
      sleep 1
    done
    echo "$svc: $(url_of "$svc" || true)"
  done
  echo "now run: scripts/tunnel-models.sh publish"
}

status() {
  local svc
  for svc in "${SERVICES[@]}"; do
    if alive "$svc"; then
      echo "$svc: up, $(url_of "$svc")"
    else
      echo "$svc: down"
    fi
  done
}

stop() {
  local svc
  for svc in "${SERVICES[@]}"; do
    if alive "$svc"; then
      kill "$(cat "$(pid_of "$svc")")" || true
      echo "$svc: tunnel stopped"
    fi
    rm -f "$(pid_of "$svc")"
  done
}

publish() {
  local svc chat embed key url code
  for svc in "${SERVICES[@]}"; do
    alive "$svc" || { echo "the $svc tunnel is not running; run start first" >&2; exit 1; }
  done
  chat="$(url_of chat)"; embed="$(url_of embed)"; key="$(models_key)"
  # Checked from the public side before production is pointed at it.
  for url in "$chat" "$embed"; do
    code="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' -H "Authorization: Bearer $key" "$url/v1/models" || true)"
    [ "$code" = 200 ] || { echo "$url answered $code with the key; not publishing" >&2; exit 1; }
  done
  gh variable set MODELS_CHAT_URL --body "$chat"
  gh variable set MODELS_EMBED_URL --body "$embed"
  printf '%s' "$key" | gh secret set MODELS_API_KEY
  echo "stored. Redeploying main so production picks them up."
  gh workflow run deploy --ref main
}

# 200 from the public address with the key, or not.
answers() {
  local url code
  url="$(url_of "$1")"
  [ -n "$url" ] || return 1
  code="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' \
    -H "Authorization: Bearer $(models_key)" "$url/v1/models" || true)"
  [ "$code" = 200 ]
}

published() { gh variable list --json name,value -q ".[] | select(.name == \"$1\") | .value"; }

watch() {
  local interval="${WATCH_INTERVAL:-300}" limit="${WATCH_FAILURES:-3}" svc url
  declare -A failures=()
  if [ -f "$WATCH_PID" ] && kill -0 "$(cat "$WATCH_PID")" 2>/dev/null; then
    echo "already watching (pid $(cat "$WATCH_PID"))" >&2
    exit 1
  fi
  echo "$$" > "$WATCH_PID"
  trap 'rm -f "$WATCH_PID"' EXIT
  exec >> "$WATCH_LOG" 2>&1
  echo "$(date -u +%FT%TZ) watching every ${interval}s"
  while true; do
    for svc in "${SERVICES[@]}"; do
      if ! alive "$svc"; then
        echo "$(date -u +%FT%TZ) $svc: process gone, reopening"
        open_tunnel "$svc"
        failures[$svc]=0
      elif answers "$svc"; then
        failures[$svc]=0
      else
        failures[$svc]=$(( ${failures[$svc]:-0} + 1 ))
        echo "$(date -u +%FT%TZ) $svc: check failed (${failures[$svc]}/$limit)"
        if [ "${failures[$svc]}" -ge "$limit" ]; then
          echo "$(date -u +%FT%TZ) $svc: reopening"
          kill "$(cat "$(pid_of "$svc")")" 2>/dev/null || true
          open_tunnel "$svc"
          failures[$svc]=0
        fi
      fi
    done
    sleep 20  # a new tunnel's address takes a few seconds to appear and resolve
    url="$(url_of chat)|$(url_of embed)"
    if [ "$url" != "$(published MODELS_CHAT_URL)|$(published MODELS_EMBED_URL)" ]; then
      echo "$(date -u +%FT%TZ) addresses changed, publishing"
      # A failed publish (new address not resolvable yet) is retried next round.
      ( publish ) || echo "$(date -u +%FT%TZ) publish failed; retrying next round"
    fi
    sleep "$interval"
  done
}

unwatch() {
  if [ -f "$WATCH_PID" ] && kill "$(cat "$WATCH_PID")" 2>/dev/null; then
    echo "watch stopped"
  else
    echo "not watching"
  fi
  rm -f "$WATCH_PID"
}

case "${1:-}" in
  start|status|stop|publish|watch|unwatch) "$1" ;;
  *) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
