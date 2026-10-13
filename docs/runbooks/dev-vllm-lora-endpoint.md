---
status: runbook
---

# Runbook: connecting to the herhealth LoRA dev endpoint

> **Retrieval changed on 2026-10-12 ([ADR 0017](../adr/0017-qwen3-embedding-and-reranker-on-langchain.md)).**
> `services/model`, port 8001, `bge-m3`, `HERHEALTH_MODEL_SERVICE_URL`,
> `build-index.yml`, `pin-bge-m3.py` and `publish-index.sh` no longer exist.
> The retriever runs inside the backend over an index built by `make index`,
> and calls the embedding and reranker endpoints (`HERHEALTH_EMBEDDING_URL`,
> `HERHEALTH_RERANKER_URL`). **OpenRouter and the Base / Fine-tuned selector
> were removed the same day ([ADR 0018](../adr/0018-local-models-decide-and-the-adapter-answers.md)):**
> the mode is `HERHEALTH_TRIAGE_MODE=vllm`, the base model decides and the
> adapter words informational answers. Passages below that describe the
> retrieval service, its image, the published index, OpenRouter or the
> selector are history and have not been rewritten yet.

This documents a **manually-provisioned, ephemeral dev endpoint** for the
fine-tuned adapter described in CLAUDE.md's "The fine-tuned model from our
evaluation paper" section — not a deployed service, not part of `infra/`. It
was stood up on a rented vast.ai GPU on 2026-09-01 to confirm the adapter
serves correctly under vLLM's LoRA hot-loading and to hand connection details
to whoever writes the integration code next. See also
[[adr-0011-controller-free]]-tracked issue #20, which is the broader effort
this most likely feeds — confirm that's still the right parent before filing
anything against it, this runbook doesn't assert that link formally.

**Read the constraints section before writing any code against this.** The
adapter is restricted in what it's allowed to do, and that restriction is not
optional or a suggestion — it's the direct fix for a documented safety failure
(clarification-seeking collapsing to 0.000 under fine-tuning).

---

## 1. What's being served

| | |
|---|---|
| Base model | `Qwen/Qwen3.5-9B` – a **multimodal hybrid** (vision tower; full attention only every 4th layer), not a text model. See [uni-server-vllm.md §0.2](uni-server-vllm.md). |
| Adapter | `herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2` (private HF repo), served under the name `herhealth` |
| Server | vLLM OpenAI-compatible API, `--enable-lora` |
| Host | vast.ai on-demand GPU rental, single RTX 5090 (32GB VRAM), `vastai/vllm` template |

## 2. Is the endpoint still live?

The instance from the 2026-09-01 session may or may not still be running —
vast.ai bills hourly and it may have been stopped. Check the vast.ai console
(**Instances**) first. If it's still there, skip to §4. If not, §3 re-provisions
it in a few minutes.

## 3. (if needed) Stand up a fresh instance

- [ ] Rent a GPU on [cloud.vast.ai](https://cloud.vast.ai/create/): 24GB+ VRAM
      single card, 60GB+ disk, `vastai/vllm` template if offered (ships vLLM
      preinstalled).
- [ ] Get the SSH command from the instance's key icon in the **Instances**
      tab; add your public key there if this is a new account.
- [ ] Connect with a local port-forward:
      ```
      ssh -p <PORT> root@<HOST> -L 8001:localhost:8001
      ```
- [ ] `huggingface-cli login` — needs a token with read access to
      `herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2` (private repo).
- [ ] Check nothing else already holds the port you're about to use — the
      `vastai/vllm` template auto-starts its own default model behind a Caddy
      proxy. `ss -ltnp | grep <port>` first; if the template's own vllm
      process is running and you don't need it, `kill <pid>` to free the GPU
      memory rather than fighting Caddy for the port.
- [ ] Start the server:
      ```
      vllm serve Qwen/Qwen3.5-9B --enable-lora \
        --lora-modules herhealth=herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2 \
        --max-lora-rank 16 --max-model-len 16384 \
        --limit-mm-per-prompt '{"image":0,"video":0}' --port 8001
      ```
      `--max-model-len 16384` is load-bearing, not a tuning knob you can drop:
      the base model's native 262144-token context makes vLLM try to reserve
      KV cache for the full length by default, which fails to fit a single
      24–32GB card. 16384 comfortably covers a triage turn's injected
      `red_flags.yaml` + retrieved passages + conversation history. **Never go
      below 8192** – the system prompt alone is ~3,200–3,600 tokens before
      retrieval.

      `--limit-mm-per-prompt '{"image":0,"video":0}'` was added 2026-09-09:
      the base carries a vision tower, and without **both** keys at 0 the
      engine profiles a video item and reserves a 12,288-token encoder cache
      this text-only system never uses. Look for `running in text-only mode`.

      **On any host with more than one GPU, add `--disable-custom-all-reduce`**
      unless you have confirmed GPU peer-to-peer access works. Without it,
      corrupted all-reduce produces replies of `!!!!!!!!!!!` and deadlocks
      startup – see [uni-server-vllm.md §0.1](uni-server-vllm.md).
- [ ] Verify: `curl http://localhost:8001/v1/models` should list both
      `Qwen/Qwen3.5-9B` and `herhealth`.

## 4. API contract

OpenAI-compatible `POST /v1/chat/completions` against whatever host:port the
SSH tunnel maps to locally (`localhost:8001` above). Two selectable `model`
values: the bare base model, or `herhealth` for base+adapter.

```json
{
  "model": "herhealth",
  "messages": [{"role": "user", "content": "..."}],
  "chat_template_kwargs": {"enable_thinking": false}
}
```

`GET /v1/models` is the liveness check — confirms both the tunnel and the
server are actually up before debugging anything more specific.

## 5. Known quirks to design around, not work around later

- **Thinking mode defaults on.** Without `chat_template_kwargs.enable_thinking:
  false`, `content` comes back containing a full `<think>...</think>` reasoning
  block ahead of the actual answer — confirmed **not** split into the
  response's separate `reasoning` field (it comes back `null` either way in
  this vLLM version). Always pass `enable_thinking: false` explicitly, or the
  integration must parse and strip `<think>` blocks itself before any
  downstream use of `content`.
