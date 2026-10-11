---
status: runbook
---

# Runbook: serving the LoRA adapter on the university VM (JupyterHub)

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
All three were answering about two and a half minutes after `start all`.

Acceptance test, with the three processes up:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache
uv run python scripts/smoke_models.py --skip-structured
```

Last run on this box, 2026-10-11:

```
ok    health chat  answering
ok    health embed  answering
ok    health rerank  answering
ok    models http://127.0.0.1:8002  Qwen/Qwen3.5-9B, herhealth
ok    chat en  A calendar is a system of organizing days for social, religious, scientific, com
ok    chat fr  Un calendrier sert à organiser et à planifier nos activités sur une période donn
ok    chat ar  يساعدنا التقويم في تنظيم وقتنا وتخطيط أنشطتنا اليومية والشهرية والسنة.
ok    embeddings  width=2560
ok    rerank en  relevant=0.9962 irrelevant=2.837e-06
ok    rerank fr  relevant=0.9986 irrelevant=3.975e-06
ok    rerank ar  relevant=0.9993 irrelevant=3.44e-06
11 of 11 checks passed
```

The embedding width, 2560, is what the retrieval index has to be built at.

**Schema-constrained decoding does not work on this serve.** It crashed the
engine on 2026-09-08. Retested on 2026-10-11 with vLLM 0.28.0, it no longer
crashes, and normal chat keeps working afterwards, but both attempts
returned HTTP 500:

- The full `TriageDecision` schema (`uv run python scripts/smoke_models.py`):
  `Regex compilation timed out after 5s. The pattern may be too complex`,
  raised from vLLM's outlines backend.
- A two-field schema sent by hand: `grammar rejected tokens [248046]`, and
  the request was terminated.

Until that is investigated, structured output has to come from the prompt,
with validation and retry in the caller.

**If a GPU refuses to start a process** with `CUDA-capable device(s) is/are
busy or unavailable` while `nvidia-smi` shows no process on it and
`nvidia-smi -q -i <n>` says `System is not in ready state`, the card is
stuck, not misconfigured. On 2026-10-11 this happened to GPU 3 and restarting
the JupyterHub server cleared it.

On a host with Docker and the NVIDIA container toolkit, the same three
processes start with:

```bash
docker compose -f infra/compose.model.yml --env-file infra/model/serve.conf up -d
```

That file has never been started. It was validated on this box with
`docker compose config` on 2026-10-11, and
`scripts/tests/test_compose_parity.py` checks it against the launcher. Both
need the Docker CLI, which is not part of this pod's image and disappears on
restart; without it those tests skip.

### Restoring after a wipe

The launcher expects vLLM at `/home/jovyan/herhealthgpt-venv`, the models in
`/home/jovyan/.cache/huggingface` at the revisions pinned in `serve.conf`, and
the adapter in `herhealth-lora-v2/` in the repo root. If any is gone:

```bash
python -m venv /home/jovyan/herhealthgpt-venv
/home/jovyan/herhealthgpt-venv/bin/pip install vllm==0.28.0 huggingface_hub

export HF_HOME=/home/jovyan/.cache/huggingface
set -a; . infra/model/serve.conf; set +a
HF=/home/jovyan/herhealthgpt-venv/bin/hf
$HF download "$CHAT_MODEL"   --revision "$CHAT_REVISION"     # 19 GB
$HF download "$EMBED_MODEL"  --revision "$EMBED_REVISION"    # 7.6 GB
$HF download "$RERANK_MODEL" --revision "$RERANK_REVISION"   # 7.6 GB

