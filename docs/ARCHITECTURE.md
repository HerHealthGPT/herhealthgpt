# HerHealthGPT architecture: what is running

The reference for how the system is built and deployed **as it runs today**.
Read from the live servers, the configuration and the code on 2026-10-20.
Where another document disagrees with this one about what runs, this one was
checked more recently; decisions and their reasons live in the ADRs
(`docs/adr/`), which this document links rather than repeats.

**HerHealthGPT is an urgency-triage and information tool for women's
reproductive health, in English, Arabic and French. It does not diagnose.**
Its knowledge base is source-traceable, not clinician-adjudicated
([`DATASHEET.md`](DATASHEET.md)).

## 1. The whole system

```
 Browser (herhealthgpt.org)                       Campus GPU server (JupyterHub pod)
        │ HTTPS                                    ┌──────────────────────────────────┐
        ▼                                          │ vLLM :8002  Qwen3.5-9B           │
 ┌──────────── AWS EC2 t3.large, us-east-1 ──────┐ │       + LoRA "herhealth" (GPU 0,1)│
 │ Caddy  ── herhealthgpt.org ──► frontend :3000 │ │ vLLM :8003  Qwen3-Embedding-4B   │
 │        ── api.herhealthgpt.org ─► backend:8000├─┼─► (GPU 2)                        │
 │ Docker Compose; images from ECR, tag = git SHA│ │ vLLM :8004  Qwen3-Reranker-4B    │
 │ volume herhealth_uploads (kept files)         │ │       (GPU 3, off by default)    │
 └──────┬────────────────────────────┬───────────┘ │ cloudflared quick tunnels for    │
        │                            │             │ :8002 and :8003, watched by      │
        ▼                            ▼             │ tunnel-models.sh watch           │
 RDS PostgreSQL 16              Amazon SES         └──────────────────────────────────┘
 db.t4g.micro (private)         (verification and        ▲ HTTPS, bearer key
                                 reset emails)           └── from the backend container
```

The backend reaches the models through Cloudflare quick tunnels opened from
the GPU pod, because the pod accepts no inbound connections. The retrieval
index (FAISS) is baked into the backend image; only embedding the query
crosses the tunnel.

## 2. The GPU server

| | |
|---|---|
| Host | campus JupyterHub pod (no Docker daemon, no inbound connections) |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8.0-117 |
| CPU / RAM | 256 cores / 1 TB |
| GPUs | 4 × NVIDIA A16, 15 GB each, driver 580.126.09, CUDA 13.0 |
| Serving stack | Python 3.12.13, vLLM 0.28.0, PyTorch 2.13.0+cu130, Transformers 5.16.1 (venv `/home/jovyan/herhealthgpt-venv`) |
| Started by | `scripts/serve-models.sh`, settings in `infra/model/serve.conf` |
| Access | each server binds `127.0.0.1` and requires a bearer key, passed as `VLLM_API_KEY` in the environment (never on the command line); the key is in `infra/envs/models.env` (git-ignored) |

### The three model servers

| Port | Model (pinned revision) | GPUs | Served as | Used for |
|---|---|---|---|---|
| 8002 | `Qwen/Qwen3.5-9B` @ `c2022362` + LoRA adapter | 0, 1 (tensor parallel 2) | `Qwen/Qwen3.5-9B` and `herhealth` | every product model call; the adapter only in comparison mode B |
| 8003 | `Qwen/Qwen3-Embedding-4B` @ `5cf2132a` | 2 | `herhealth-embed` | embedding queries (2,560 dimensions) |
| 8004 | `Qwen/Qwen3-Reranker-4B` @ `22e68366` | 3 | `herhealth-rerank` | reranking, **off** (`HERHEALTH_RERANK=off`: no measured gain, ADR 0017) |

Launch flags of the chat server, and why each is there:

