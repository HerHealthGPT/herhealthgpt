# Model-serving stack on the campus GPU box — design

Date: 2026-10-11. Status: draft, awaiting review.

This is step 1 of three. Steps 2 and 3 get their own specs:

1. **Model-serving stack** (this document): three vLLM processes, a compose
   file, a native launcher, smoke tests.
2. **Retrieval**: LangChain index build and an embed → search → rerank
   retriever on the two new models.
3. **Backend chain**: LangChain retriever → prompt → chat model → structured
   `TriageDecision`, OpenRouter removed, `services/model` retired.

## What was decided, and by whom

Decided by Mazen Bahgat on 2026-10-11:

- The stack runs on the campus GPU box only. OpenRouter is no longer used.
- The reasoning model is `Qwen/Qwen3.5-9B` with the project's LoRA adapter at
  `herhealth-lora-v2/` in the repo root (gitignored).
- Embeddings move from `BAAI/bge-m3` to `Qwen/Qwen3-Embedding-4B`, and
  `Qwen/Qwen3-Reranker-4B` is added as a reranker.
- The RAG pipeline is rewritten on LangChain, end to end, including the LLM
  call.
- A Docker Compose file is the reproducible definition of the serving stack.
  A native launcher is what actually runs on this box.
- The chat context window is 32,768 tokens.

These reverse parts of `CLAUDE.md`, ADR 0010 (bge-m3, no reranker), ADR 0011
rule 1 (the adapter is phrasing-only until retrained) and ADR 0012 (OpenRouter
reasoning). Those documents still describe the earlier stack. Updating them, or
writing the ADR that supersedes them, belongs to step 3 and is not done here.
The adapter's measured behaviour is unchanged by this decision: the evaluation
recorded clarification-seeking at 0.000 and French and Arabic under-triage at
0.994 after fine-tuning, on silver labels that are not clinician-adjudicated.

## Why a compose file and a native launcher

The working environment is an unprivileged JupyterHub pod on Kubernetes. The
Docker CLI is installed but no daemon is reachable, rootless Docker cannot
start (mounts are denied; `newuidmap` and `/dev/fuse` are absent) and the
NVIDIA container toolkit is not installed. A compose file therefore cannot be
started or tested here.

vLLM 0.28.0 already runs natively from `/home/jovyan/herhealthgpt-venv`. So:

- `infra/compose.model.yml` is the reproducible definition for any host with
  Docker and GPU access. On this box it is validated with
  `docker compose config` only.
- `scripts/serve-models.sh` runs the same three processes natively.
- Both read `infra/model/serve.conf`, so flags, ports and model revisions
  cannot drift between them.

## Runtime layout

Four NVIDIA A16 cards. vLLM sees 14.61 GiB on each.

| Process | Model | GPUs | Port | Served name |
|---|---|---|---|---|
| chat | `Qwen/Qwen3.5-9B` + LoRA | 0, 1 | 8002 | `herhealth` (adapter), base under its own id |
| embeddings | `Qwen/Qwen3-Embedding-4B` | 2 | 8003 | `herhealth-embed` |
| reranker | `Qwen/Qwen3-Reranker-4B` | 3 | 8004 | `herhealth-rerank` |

All three bind to `127.0.0.1`. Port 8002 is the backend's existing default
for `HERHEALTH_VLLM_URL`; the old launcher defaulted to 8000.

Why this split and no other:

- Tensor-parallel size must divide the model's 16 attention heads and 4
  key-value heads, so the chat model can use 1, 2 or 4 GPUs. Three is invalid.
  One is too small for 17.98 GiB of weights.
- Each 4B model is about 8 GB of weights at 16-bit precision. Two of them do
  not fit on one 14.61 GiB card, so each gets its own.

### Chat memory and the context window

Measured from vLLM's log of the 2026-09-17 serve, same flags, two GPUs:

| Item | Per GPU |
|---|---|
| Visible memory | 14.61 GiB |
| vLLM budget at `--gpu-memory-utilization` 0.92 | 13.44 GiB |
| Weights as loaded | 8.53 GiB |
| Runtime overhead | 0.93 GiB |
| Token cache | 3.98 GiB, holding 183,947 tokens |

That table is the 8,192 window. Measured on 2026-10-11 at the 32,768 window,
the same 3.98 GiB holds 234,599 tokens, which is 7.16 full-length requests at
once (the estimate before the run was 5.6).
This depends on `--enforce-eager`: with CUDA graphs enabled an earlier run
left 1.71 GiB per GPU and 78,568 tokens.

