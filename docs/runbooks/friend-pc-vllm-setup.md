---
status: runbook
---

# Runbook: vLLM + LoRA on a friend's GPU PC (UltraViewer / remote desktop)

Use this when you are sitting at a friend's Windows PC over UltraViewer and
cannot copy-paste from their terminal. **Transfer this file** (or
`scripts/setup-friend-vllm.ps1` from the repo) using UltraViewer's file
transfer — do not rely on the clipboard.

Your machine runs the app (backend, frontend, RAG on :8001). The friend's PC
runs **only** the GPU model on port **8002**. Retrieval stays on your machine.

---

## Before you start

| Check | Command to type manually |
|-------|--------------------------|
| NVIDIA GPU present | `nvidia-smi` |
| At least 24 GB VRAM | read the top-right of `nvidia-smi` output |
| Internet works | open https://huggingface.co in a browser |

**vLLM does not run on Mac or on CPU-only PCs.** If `nvidia-smi` fails, stop
here — use OpenRouter only (`HERHEALTH_TRIAGE_MODE=openrouter`).

---

## Step 1 — Install WSL2 (Windows only, one-time)

vLLM is Linux-only. On Windows, use **WSL2 Ubuntu**.

1. Open **PowerShell as Administrator**
2. Type exactly (press Enter after each line):

```
wsl --install -d Ubuntu
```

3. Reboot when asked
4. After reboot, open **Ubuntu** from the Start menu and create a username/password

---

## Step 2 — Inside Ubuntu (WSL), install Python + vLLM

Open the **Ubuntu** terminal. Type these lines one at a time (wait for each to finish):

```
sudo apt update
sudo apt install -y python3.12-venv python3-pip git
python3.12 -m venv ~/vllm-env
source ~/vllm-env/bin/activate
pip install --upgrade pip
pip install vllm huggingface_hub
```

This takes 10–20 minutes (large download).

---

## Step 3 — Hugging Face login

You need a token with read access to the private adapter repo
`herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`.

1. On your phone or laptop, create a token at https://huggingface.co/settings/tokens
2. On the friend's PC, in the same Ubuntu terminal:

```
source ~/vllm-env/bin/activate
huggingface-cli login
```

3. When prompted, **type** the token (it will not show as you type — normal)
4. Press Enter

---

## Step 4 — Start the model server

Still in Ubuntu, with the venv activated:

```
source ~/vllm-env/bin/activate
vllm serve Qwen/Qwen3.5-9B --enable-lora \
  --lora-modules herhealth=herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2 \
  --max-lora-rank 16 --max-model-len 16384 \
  --host 0.0.0.0 --port 8002
```

First run downloads ~20 GB of weights — can take 30–60 minutes.

**Leave this terminal open.** When ready you should see something like
`Uvicorn running on http://0.0.0.0:8002`.

---

## Step 5 — Verify on the friend's PC

Open a **second** Ubuntu terminal:

```
curl http://localhost:8002/v1/models
```

You should see JSON listing `Qwen/Qwen3.5-9B` and `herhealth`.

---

## Step 6 — Let your machine reach the GPU PC

### Same home Wi‑Fi (easiest)

1. On the friend's PC, open **Command Prompt** (Windows) and type:

```
ipconfig
```

2. Note the **IPv4 Address** (e.g. `192.168.1.42`)
3. On **your** machine, test:

```
curl http://192.168.1.42:8002/v1/models
```

If it fails, allow port 8002 in Windows Firewall on the friend's PC
(Windows Security → Firewall → Advanced → Inbound rule → TCP 8002).

### Different networks

Use **Tailscale** (free) on both PCs — then use the friend's Tailscale IP
instead of `192.168.x.x`.

---

## Step 7 — Your backend config

In `infra/envs/backend.env` on **your** machine:

```env
# Test OpenRouter first:
HERHEALTH_TRIAGE_MODE=openrouter
OPENROUTER_API_KEY=sk-or-...
HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001

# When friend's GPU is ready, switch to vLLM + OpenRouter fallback:
HERHEALTH_TRIAGE_MODE=vllm
HERHEALTH_VLLM_URL=http://192.168.1.42:8002
HERHEALTH_VLLM_MODEL=herhealth
OPENROUTER_API_KEY=sk-or-...
HERHEALTH_MODEL_SERVICE_URL=http://127.0.0.1:8001
```

Restart the backend after changing env.

**Behaviour in `vllm` mode:**

1. Tries friend's GPU (`HERHEALTH_VLLM_URL`) with the LoRA adapter
2. If unreachable (PC off, firewall, tunnel down) → **automatically falls back to OpenRouter**
3. RAG (`services/model` on :8001) always runs on your machine

---

## Step 8 — Test chat

1. Your machine: retrieval service running (`uv run python -m herhealth_model`)
2. Your machine: backend + frontend running
3. Browser → http://localhost:3000/chat
4. Ask: *"I've had irregular periods for three months"*
5. Check backend logs — you should see either vLLM responses or a
   `falling back to openrouter` warning

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `nvidia-smi` not found in WSL | Install NVIDIA WSL drivers on Windows host |
| CUDA OOM | Close other GPU apps; need 24 GB+ VRAM |
| `401` from Hugging Face | Re-run `huggingface-cli login` with a valid token |
| Your PC cannot reach :8002 | Firewall, wrong IP, or friend on a different network — use Tailscale |
| Model answers but no citations | RAG service not running on your :8001 |
| Adapter jumps straight to conclusion | Known limitation — adapter not retrained for ask-vs-conclude yet |

---

## Safety reminder

The current LoRA adapter is **phrasing-trained only**. Until it is retrained on
multi-turn data, treat vLLM output as experimental. OpenRouter fallback uses
the **base** model, not the adapter — behaviour will differ between the two.