| Flag | Why |
|---|---|
| `--enable-lora --lora-modules herhealth=…/herhealth-lora-v2 --max-lora-rank 16` | serve the base and the adapter from one process |
| `--tensor-parallel-size 2` | 9B in bf16 does not fit one 15 GB A16 |
| `--disable-custom-all-reduce` | GPU peer-to-peer is unavailable here; vLLM's custom all-reduce silently corrupts activations and the model emits `!!!!` (`docs/runbooks/uni-server-vllm.md` §0.1) |
| `--enforce-eager` | no CUDA graphs, which leaves about 4 GiB per GPU for the token cache |
| `--limit-mm-per-prompt {"image":0,"video":0}` | the base is multimodal; capping both stops it reserving a vision encoder cache |
| `--max-model-len 32768` | a decision prompt is 15,000–21,600 characters plus retrieved passages |

The embedding server runs with `--runner pooling --convert embed`; the reranker
with `--runner pooling` and a `hf-overrides`/chat template that turn the
Qwen3 reranker into a yes/no classifier.

### Tunnels to production

`scripts/tunnel-models.sh` opens a Cloudflare quick tunnel (cloudflared
2026.10.0) to :8002 and :8003, checks they answer with the key, stores the
addresses in the GitHub variables `MODELS_CHAT_URL` / `MODELS_EMBED_URL` and
the key in the secret `MODELS_API_KEY`, and redeploys. A quick tunnel's
address changes when it restarts, so `tunnel-models.sh watch` runs on the pod
and every 5 minutes reopens a dead tunnel and republishes (one redeploy). It
does not survive the pod restarting. The lasting fix, a named tunnel with a
fixed hostname, needs a Cloudflare account and is not done.

## 3. The models and what each does

All calls go through LangChain's OpenAI-compatible client
(`triage/chain.py`, `build_chat_model`) at **temperature 0** with **thinking
off** (`chat_template_kwargs: {"enable_thinking": false}`).

| Role | Model | Max tokens | Code |
|---|---|---|---|
| Extract: what her message answers, as closed-vocabulary values | base | 300 | `chain.py` `LangChainFeatureExtractor` |
| Decide: `ask` / `conclude` / `inform` / `decline` as JSON | base | 1,200 | `chain.py` `LangChainReasoningClient` |
| Write an informational answer as a page | **base** (`HERHEALTH_PAGE_MODEL` unset) | 1,100, 60 s | `chain.py` `LangChainAnswerWriter` |
| Which features a general question is about (for "when to get help") | base | 300 | `chain.py` `LangChainSymptomTopics` |
| Read a tracker file no converter understands | base | 6,000 | `app/main.py` `_build_cycle_extractor` |
| Comparison mode B: plain chat, no retrieval, no checks | adapter `herhealth` | — | `triage/comparison.py` |

**The decision is not constrained by guided decoding.** The model is asked
for JSON; the client parses it, repairs what is safe to repair (drops unknown
null keys, invented condition names, names beside a non-emergency warning
sign), rejects case-note wording, validates it against `TriageDecision` and
against the knowledge base, and retries once with feedback
(`clients.py` `parse_decision_text`, `vocabulary.py`). The schema is the
safety net; it is enforced after generation, not during it.

**The fine-tuned adapter is not on the product path.** Pages were moved to
the base model on 2026-10-13: it wrote a complete page in 33 s where the
adapter took 95 s and copied passages sentence by sentence
(`app/config.py`, `page_model`). The adapter answers only in comparison
mode B, which is switched on in production (`COMPARISON_MODES=on`).

### The base model

`Qwen/Qwen3.5-9B` loads as `Qwen3_5ForConditionalGeneration`: a vision tower
(capped to zero, "text-only mode") and a hybrid stack in which every fourth
layer is full attention and the rest are gated linear-attention blocks.

### The adapter `herhealth-lora-v2`

| | |
|---|---|
| Type | LoRA, `r=16`, `lora_alpha=16`, dropout 0, no DoRA, no rsLoRA, `CAUSAL_LM` |
| Targets | `q/k/v/o_proj` and `gate/up/down_proj` of the language model (as a module-name pattern) |
| Trained on | `ft_corpus_v1.jsonl`, 2,700 single-turn answers (900 each menstrual, PCOS, fertility), QLoRA via Unsloth, `peft` 0.19.1 |
| Published | `huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2` (private) |
| Served from | `/home/jovyan/Grad-Project/herhealthgpt/herhealth-lora-v2` |
| May not decide | never shown a clarifying question; as decision-maker it returned 0 valid decisions on 30 questions against 23 for the base (2026-10-12). Retraining on multi-turn data is a precondition (CLAUDE.md) |