Speed, not memory, is the practical limit. Code comments record about 100
seconds per model call at prompts of 4,000 to 5,000 tokens.

## Files

### `infra/model/serve.conf` (new)

Originally specified as `serve.env`. Renamed at commit time: `.gitignore`
ignores `*.env` and the hygiene check rejects any committed file with `env`
as a name part, since those names are reserved for secrets.

One `KEY=value` file, valid for both `docker compose --env-file` and
`source` in bash. No secrets.

```
VLLM_VERSION=0.28.0
HF_HOME=/home/jovyan/.cache/huggingface

CHAT_MODEL=Qwen/Qwen3.5-9B
CHAT_REVISION=<commit sha of the cached snapshot>
CHAT_ADAPTER_NAME=herhealth
CHAT_ADAPTER_DIR=./herhealth-lora-v2
CHAT_GPUS=0,1
CHAT_PORT=8002
CHAT_MAX_MODEL_LEN=32768

EMBED_MODEL=Qwen/Qwen3-Embedding-4B
EMBED_REVISION=<commit sha, recorded at download>
EMBED_SERVED_NAME=herhealth-embed
EMBED_GPUS=2
EMBED_PORT=8003
EMBED_MAX_MODEL_LEN=8192

RERANK_MODEL=Qwen/Qwen3-Reranker-4B
RERANK_REVISION=<commit sha, recorded at download>
RERANK_SERVED_NAME=herhealth-rerank
RERANK_GPUS=3
RERANK_PORT=8004
RERANK_MAX_MODEL_LEN=8192
```

The three `*_REVISION` values are filled with real commit SHAs during
implementation. An unpinned revision is a defect: the retrieval index in step
2 is only valid against the exact embedding weights that built it.

### `infra/compose.model.yml` (new)

Three services on `vllm/vllm-openai:v${VLLM_VERSION}`. Each has:

- `deploy.resources.reservations.devices` with explicit `device_ids`.
- `ipc: host`, which vLLM's tensor-parallel workers need.
- The Hugging Face cache mounted read-only at the container's `HF_HOME`, and
  `HF_HUB_OFFLINE=1`, so a start never downloads.
- The port published on `127.0.0.1` only.
- A health check on `GET /health` with a long start period.
- `restart: unless-stopped`.

The chat service also mounts `CHAT_ADAPTER_DIR` read-only.

### `scripts/serve-models.sh` (new, replaces `scripts/setup-uni-vllm.sh`)

Subcommands: `start [chat|embed|rerank|all]`, `stop [...]`, `check`, `clean`,
and `print <service>`, which prints the `vllm` arguments without starting
anything. A test compares that output with the compose file's command for the
same service, which is what keeps the two definitions identical.

- Reads `infra/model/serve.conf`.
- Sets `CUDA_VISIBLE_DEVICES` per process from `*_GPUS`.
- Writes a pid file and a log per process under
  `/home/jovyan/herhealth-serve/`, which is on the persistent volume.
- `check` reports, per process: pid state, whether `/v1/models` answers, the
  weights' presence and size, and free disk.
- `clean` keeps the existing behaviour, including removing `~/.cache/vllm`,
  whose stale peer-access probe caused the corruption described in the
  runbook.
- Refuses to start a process whose weights are missing, and prints the
  download command. It does not download by itself: a network call is asked
  for, never implied.

`scripts/setup-uni-vllm.sh` is deleted in the same change, and the references
to it in `docs/runbooks/` are updated.

### Flags

Chat keeps every flag proven on this hardware, with two changes: the adapter
path and the window.

```
vllm serve $CHAT_MODEL --revision $CHAT_REVISION
  --enable-lora --lora-modules $CHAT_ADAPTER_NAME=$CHAT_ADAPTER_DIR
  --max-lora-rank 16
  --max-model-len $CHAT_MAX_MODEL_LEN
  --tensor-parallel-size 2
  --disable-custom-all-reduce
  --enforce-eager
  --limit-mm-per-prompt '{"image":0,"video":0}'
  --host 127.0.0.1 --port $CHAT_PORT
```

Environment, as today: `NCCL_P2P_DISABLE=1`, `NCCL_IB_DISABLE=1`,
`VLLM_USE_FLASHINFER_SAMPLER=0`, `TRITON_CACHE_DIR` on the persistent volume.

`nvidia-smi topo -p2p r` reported peer access as OK between all four cards on
2026-10-11. `--disable-custom-all-reduce` stays regardless: the failure it
prevents is silent corruption, and removing it is not part of this work.

