---
status: runbook
---

# Runbook: running the whole app, on both machines

Everything below was executed end to end on **2026-09-09** and the results are
what this file records — not what the design intends. Two machines:

| Machine | Runs | Needed for |
|---|---|---|
| **Campus VM** (Lobot JupyterHub, `group-digi2026-g1`) | vLLM + the `herhealth` LoRA | the **Fine-tuned** tab only |
| **Your laptop** | Postgres, retrieval, backend, frontend | everything |

The laptop stack works on its own. **Base** chat runs entirely off OpenRouter and
never touches campus. Start the VM only when you need the Fine-tuned tab.

---

## Part 1 — Campus VM (skip if you only need Base)

Full detail, including the flags and why each one exists, is in
[uni-server-vllm.md](uni-server-vllm.md). The short version:

1. Open JupyterLab → File → New → Terminal. **Leave the tab open** — closing it
   kills the container and vLLM with it.
2. Clean, then start, using blocks A and B of
   [uni-server-vllm.md §0](uni-server-vllm.md).
3. Wait for `Application startup complete.` (~30 s).
4. Verify on the VM:
   ```bash
   curl -s http://127.0.0.1:8000/v1/models
   ```
   Must list `Qwen/Qwen3.5-9B` and `herhealth`, with `herhealth`'s `parent`
   set to the base model.
5. Copy the proxy token — it **rotates on every Jupyter restart**:
   ```bash
   echo "$JUPYTERHUB_API_TOKEN"
   ```
6. Confirm the route your laptop will use, from the VM:
   ```bash
   curl -sS -H "Authorization: token ${JUPYTERHUB_API_TOKEN}" \
     "https://lobot.cs.queensu.ca/user/group-digi2026-g1/proxy/8000/v1/models"
   ```

**Never put the pod IP (`10.244.x.x`) in any laptop config.** It is reachable
only from inside the Kubernetes cluster.

---

## Part 2 — Laptop configuration

`infra/envs/backend.env` (gitignored; copy from `backend.env.example`). The
values that matter for this runbook:

```env
HERHEALTH_DATABASE_URL=postgresql+psycopg://herhealth:herhealth@localhost:5432/herhealth
HERHEALTH_SESSION_SECRET=<openssl rand -hex 32>
HERHEALTH_TRIAGE_MODE=openrouter
OPENROUTER_API_KEY=sk-or-...
HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001
HERHEALTH_COOKIE_SECURE=false
HERHEALTH_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Fine-tuned tab only
HERHEALTH_MODEL_SELECTOR=on
HERHEALTH_VLLM_URL=https://lobot.cs.queensu.ca/user/group-digi2026-g1/proxy/8000
HERHEALTH_VLLM_MODEL=herhealth
HERHEALTH_VLLM_API_KEY=<JUPYTERHUB_API_TOKEN from Part 1 step 5>
```

Two things that trip people up:

- **`HERHEALTH_TRIAGE_MODE` stays `openrouter` even when using Fine-tuned.**
  The mode selects the *default*; the tab selects the client. Base →
  OpenRouter, Fine-tuned → `HERHEALTH_VLLM_*`.
- **No trailing slash on `HERHEALTH_VLLM_URL`.** The client appends
  `/v1/chat/completions` itself.

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker Desktop, Node 20+, and
a built index at `build/index/`. Confirm the index with:

```bash
cat build/index/manifest.json     # 4,454 passages / 1024 dims / BAAI/bge-m3
```

---

## Part 3 — Start the laptop stack

**Order matters.** Every triage turn calls retrieval on `:8001` *before* the
reasoning model, so a backend without retrieval returns `502` no matter how
healthy campus is.

### 1. Postgres

```bash
docker compose -f infra/compose.yml up -d postgres
docker exec infra-postgres-1 pg_isready -U herhealth      # "accepting connections"
```

### 2. Migrations (first run, and after pulling new ones)

```bash
set -a; . ./infra/envs/backend.env; set +a
cd services/backend && uv run --extra api alembic upgrade head
cd ../..
```

`alembic current` should print a revision ending `(head)` — as of 2026-09-09
that is `0009_dob_and_health_note`.

### 3. Retrieval — `services/model` on :8001

```bash
export HERHEALTH_INDEX_DIR="$(pwd)/build/index"
uv run --package herhealth-model python -m herhealth_model
```

First load of `bge-m3` takes **1–3 minutes**. Wait for it:

```bash
curl -s http://127.0.0.1:8001/health          # {"status":"ok"}
```