## 4. Retrieval

| | |
|---|---|
| Index | FAISS, `build/index/` (`index.faiss`, `passages.jsonl`, `manifest.json`, 40 MB), built on the GPU server by `make index`, published as a GitHub release by `scripts/publish-index-release.sh` (`INDEX_RELEASE`, today `index-20261013-…`), baked into the backend image by the deploy |
| Contents | 3,862 sentence-level source passages + 93 evidence statements, 2,560 dimensions, built 2026-10-12 |
| Excluded | NHS text (licence: quote-only); the backend refuses an index that contains any |
| Query | her opening message plus her most recent answers (`agent.py` `build_retrieval_query`), `k = 8`; an informational page searches again once per page section (24 each) |
| Code | `triage/retrieval.py` (`TriageRetriever`, `LangChainRetrievalClient`) |
| Latency | 0.09 s per search, measured |

**The index is behind the knowledge base by four rows.** It was built when
`evidence.csv` held 146 rows; batch 27 added four womenshealth rows on
2026-10-19. Those rows still reach the model through the evidence join in the
turn context; they are only missing as retrievable statements until
`make index` is run again.

## 5. Backend (FastAPI)

`services/backend`, Python 3.12. FastAPI 0.141, Uvicorn 0.52, Pydantic 2.13,
SQLAlchemy 2.0 (async) with psycopg 3, Alembic 1.19, LangChain core 1.6 /
langchain-openai 1.7 / langchain-community 0.4, faiss-cpu 1.15, pypdf 6,
defusedxml, argon2-cffi, google-auth, boto3 (SES).

### Endpoints

| Prefix | Routes |
|---|---|
| `/accounts` | `register`, `sign-in`, `sign-in/google`, `refresh`, `sign-out`, `sign-out-everywhere`, `me` (get, patch, delete), `verify-email` (+ `resend`), `reset-password` (+ `request`), `health-note`, `cycle-data` (+ `preview`), `files` (+ `/{id}`) |
| `/triage` | `turn`, `sessions`, `sessions/{id}` (get, delete), `models` |
| `/health` | readiness; pings the database |

### Data (PostgreSQL 16, migrations `0001`–`0012`)

`users`, `credentials`, `sessions`, `sign_in_failures`,
`email_verification_codes`, `verification_code_sends`, `password_reset_codes`,
`password_reset_sends`, `health_notes`, `cycle_data`, `stored_files`,
`consultation_sessions`, `messages` (each assistant message stores the full
decision payload, so a reopened chat shows its sources).

### One chat turn

`POST /triage/turn` → `app/triage/routes.py` → `TriageAgent.run_turn`
(`triage/agent.py`): retrieve → extract → build the turn context from the
knowledge files → compose the prompt → decide → gates → for an informational
answer, write the page and "when to get help" → route checks (repair,
closed vocabulary, provenance cap) → sources and cycle-data use attached →
stored → returned. Every step with its file and line, and ten traced
examples: [`experiments/2026-10-19-traced-consultations.md`](experiments/2026-10-19-traced-consultations.md).

The gates, in order (`agent.py` `run_turn`): her data, unclear decline,
inform with symptoms, premature conclusion (needs 5 answers), repeated
question, red flag. Each sends the reply back once; the her-data, repeated-
question and red-flag gates then act in code if the model still does not.

### Accounts and her data

- Passwords hashed with Argon2; sessions are httpOnly cookies with a
  short-lived access token and a refresh token; optional Google sign-in.
- Verification and password-reset codes sent by Amazon SES.
- Profile: date of birth (used as an age band, never stored as one) and an
  optional health note, both background only (ADR 0015).