# The adapter repo is private: this one needs `$HF auth login` with a READ
# token for the herhealthgpt org first. Never paste the token into the repo.
$HF download herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2 --local-dir herhealth-lora-v2
```

The three models and the vLLM install fill the 49 GB home volume to within
about 3 GB, so check `df -h /home/jovyan` before downloading anything else.

After a pod restart the processes are gone and nothing restarts them:
run `start all` again. Keep a JupyterLab tab open while testing, or idle
culling will stop the pod.

## 0. Start the server (copy-paste)

Closing the JupyterLab tab (or Hub → Stop My Server) **kills the container**.
vLLM dies with it. The pod IP (`10.244.x.x`) is gone. Home-volume files may
survive; the GPU process never does.

Verified working on **2026-09-09**, vLLM **0.28.0**, as
`jovyan@jupyter-group-digi2026-g1`. Engine init 15.98 s; server answering ~30 s
after launch; a 454-token answer took 35 s.

| | |
|---|---|
| Base | `Qwen/Qwen3.5-9B` |
| Adapter id | `herhealth` |
| Adapter path | `/home/jovyan/models/herhealth-lora-v2` |
| Venv | `~/herhealthgpt-venv` (fallback: `~/vllm-env`) |
| GPUs | two NVIDIA A16, 14.6 GiB usable each, **sm_86** |
| Port **inside the pod** | **8000** |
| `max_model_len` | **8192** |
| `tensor_parallel_size` | **2** |
| API key | none |
| Pod IP | `10.244.x.x` — Kubernetes-only; this laptop cannot use it |

Open JupyterLab → File → New → Terminal. Paste **block A**, then **block B**.

### A. Clean leftover GPU / vLLM

```bash
pkill -9 -f 'vllm serve' || true
pkill -9 -f 'VLLM::' || true
rm -f /home/jovyan/vllm.pid
rm -rf ~/.cache/vllm          # stale GPU P2P-capability probe cache — see §0.1
sleep 5
nvidia-smi --query-gpu=index,memory.used --format=csv
# expect ~0 MiB on both GPUs before continuing
```

Do **not** delete `/home/jovyan/models/` or `~/.cache/huggingface/` /
`~/.cache/triton/` unless you intend to re-download / recompile.
`~/.cache/vllm` is different — cheap to rebuild, and it holds the stale
peer-access probe implicated in §0.1.

### B. Start

```bash
source ~/herhealthgpt-venv/bin/activate
# if that fails: source ~/vllm-env/bin/activate

nohup env \
  NCCL_P2P_DISABLE=1 \
  NCCL_IB_DISABLE=1 \
  VLLM_USE_FLASHINFER_SAMPLER=0 \
  NCCL_DEBUG=INFO \
  TRITON_CACHE_DIR=/home/jovyan/.cache/triton \
  HF_HOME=/home/jovyan/.cache/huggingface \
  vllm serve Qwen/Qwen3.5-9B \
  --enable-lora \
  --lora-modules herhealth=/home/jovyan/models/herhealth-lora-v2 \
  --max-lora-rank 16 \
  --max-model-len 8192 \
  --tensor-parallel-size 2 \
  --disable-custom-all-reduce \
  --enforce-eager \
  --limit-mm-per-prompt '{"image":0,"video":0}' \
  --host 127.0.0.1 --port 8000 \
  > /home/jovyan/vllm.log 2>&1 &
echo $! > /home/jovyan/vllm.pid
tail -f /home/jovyan/vllm.log
```

| Flag / env | Failure without it |
|---|---|
| **`--disable-custom-all-reduce`** | **Corrupt `!!!!!!!` output *and* a startup deadlock. Mandatory on this box — see §0.1.** |
| `NCCL_P2P_DISABLE=1` / `NCCL_IB_DISABLE=1` | Hang after NCCL init (185 MiB, 100% util) |
| `VLLM_USE_FLASHINFER_SAMPLER=0` | Crash: FlashInfer ninja build, missing `curand.h` |
| `--enforce-eager` | Long Inductor / CUDA-graph spin at empty VRAM |
| `--limit-mm-per-prompt '{"image":0,"video":0}'` | **Both** keys are needed — see §0.2 |
| `--tensor-parallel-size 2` | 17.98 GiB of bf16 weights do not fit one 14.6 GiB A16 |
| `--max-model-len 8192` | 4096 is too small for the triage prompt — see §0.3 |
| `TRITON_CACHE_DIR` under home | Culls wipe the ephemeral Triton cache |

**Wait for `Application startup complete.`** — this vLLM version's wording.
Earlier notes here said `Uvicorn running on http://127.0.0.1:8000`; that now
reads `Starting vLLM server on http://127.0.0.1:8000`, a few lines earlier.
Ctrl+C stops `tail` only. Startup is ~30 s, and the hundreds of `no matching
PunicaWrapper ... will be ignored` warnings along the way are expected (§0.2).