**Do not start the backend until this answers.** Measured 2026-09-09: it took
~35 s to become healthy, while the backend was ready in under 15 s — so the
backend comes up *first* and looks fine while every turn still 502s.

### 4. Backend — FastAPI on :8000

```bash
set -a; . ./infra/envs/backend.env; set +a
export HERHEALTH_KNOWLEDGE_DIR="$(pwd)/knowledge"
uv run --extra api --package herhealth-backend python -m herhealth_backend.app
```

```bash
curl -s http://127.0.0.1:8000/health          # {"status":"ok"}
```

Restart this after **any** change to `HERHEALTH_VLLM_*` or
`HERHEALTH_MODEL_SELECTOR`.

### 5. Frontend — Next.js on :3000

```bash
cd services/frontend
npm install        # first time only
npm run dev
```

Next takes ~50 s to serve its first request. <http://localhost:3000>

### PowerShell equivalent for steps 2–4

`set -a; . ./file` is Git Bash. In PowerShell, load the env file like this:

```powershell
Get-Content .\infra\envs\backend.env | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith('#')) { return }
  $i = $line.IndexOf('=')
  if ($i -lt 1) { return }
  Set-Item -Path ("Env:" + $line.Substring(0, $i).Trim()) -Value $line.Substring($i + 1).Trim()
}
```

---

## Part 4 — Verify, without opening a browser

### The whole stack in one block

```bash
printf "postgres  %s\n" "$(docker exec infra-postgres-1 pg_isready -U herhealth 2>&1 | tail -1)"
printf "model     %s\n" "$(curl -s -m 5 http://127.0.0.1:8001/health)"
printf "backend   %s\n" "$(curl -s -m 5 http://127.0.0.1:8000/health)"
printf "frontend  HTTP %s\n" "$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:3000/)"

set -a; . ./infra/envs/backend.env; set +a
curl -s -m 20 -H "Authorization: Bearer $HERHEALTH_VLLM_API_KEY" \
  "$HERHEALTH_VLLM_URL/v1/models"
```

Expected, all four green plus both model ids from campus.

### Retrieval on its own

```bash
curl -s -X POST http://127.0.0.1:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"irregular periods and pelvic pain","k":3}'
```

Each hit must carry a real `feature_id` and `condition_id` — not just a
`passage_id`. If they are null the prompt cannot name a feature, and the model
will invent one.

### The full RAG + Fine-tuned path

`/triage/*` requires a signed-in session, so the fastest end-to-end check
drives the clients directly — the same three objects `routes.py` wires up:

```python
from pathlib import Path
import os
from herhealth_contracts.loading import load_knowledge_base
from herhealth_backend.triage.agent import Message, TriageAgent
from herhealth_backend.triage.clients import HttpRetrievalClient, VllmReasoningClient
from herhealth_backend.triage.vocabulary import validate_against_knowledge_base

base = load_knowledge_base(Path(os.environ["HERHEALTH_KNOWLEDGE_DIR"]))
agent = TriageAgent(
    base=base,
    reasoning=VllmReasoningClient(),                        # campus LoRA
    retrieval=HttpRetrievalClient(base_url="http://127.0.0.1:8001"),
)
turn = agent.run_turn([Message(role="user", content="I've had irregular periods for three months.")])
validate_against_knowledge_base(turn.decision, agent.base, turn.retrieved)   # what the API does
print(turn.decision)
```

**`validate_against_knowledge_base` is the step that matters.** Without it the
check is far more optimistic than the app: `TriageDecision` alone does *not*
enforce the closed vocabularies, and a decision that parses can still be
rejected by the route as a `ClosedVocabularyViolation` → `502`.

### In the browser

<http://localhost:3000/chat> → sign in → set date of birth if prompted (the age
band is injected into the triage prompt) → **new** chat → pick **Base** or
**Fine-tuned** → send *"I've had irregular periods for three months."*

Tabs lock after the first user message in a session, so choose before sending.

---

## Part 5 — What the Fine-tuned tab actually does today

Measured 2026-09-09 over repeated identical runs of the same in-scope opening
message, through the full retrieve → reason → validate path.

**Before the fallback landed: 3 of 4 runs returned 200, the fourth was a 502.**
Latency 16.5 s – 63 s per turn.