Embeddings and reranker run with `--runner pooling`.

- Embeddings: `--convert embed`.
- Reranker: the installed vLLM has a dedicated path for the original Qwen3
  reranker, switched on by the Hugging Face config keys
  `is_original_qwen3_reranker` and `classifier_from_token` (two tokens),
  passed through `--hf-overrides`, plus a scoring chat template. The exact
  values are taken from vLLM 0.28's own example
  (`examples/pooling/score/qwen3_reranker_*`) during implementation and
  recorded in `serve.conf` comments. They are not written here from memory.

### `scripts/smoke_models.py` (new)

A standalone script using `httpx` only. Exit code 0 means the stack is
usable. Checks, in order:

1. `GET /health` answers on all three ports.
2. Chat `/v1/models` lists the base model and `herhealth`.
3. Chat, with `model=herhealth`, answers one short prompt each in English,
   French and Arabic. The reply must be non-empty and must not be a run of
   `!`, which is the signature of the corrupted all-reduce.
4. Embeddings returns vectors of one consistent width for three inputs, with
   finite values. The width is printed and recorded for step 2.
5. Reranker scores a relevant passage above an irrelevant one for the same
   query, in English, French and Arabic.
6. Structured-output probe: one chat request with a JSON schema taken from
   `TriageDecision.model_json_schema()`. Reported separately as PASS, FAIL or
   CRASH, and it does not affect the exit code. After the probe the script
   re-checks chat `/health`, because the known failure mode kills the engine.

Fixture texts for checks 3 and 5 are plain everyday sentences that are not
about health at all (a calendar, a library, tomatoes). They test that the
models answer, embed and rank in three languages, and assert nothing clinical.

### Docs

- `docs/runbooks/uni-server-vllm.md`: updated to the three-process layout,
  the new script and the 32,768 window. Section 0.3 currently says 8192 is
  the verified working value.
- `docs/runbooks/dev-vllm-lora-endpoint.md`: its §6 restriction on the
  adapter is left as written; step 3's ADR is where that is revisited.

## Prerequisites needing a go-ahead

None is done until confirmed at implementation time.

- **Python environment.** The repo has no virtual environment on this box.
  The first `uv run` installs the workspace's dependencies from PyPI. The
  environment and uv's cache go on the ephemeral disk
  (`UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv`, `UV_CACHE_DIR=/tmp/uv-cache`)
  so they take nothing from the persistent volume.

- **Disk.** The persistent volume has 15 GB free; the two models need about
  16 GB. Deleting `/home/jovyan/.cache/pip` (3.7 GB) makes them fit, with
  about 2.7 GB to spare. The ephemeral disk has 78 GB but is wiped on restart.
- **Network.** Downloading `Qwen/Qwen3-Embedding-4B` and
  `Qwen/Qwen3-Reranker-4B` from Hugging Face. Both are expected to be public
  and ungated; this is confirmed at download, since no Hugging Face token is
  stored on this box.

## Risks

- **Structured output crashed this setup on 2026-09-08.** With the model
  split across two GPUs, enabling constrained decoding hit a CUDA launch
  failure in the token-bitmask kernel and took the engine down. Check 6
  retests it on 0.28.0. If it still crashes, step 3 falls back to JSON by
  prompt, validation and retry, which is what the backend does today, and
  there is no second model behind it once OpenRouter is gone. A code comment
  records roughly one in four in-scope turns failing against the adapter
  alone on 2026-09-09.
- **The compose file is unverified at runtime.** It is validated for syntax
  and interpolation only. Its first real start will be on some other host.
- **Idle culling.** JupyterHub stops the pod when idle, which kills all three
  processes. The launcher restores them; nothing restarts them automatically.
- **Disk margin is thin** after the downloads. Step 2's index and LangChain
  dependencies have to fit in what remains.
- **Slow generation.** A larger window allows longer prompts, and each call
  already takes on the order of 100 seconds.

## Out of scope

- Any change to the backend, frontend or database.
- The retrieval index, LangChain, and removing `bge-m3` (step 2).
- Removing OpenRouter and retiring `services/model` (step 3).
- Production on AWS. `infra/compose.prod.yml` and the deploy workflow are
  untouched and keep describing the earlier stack.
- Retraining the adapter.

## Done when

- `scripts/serve-models.sh start all` brings up three processes on this box
  and `scripts/smoke_models.py` exits 0.
- The structured-output probe has a recorded result.
- `docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf config`
  succeeds.
- `serve.conf` carries three real revision SHAs.
- The runbook describes the new layout.