```bash
curl -s http://localhost:8000/v1/models
# must list Qwen/Qwen3.5-9B and herhealth;
# herhealth's "parent" must be "Qwen/Qwen3.5-9B" — that is the adapter attaching

curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "herhealth",
    "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
    "max_tokens": 64,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

The first generation compiles LoRA kernels on demand and can take 1–3 minutes;
the second is fast. A normal sentence with `"finish_reason": "stop"` means the
serve is healthy. Then re-run with a real symptom question and `"max_tokens":
512` to confirm it holds under a longer generation.

**If a model or the adapter is missing**, `bash scripts/serve-models.sh check`
says which. For a missing model, `start` prints the command that fetches it;
for the adapter, see "Restoring after a wipe" at the top. Keep the
JupyterLab tab open — idle culling is what "I closed the machine" usually is.

### Stop it

```bash
kill "$(cat /home/jovyan/vllm.pid)"     # or re-run block A
```

---

## 0.1 The `!!!!!!!` bug — root cause, fixed 2026-09-09

**Symptom — two faces of one cause:**

- Chat completions returned a solid run of `!!!!!!!!!!!` instead of text.
- On other starts the engine deadlocked *before* binding `:8000`. One run sat
  **23 hours** with both `VLLM::Worker_TP` processes at ~102% CPU and both GPUs
  at 100% utilisation, printing `No available shared memory broadcast block
  found in 60 seconds` once a minute. That message is the EngineCore *writer*
  reporting its TP workers never came back to read — a downstream symptom, not
  the cause. It is not about `/dev/shm`.

**Cause.** vLLM's **custom all-reduce** kernel combines activations across the
two GPUs and needs CUDA peer-to-peer access. P2P is broken on these A16s —
which is exactly why this runbook already had to set `NCCL_P2P_DISABLE=1` to
stop an NCCL hang. vLLM decides whether to use custom all-reduce from a cached
capability probe under `~/.cache/vllm`; when that probe is stale or wrong, the
kernel stays enabled, reduces across a link that does not work, and every
layer's output is silently corrupted. By the final layer the logits are NaN,
and `argmax` over an all-NaN tensor returns index **0** — which in Qwen's
byte-level BPE vocabulary is the character `!`. Hence `!!!!!!!`. The same
broken collective explains the startup deadlock: a stuck NCCL collective
busy-waits, so CPU and GPU both read as pegged while nothing progresses.

**Fix.** `--disable-custom-all-reduce`, plus `rm -rf ~/.cache/vllm` once to
drop the stale probe. Confirm in the log:

```
Using ['PYNCCL'] all-reduce backends (in dispatch order) for group 'tp:0'
```

`CUSTOM` must **not** appear in that dispatch list. With the flag set, engine
init took 15.98 s and `herhealth` answered `"Hello! How can I assist you
today?"` with `finish_reason: "stop"`.

**Ruled out — do not re-investigate:**

- *The adapter.* Every tensor in `herhealth-lora-v2` is `float32`, zero NaN,
  zero Inf, max |weight| ≈ 0.41 (typical 0.03–0.08). Healthy.
- */dev/shm size.* 1008 GB on this pod, not the 64 MB a Kubernetes default
  would give — despite the `shm_broadcast` message naming shared memory.
- *Insufficient VRAM.* 8.53 GiB per rank for weights, 3.98 GiB KV cache, on
  14.6 GiB cards. Comfortable.
- *`Available RAM: 8.32 GiB` / "auto-prefetch is disabled".* That is **system**
  RAM, not GPU, and it only skips a load-path optimisation. Harmless.

## 0.2 The base model is a multimodal hybrid, not a text model