- **Observed code-switching**: one test response inserted Chinese characters
  mid-English sentence, unprompted. Not characterized beyond one occurrence —
  don't assume output is reliably monolingual.
- **`!!!!!!!!!!!` replies mean NaN logits, not a bad prompt.** `!` is token 0
  in Qwen's byte-level BPE vocabulary, and `argmax` over an all-NaN logit
  vector returns index 0. On multi-GPU hosts the cause is vLLM's custom
  all-reduce running over a link without peer-to-peer access; fix with
  `--disable-custom-all-reduce` and `rm -rf ~/.cache/vllm`. Diagnosed
  2026-09-09 on the campus VM – [uni-server-vllm.md §0.1](uni-server-vllm.md)
  carries the evidence and the list of things already ruled out (the adapter
  is clean; `/dev/shm` is not implicated).
- **Register variance**: the same question asked twice produced a casual
  bullet-point answer once and a terse clinical-register answer (naming
  specific lab panels: LH/FSH ratio, prolactin, pelvic ultrasound) the other
  time. Consistent with `gold_seeds_styled.csv`'s six-register training design
  — expect this variance, don't treat one sampled response as representative.

## 6. Hard constraints — do not design past these

- **Phrasing-only. It may not decide anything.** Per CLAUDE.md: this adapter
  was trained on `gold_seeds_styled.csv`, which contains zero examples where
  the correct answer is a clarifying question — the documented cause of its
  clarification-seeking collapsing from 0.856 to 0.000. A live smoke test on
  2026-09-01 reproduced this directly: asked about three months of irregular
  periods, it jumped straight to a full differential and named specific lab
  tests to run, with no clarifying question at all. **Do not wire this
  adapter's output to choose an `action_code`, populate `TriageDecision`, or
  otherwise stand in for a triage decision.** It may only render/phrase
  content that something else has already decided, until it's retrained on
  the multi-turn data at `services/data/eval/benchmark/bootstrap_multi_turn.jsonl`
  and that retrain is reviewed.
- **No model weights load inside the backend process.** This must be called
  over HTTP from wherever it's used, the same way `services/backend` already
  calls `services/model` for embeddings — never imported or loaded in-process.
- **The system never diagnoses.** No output surfaced to a user may be framed
  as a diagnosis, in any file, string literal, or UI copy. The raw adapter
  already leans this direction unprompted (e.g. "tests to confirm the
  diagnosis") — code sitting between this model and a user needs to actively
  keep that framing out, not just relay `content` verbatim.
- **This is not the production shape.** The eventual output channel is the
  schema-constrained `TriageDecision`
  (`packages/contracts/src/herhealth_contracts/decision.py`) via vLLM guided
  decoding. This dev endpoint has guided decoding configured for neither the
  schema nor anything else — treat whatever gets built against it now as a
  phrasing/rendering prototype, not a preview of the final integration shape.

## Done when

Whoever picks this up has a working HTTP call path to this model that (a)
always disables thinking mode or strips `<think>` blocks, (b) never lets the
model's output determine urgency or action code, and (c) doesn't route model
output to a user without checking it isn't phrased as a diagnosis. Confirm
scope against issue #20 / ADR 0011's migration checklist before assuming this
should go further than a phrasing prototype.