**After (2026-09-09, same message, same method): 4 of 4 returned 200**, with the
base-model fallback firing exactly once — on the run that previously failed.
Latency 28.8 s / **101.6 s** / 47.1 s / 36.0 s. That 101.6 s is the fallback
path: `VllmReasoningClient` spends all three of its own corrective retries
against the adapter before `FallbackReasoningClient` hands over to OpenRouter,
so a recovered turn costs roughly the failed attempt *plus* a fresh one. It fits
inside `REASONING_TIMEOUT_SECONDS` (150 s), but not with much room — if turns
start timing out, lowering `MAX_DECISION_ATTEMPTS` for the vLLM primary is the
lever, because handing over sooner is cheaper than retrying a model that is
failing for structural reasons.

The failure modes below are what the fallback now absorbs. They have not gone
away; they are recovered from.

That is the honest state of the integration. Three distinct causes, all
observed:

1. **`citations` omitted on an `ask`.** By far the most common. The model
   decides to ask a clarifying question and sends no citation, which
   `TriageDecision` rejects — *"a decision must be grounded in at least one
   citation or a red_flag_id"*. `_decide_via_chat_completions` retries up to
   `MAX_DECISION_ATTEMPTS` (3) with corrective feedback appended. Usually the
   retry fixes it; run 3 exhausted all three attempts and became a 502.
2. **`"conclude": false` sent as an extra key.** The model treats the
   `type` values as boolean flags — `extra_forbidden`. Recovered on retry.
3. **Out-of-vocabulary condition ids.** One run returned
   `matching_conditions` including **`menopause`**, which is *not* in
   `conditions.yaml` — the real id is `perimenopause`. `TriageDecision`
   accepted it; only `validate_against_knowledge_base` catches it, as a
   `ClosedVocabularyViolation` → 502.

None of this is the model server misbehaving — campus vLLM answered every
request correctly. It is the JSON contract being enforced by validation on
receipt rather than by constrained decoding, which is the documented gap in
[ADR 0011](../adr/0011-controller-free-triage.md)'s migration checklist item 7.

**Cases 1 and 2 now fail over to the base model**; case 3 does not.
`ClosedVocabularyViolation` is raised by `routes.py` *after* the client returns,
so `FallbackReasoningClient` never sees it — that route retries against the same
client instead. An out-of-vocabulary condition id is therefore still a possible
502.

**The per-answer "unreviewed model" notice was removed on 2026-09-09.** The
Fine-tuned option is `reviewed=True`, so `UnreviewedModelNotice` renders
nothing. The adapter's training did not change, and neither did anything in
Part 5 above; what still keeps it out of a demo is `HERHEALTH_MODEL_SELECTOR`
being off by default, and `default_model_id` still resolving to the base
model.

**Two known-and-expected behaviours that are not defects:**

- The adapter frequently **concludes without asking first**. It is
  phrasing-trained only; `gold_seeds_styled.csv` contains no example where the
  correct move is a clarifying question. See CLAUDE.md.
- The out-of-scope path works. *"Who won the football match last night?"*
  correctly returned `type=decline` with no citations and no action code, in
  7.6 s.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `502` / `WinError 10061` on every turn | `:8001` is not listening. It is slower to start than the backend — check `curl http://127.0.0.1:8001/health` first, always. |
| `502` with `ClosedVocabularyViolation` in the backend log | The model used a feature/condition/red-flag id outside the closed vocabulary. Expected at some rate today — see Part 5. |
| `502` with `malformed JSON` after 3 attempts | The retry loop was exhausted, usually on the missing-citation rule. Retry the message. |
| **Fine-tuned** tab greyed out | `HERHEALTH_VLLM_URL` unset, or the backend was not restarted after setting it. Restart, then hard-refresh so `GET /triage/models` reloads. |
| `504 Gateway Time-out` from the Lobot proxy | The Hub cut the request at ~60 s. Warm the LoRA with a short curl on the VM first, then retry. |
| Fine-tuned worked yesterday, 403 today | `JUPYTERHUB_API_TOKEN` rotated. Re-copy it (Part 1 step 5), update `backend.env`, restart the backend. |
| Everything on the VM is gone | The Jupyter server was culled. Re-run [uni-server-vllm.md §0](uni-server-vllm.md); the token will have rotated too. |
| Model replies are `!!!!!!!` | Custom all-reduce corrupting TP output. [uni-server-vllm.md §0.1](uni-server-vllm.md). |

---

## Shutting down

```bash
# laptop: Ctrl+C the frontend, backend and model terminals, then
docker compose -f infra/compose.yml down

# VM: stop vLLM (or just close JupyterLab, which kills it anyway)
kill "$(cat /home/jovyan/vllm.pid)"
```