`Qwen/Qwen3.5-9B` loads as **`Qwen3_5ForConditionalGeneration`**: a vision
tower plus a *hybrid* attention stack. The log says so four ways —
`visual.blocks.*` modules; `Setting attention block size to 528 tokens to
ensure that attention page size is >= mamba page size`; Qwen3VL video
processing warnings; and `qwen_gdn_linear_attn` (gated DeltaNet linear
attention) kernel selection. Only every fourth layer is full attention.

Three consequences:

1. **`--limit-mm-per-prompt` must cap `video` as well as `image`.** With only
   `{"image":0}` the engine still profiled one video item at maximum feature
   size and reserved a 12,288-token encoder cache. With both at 0 the log
   prints `All limits of multimodal modalities supported by the model are set
   to 0, running in text-only mode.` — that line is the check.
2. **The hundreds of `no matching PunicaWrapper is found; visual.blocks.N…
   will be ignored` warnings are expected and correct.** That is vLLM declining
   to apply LoRA to vision modules the adapter never targeted. The line that
   matters is `Loaded new LoRA adapter: name 'herhealth'`.
3. **The adapter's module list corroborates the architecture — it is not a
   defect.** It carries `mlp.{gate,up,down}_proj` on all 32 layers, but
   `self_attn.{q,k,v,o}_proj` on layers **3, 7, 11, 15, 19, 23, 27, 31** only —
   the full-attention layers. The rest are linear-attention blocks with no
   attention projections to adapt. Keys are prefixed
   `base_model.model.model.language_model.*`, so training targeted the text
   tower correctly.

`CLAUDE.md`, `README.md` and `dev-vllm-lora-endpoint.md` all describe this base
as a plain text model. That is wrong, and it misdirected tuning on this box for
two sessions.

## 0.3 Why `max_model_len` is 8192, not 4096

The triage system prompt is **~3,200–3,600 tokens before retrieval**:
`DEFAULT_SYSTEM_PROMPT` (5,607 chars) + feature vocabulary (872) + all 16 red
flags rendered verbatim every turn (2,873) + `_JSON_SHAPE_INSTRUCTION` (3,353)
= 12,709 characters, then `k=8` retrieved passages, the chat template, and the
conversation history on top.

At 4096 there was no room left to generate. `services/backend`'s
`_chat_completions_body` sends no `max_tokens`, so vLLM defaults to "whatever
remains in the window" — a few dozen tokens, far too few for a
`TriageDecision`. That fails validation, and
`_decide_via_chat_completions` retries with *more* prompt appended each time.

8192 costs almost nothing here: KV cache holds **183,947 tokens = 22.45×
concurrency at 8192**.

---

The uni GPU box is reached through **JupyterHub**, not SSH: your session is a
container (`HOSTNAME=jupyter-group-digi2026-g1`) whose only inbound route from
the internet is the hub's URL prefix `/user/<hub-username>/`. Two things follow,
and both differ from [dev-vllm-lora-endpoint.md](dev-vllm-lora-endpoint.md) and
[friend-pc-vllm-setup.md](friend-pc-vllm-setup.md):

1. **The container filesystem is wiped on every restart. Only the home
   volume survives.** That is what erased the last setup. Everything
   expensive — the venv and the ~20 GB of weights — has to live under
   `/home/jovyan`, and `HF_HOME` has to point there or Hugging Face
   re-downloads into the ephemeral layer.
2. **You cannot open a port to the world.** Reach vLLM through
   `jupyter-server-proxy` (§5A, authenticated, nothing extra to install) or a
   Cloudflare quick tunnel (§5B, public URL, so vLLM needs `--api-key`).

`scripts/serve-models.sh` starts and stops the processes. It does not install
vLLM or download models. The commands for that are under "Restoring after a
wipe" at the top; §2–§4 below explain why each step is needed, but their
paths (`vllm-env`, `/home/jovyan/models/`) are the old layout.