- Cycle data (ADR 0019): read by converters (our CSV template, Apple Health
  export, Apple Health's shared PDF) or the base model; only closed-vocabulary
  values kept, after she confirms.
- Kept files (ADR 0020): stored on the EC2 disk in `herhealth_uploads`,
  deleted 30 days after upload by an hourly job; nothing reads them.

## 6. Frontend (Next.js)

`services/frontend`: Next.js 16.3.4, React 19.2.8, TypeScript 5,
Tailwind CSS 4, Radix UI, lucide icons, sonner toasts. Node 22 locally.
A normal responsive web app, **not a PWA**.

Pages: `/sign-up`, `/register`, `/sign-in`, `/verify-email`,
`/forgot-password`, `/reset-password`, `/onboarding`, `/dashboard`, `/chat`,
`/settings`, `/how-it-works`, `/cycle-import-guide`.

Interface languages: English, Arabic (right-to-left) and French
(`src/i18n/messages/{en,ar,fr}`). The chat replies in the language she
writes in. The API is called at `/api/*`, which Next.js forwards to the
backend locally; in production the browser calls `api.herhealthgpt.org`.

## 7. Knowledge base and data pipeline

Seven files in `knowledge/` (counts on 2026-10-20): 39 features, 19
conditions, 150 evidence rows, 17 warning-sign rules, 5 sources, 4 action
codes, and the weights file used by the retired controller. Every clinical
row carries a verbatim source quote. Full detail:
[`KNOWLEDGE_BASE.md`](KNOWLEDGE_BASE.md).

The pipeline (`services/data`, `make` targets): `fetch` (robots-checked,
immutable raw copies) → `clean` → `evidence` (batches → `evidence.csv`,
approved batches only) → `validate` → `verify-quotes` → `index` (needs the
embedding server).

`packages/contracts`: the Pydantic schemas shared by the services
(`TriageDecision`, the knowledge-file models, `RetrievedPassage`,
`CycleExtraction`). Nothing else may be imported across services.

## 8. Production on AWS

| | |
|---|---|
| Region | `us-east-1` |
| Server | one EC2 `t3.large`, 60 GB encrypted root disk, auto-recovers on hardware failure |
| Containers | Docker Compose (`infra/compose.prod.yml`): Caddy, frontend, backend; images in ECR tagged with the git SHA |
| Database | RDS PostgreSQL 16, `db.t4g.micro`, private subnet, single-AZ, 7-day backups |
| TLS / proxy | Caddy with Let's Encrypt, `herhealthgpt.org` and `api.herhealthgpt.org` |
| Email | Amazon SES |
| Logs and alarms | CloudWatch log groups per container; 7 alarms to one SNS email topic |
| Secrets | Secrets Manager (database), SSM, GitHub secrets for the model key |
| Infrastructure as code | Terraform (`infra/terraform/prod`), applied by hand, never by CI |

**Deploy.** A merge to `main` that touches a service runs the `deploy`
workflow: build both images, push to ECR, copy the compose file and
Caddyfile to S3, then run `/opt/herhealth/deploy.sh <sha>` on the host
through SSM. The host migrates the database, switches release, health-checks
through Caddy, and rolls back by itself if the check fails.
Runbook: [`runbooks/aws-deploy.md`](runbooks/aws-deploy.md).

**CI** (`.github/workflows`, path-filtered): `backend`, `frontend`, `data`,
`terraform` (plan only), `hygiene` (blocks payload-shaped files, every PR),
`deploy`.

## 9. Evaluation tooling

| Command | Measures |
|---|---|
| `make eval-red-flags` | live red-flag recall, one case per rule (17 of 17, 2026-10-19) |
| `make eval-languages` | same urgency across English, Arabic, French over full consultations |
| `make trace-turns` | every layer of ten consultations, call by call |
| `herhealth-eval-decisions` | first turns and scripted consultations |
| `make eval` | the retired rule-based controller only |

Figures and their limits: [`DATASHEET.md`](DATASHEET.md).

## 10. Known gaps in what runs

- The retrieval index predates batch 27 (four rows); run `make index`.
- The decision format is checked after generation, not constrained during it.
- The fine-tuned adapter is not used by the product; it waits on a
  multi-turn retrain.
- The tunnel addresses change on restart; the watchdog republishes, a named
  tunnel would not need to.
- One server and a single-AZ database; kept files have no backup.
- Arabic and French wording is not reviewed by a native speaker.
