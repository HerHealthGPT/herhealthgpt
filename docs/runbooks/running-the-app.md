---
status: runbook
---

# Runbook: running the whole app locally

Rewritten 2026-10-20 from how it actually runs. What runs and why:
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). The earlier version (OpenRouter,
the Base / Fine-tuned tabs, a retrieval service on `:8001`) described a stack
that no longer exists; it is in git history.

Two ways to run it:

| Setup | Models | Backend, frontend, database |
|---|---|---|
| **A. All on the campus pod** (how it runs today) | vLLM on the pod, `127.0.0.1:8002/8003` | on the pod too |
| **B. Laptop** | the pod's models through the tunnel addresses | on the laptop |

Either way the models run on the campus GPU server; nothing else needs a GPU.

## 0. The models (campus pod)

```bash
scripts/serve-models.sh start      # chat :8002 (base + adapter), embed :8003, rerank :8004
scripts/serve-models.sh check      # are they up, and do they require the key?
```

Settings are in `infra/model/serve.conf`; the bearer key is
`HERHEALTH_MODELS_API_KEY` in `infra/envs/models.env`. Details and
troubleshooting: [`uni-server-vllm.md`](uni-server-vllm.md). Check:

```bash
K=$(sed -n 's/^HERHEALTH_MODELS_API_KEY=//p' infra/envs/models.env)
curl -s -H "Authorization: Bearer $K" http://127.0.0.1:8002/v1/models   # Qwen/Qwen3.5-9B and herhealth
```

## 1. Configure `infra/envs/backend.env`

Copy `infra/envs/backend.env.example` and fill in. The ones that matter:

| Key | Setup A | Setup B |
|---|---|---|
| `HERHEALTH_DATABASE_URL` | `postgresql+psycopg://…@127.0.0.1:5432/herhealth` | same, on the laptop |
| `HERHEALTH_SESSION_SECRET` | `openssl rand -hex 32` | same |
| `HERHEALTH_TRIAGE_MODE` | `vllm` | `vllm` |
| `HERHEALTH_VLLM_URL` | `http://127.0.0.1:8002` | the `MODELS_CHAT_URL` tunnel address |
| `HERHEALTH_EMBEDDING_URL` | `http://127.0.0.1:8003` | the `MODELS_EMBED_URL` tunnel address |
| `HERHEALTH_VLLM_API_KEY` / `HERHEALTH_MODELS_API_KEY` | the models key | same |
| `HERHEALTH_INDEX_DIR` | `build/index` | `build/index` (copy it from the pod) |
| `HERHEALTH_UPLOAD_DIR` | e.g. `build/uploads` | same; empty switches kept files off |
| `HERHEALTH_COOKIE_SECURE` | `false` (plain HTTP) | `false` |
| `HERHEALTH_EMAIL_SENDER` | `console` (codes printed to the log) or `ses` | same |
| `HERHEALTH_COMPARISON_MODES` | `on` to show the mode choice in the chat | same |

Never print or commit this file; it holds secrets.

## 2. Database

The pod has no Docker. PostgreSQL 16 runs from a local install:

```bash
# Setup A (pod), once a session if it is not already running
pg_ctl -D /home/jovyan/herhealth-pgdata -o "-c listen_addresses=127.0.0.1 -c port=5432" -l /tmp/pg.log start
# Setup B (laptop with Docker)
make db-up
```

Then apply the migrations (`0001`–`0012`):

```bash
make migrate
```

## 3. Backend (`:8000`)

```bash
make serve          # loads backend.env; needs the api and retrieval extras
curl -s http://127.0.0.1:8000/health    # {"status":"ok"}
```

On the pod, `uv` needs its environment outside the repository:
`export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache`
before any `uv` or `make` command.

## 4. Frontend (`:3000`)

```bash
cd services/frontend
npm ci
npm run dev                 # or: npm run build && npx next start -p 3000
```

The frontend calls `/api/*`, which Next.js forwards to `BACKEND_URL`
(default `http://localhost:8000`). Open http://localhost:3000, register, and
use the code printed in the backend log if the email sender is `console`.

## 5. Check the whole path without a browser

```bash
make trace-turns CASE=T05-emergency-en   # one consultation through every layer
```

It builds the agent as the API does and prints the outcome; the full trace is
in `build/trace/`.

## Troubleshooting

| Symptom | Cause, fix |
|---|---|
| Chat answers "not configured" (503) | `HERHEALTH_TRIAGE_MODE` is not `vllm`, or the index is missing at `HERHEALTH_INDEX_DIR` (run `make index`) |
| 502 on every chat turn | the model servers or the tunnel are down: `serve-models.sh check`, `tunnel-models.sh status` |
| Replies of `!!!!!!` | the chat server was started without `--disable-custom-all-reduce` ([`uni-server-vllm.md`](uni-server-vllm.md) §0.1) |
| 401 from a model server | the key in `backend.env` does not match `models.env` |
| Sign-in works but you are logged straight out | `HERHEALTH_COOKIE_SECURE` must be `false` on plain HTTP |
| `make serve` fails importing LangChain or FAISS | run with `--extra retrieval` (the Makefile does) |

## Shutting down

```bash
# backend and frontend: Ctrl+C, or kill by PID (list with: ps -eo pid,args | grep -E "[n]ext-server|[h]erhealth_backend")
scripts/serve-models.sh stop     # only if nobody else needs the models
```