Everything in [dev-vllm-lora-endpoint.md §6](dev-vllm-lora-endpoint.md#6-hard-constraints--do-not-design-past-these)
still binds: the adapter is **phrasing-only**, no weights load inside the
backend process, and no surfaced output may be framed as a diagnosis.

---

**Superseded 2026-10-11: the window is now 32,768.** vLLM's log of the
2026-10-11 serve shows 3.98 GiB per GPU left for the token cache, holding
234,599 tokens at this window, so 7.16 full-length requests fit at once.
(At the old 8192 window the same memory held 183,947 tokens.) That depends
on `--enforce-eager`; with CUDA graphs enabled an earlier run had 1.71 GiB
and 78,568 tokens. The reasoning above for why 4096 is too small
still holds.

## 1. Check what the VM gives you

JupyterLab → File → New → Terminal:

```bash
nvidia-smi                    # GPU present? free VRAM? who else is on the card?
df -h /home/jovyan            # need ~45 GB free: weights ~20 GB + venv ~10 GB
mount | grep -E ' /home| /home/jovyan'   # a separate mount = a real persistent volume
free -g
python -V                     # 3.10+ for current vLLM
curl -sI https://huggingface.co | head -1                 # outbound internet?
jupyter server extension list 2>&1 | grep -i proxy        # decides §5A vs §5B
```

**If `nvidia-smi` fails or shows under ~20 GB free VRAM, stop here.** Qwen3.5-9B
in bf16 will not serve. Run the app on `HERHEALTH_TRIAGE_MODE=openrouter`
instead — it works fully without the adapter, on the base model.

**If `/home/jovyan` is not a separate mount**, nothing persists and §2's whole
premise fails. Ask the admin which path is on a volume and set `PERSIST` in the
script to that path.

## 2. Prove what actually persists before trusting it

Cheap, and it saves a second 20 GB download:

```bash
date > /home/jovyan/persistence-probe.txt
```

Restart your server (File → Hub Control Panel → Stop My Server, then Start),
reopen a terminal, and `cat /home/jovyan/persistence-probe.txt`. If the date is
still there, §3's layout is safe. If it is gone, only `HERHEALTH_TRIAGE_MODE=openrouter`
is realistic on this box — re-downloading 20 GB per session is not a workflow.

## 3. The persistent layout

| Path | Holds | Cost to lose |
|---|---|---|
| `/home/jovyan/vllm-env/` | the venv (vllm, torch, CUDA wheels) | ~10 min reinstall |
| `/home/jovyan/models/herhealth-lora-v2/` | local copy of the adapter (what 2026-09-06 served) | re-download from HF |
| `/home/jovyan/.cache/huggingface/` | base weights + the adapter if not under `models/` | ~20 GB re-download |
| `/home/jovyan/.cache/huggingface/token` | the HF login | re-login |
| `/home/jovyan/vllm.log`, `vllm.pid` | last run's log and pid | nothing |

`HF_HOME` is the single control that keeps the weights out of the ephemeral
layer, so pin it in `.bashrc` rather than exporting it per session:

```bash
grep -q HF_HOME /home/jovyan/.bashrc || \
  echo 'export HF_HOME=/home/jovyan/.cache/huggingface' >> /home/jovyan/.bashrc
export HF_HOME=/home/jovyan/.cache/huggingface
```

## 4. Install and pre-download (once, then only after a wipe)

```bash
python -m venv /home/jovyan/vllm-env
source /home/jovyan/vllm-env/bin/activate
pip install --upgrade pip
pip install vllm huggingface_hub
huggingface-cli login     # a READ token; it lands in $HF_HOME and persists
```

Download the weights as an explicit, resumable step rather than letting the
first `vllm serve` do it — an interrupted server start is much harder to tell
apart from a broken one than an interrupted download:

```bash
huggingface-cli download Qwen/Qwen3.5-9B
huggingface-cli download herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2
```

The adapter repo (<https://huggingface.co/herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2>)
is **private, not gated** — the token needs read access to the `herhealthgpt`
org. Never paste that token into this repo, a notebook, or a cell output; it
lives only in `$HF_HOME/token` on the VM.

Both downloads are re-runnable: they verify the cache and exit in seconds when
it is already complete. That is the "did the wipe get my weights?" check.

## 5. Start the server, detached

**The command lives in §0.B — use that, not a variant.** It is the only one
verified on this hardware, and the three flags added on 2026-09-09
(`--disable-custom-all-reduce`, `"video":0`, `--max-model-len 8192`) are each
load-bearing; dropping any of them reproduces a failure documented in
§0.1-§0.3. This section covers only what §0 assumes.

A JupyterLab terminal dies with its tab, taking vLLM with it — hence `nohup`
and the pidfile. Prefer the local adapter path when it exists; fall back to the
HF repo:

```bash
ADAPTER=/home/jovyan/models/herhealth-lora-v2
[ -d "$ADAPTER" ] || ADAPTER=herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2
echo "$ADAPTER"
```

`--max-lora-rank 16` matches the adapter's `r=16` (CLAUDE.md, confirmed against
`adapter_config.json`). Port **8000** is the verified bind. `127.0.0.1` is
deliberate: the proxy and the tunnel both reach it locally, and `0.0.0.0` would
expose an unauthenticated model to every other pod on the cluster network.

On `max_model_len`: **8192** is the working value and the reasoning is in §0.3.
16384 remains the eventual triage target, but the base model's large native
context makes vLLM reserve KV cache for the full declared length, so raise it
only while watching `Available KV cache memory` in the log.

Stop it with `kill $(cat /home/jovyan/vllm.pid)` or the §0.A `pkill` block.

**Idle culling kills this.** JupyterHub stops servers with no activity, and a
stopped server takes vLLM down with it — the likeliest cause of the wipe you
just hit. Keep a JupyterLab tab open while testing, and ask the admin whether
your server can be exempted from the culler if you need longer runs.

## 6. Reach it from your laptop

### A. jupyter-server-proxy (preferred, if §1 showed it installed)

Any local port is served at `https://<hub-host>/user/<hub-username>/proxy/<port>/`,
authenticated by JupyterHub, with nothing exposed publicly. `<hub-host>` is the
host you type in the browser to open JupyterLab — **not** the container's
`JUPYTER_SERVER_URL` (`http://jupyter-group-digi2026-g1:8888/...`), which is an
internal cluster name and unreachable from outside. The 2026-09-06 session's
hub user was `group-digi2026-g1`.

Mint a token: browser → `https://<hub-host>/hub/token` → **Request new API
token**. It is shown once.

```powershell
curl.exe -H "Authorization: Bearer <TOKEN>" `
  https://<hub-host>/user/<hub-username>/proxy/8000/v1/models
```

JupyterHub accepts the `Bearer` scheme, and vLLM — started without
`--api-key` — ignores the header it receives, so one header satisfies both
hops. That is exactly what `VllmReasoningClient` sends when
`HERHEALTH_VLLM_API_KEY` is set (`services/backend/src/herhealth_backend/triage/clients.py`).

If the port is up locally but the proxy 404s, try the absolute form:
`/user/<hub-username>/proxy/absolute/8000/v1/models`.

### B. Cloudflare quick tunnel (if there is no server-proxy)

This publishes the endpoint at a public `https://<random>.trycloudflare.com`
URL, so add `--api-key $(openssl rand -hex 24)` to the §5 command first and
restart — otherwise anyone with the URL can use the GPU.

```bash
cd /home/jovyan
curl -L -o cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared
nohup ./cloudflared tunnel --url http://127.0.0.1:8000 > /home/jovyan/tunnel.log 2>&1 &
grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /home/jovyan/tunnel.log
```

The URL changes on every restart. This is an egress tunnel out of university
infrastructure — confirm it is acceptable to whoever runs the server before
relying on it.

### C. SSH, if the department gives you a shell on the GPU node

Then this reduces to [dev-vllm-lora-endpoint.md](dev-vllm-lora-endpoint.md):
`ssh -L 8002:localhost:8000 <user>@<node>`, and the URL on the laptop is
`http://127.0.0.1:8002` (local 8002 forwarded to the pod's 8000, because this
laptop's FastAPI already owns 8000).

## 7. Wire the backend to it

`infra/envs/backend.env` on your machine:

```env
HERHEALTH_TRIAGE_MODE=vllm
# §6A:
HERHEALTH_VLLM_URL=https://<hub-host>/user/<hub-username>/proxy/8000
HERHEALTH_VLLM_API_KEY=<jupyterhub token>
# §6B instead:
# HERHEALTH_VLLM_URL=https://<random>.trycloudflare.com
# HERHEALTH_VLLM_API_KEY=<the --api-key you generated>
# §6C (SSH tunnel campus:8000 → laptop:8002):
# HERHEALTH_VLLM_URL=http://127.0.0.1:8002
HERHEALTH_VLLM_MODEL=herhealth
OPENROUTER_API_KEY=sk-or-...            # fallback for when the VM is culled
HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001
```

No trailing slash on `HERHEALTH_VLLM_URL` — the client appends
`/v1/chat/completions` itself. In `vllm` mode the backend tries the VM first
and falls back to OpenRouter's **base** model on connect/timeout/502-504
(`FallbackReasoningClient`), so a culled server degrades rather than breaks.
Restart the backend after editing.

**Retrieval stays on your machine.** `services/model` on :8001 (bge-m3) is a
separate process, needs no GPU, and the backend reaches it over HTTP either
way — do not move it to the VM to "keep things together".

## 8. Verify end to end

```powershell
curl.exe -H "Authorization: Bearer <TOKEN>" https://<hub-host>/user/<hub-username>/proxy/8000/v1/models
```

then browser → http://localhost:3000/chat, ask *"I've had irregular periods for
three months"*, and watch the backend log for either a vLLM response or
`vllm unreachable … falling back to openrouter`.

Expect the quirks recorded in
[dev-vllm-lora-endpoint.md §5](dev-vllm-lora-endpoint.md#5-known-quirks-to-design-around-not-work-around-later):
thinking blocks unless `enable_thinking:false` (the backend already sends it),
occasional code-switching, and register variance between identical questions.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Everything gone after a break | Server culled, container reset. Run `bash scripts/serve-models.sh check`, restore whatever it reports missing (§2–§4), then `start all`. |
| Weights re-downloading every session | `HF_HOME` unset in this shell — it went to the ephemeral `~/.cache`. See §3. |
| `Disk quota exceeded` mid-download | Same cause, or the home volume is genuinely too small (§1). |
| 401 from Hugging Face | Token lacks read access to the private `herhealthgpt` repo — `huggingface-cli login` again. |
| 403 from the proxy URL | JupyterHub token expired or wrong scope — mint a new one at `/hub/token`. |
| Proxy 404s but `127.0.0.1:8000` works | Try `/user/<hub-username>/proxy/absolute/8000/…`. |
| `localhost:8002` fails on the VM | The working bind is **8000**. |
| CUDA OOM at startup | Another job holds the card — `--gpu-memory-utilization 0.45`, or `--max-model-len 8192`. |
| Adapter concludes without asking | Known and expected — it is phrasing-trained only, not retrained on multi-turn data. |
| **Responses are `!!!!!!!`** | **Custom all-reduce corrupting TP output. `--disable-custom-all-reduce` + `rm -rf ~/.cache/vllm`. Full explanation in §0.1.** |
| **Startup hangs, `No available shared memory broadcast block found in 60 seconds` repeating, both GPUs at 100%** | **Same cause as `!!!!!!!` — see §0.1. Not `/dev/shm`, which is 1008 GB here. Kill and restart with the §0.B command.** |
| Hundreds of `no matching PunicaWrapper ... will be ignored` | Expected. vLLM skipping LoRA on the vision tower — see §0.2. |
| `400` / prompt-too-long from the backend, or truncated JSON | `max_model_len` too small for the triage prompt — see §0.3. |
| `Available RAM: 8.32 GiB`, "auto-prefetch is disabled" | System RAM, not GPU. Harmless; the weights still load. |
