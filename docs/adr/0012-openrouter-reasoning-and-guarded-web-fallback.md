---
status: proposed
---

# API-hosted reasoning model, and a guarded web-search fallback

> **Proposed, not accepted.** Written from an in-session decision, not
> supervisor/mentor sign-off — same gate [ADR 0011](0011-controller-free-triage.md)
> named for itself before it was accepted. This ADR **extends** 0011; it does
> not reopen 0011's own decision to remove the deterministic controller. Do
> not treat anything below as built until the migration checklist here says so.

## Context

[ADR 0011](0011-controller-free-triage.md)'s migration checklist step 4 calls
for standing up `services/model` (self-hosted vLLM: base model + `bge-m3` +
the QLoRA adapter) and an `httpx`-based `ReasoningClient` / `RetrievalClient`
pair for `TriageAgent`. Two things learned since that checklist was written
change how step 4 is actually built, without changing what it owes the rest
of the ADR:

1. **Self-hosting the reasoning model on rented GPU compute is not viable
   right now.** A manual smoke test on a rented vast.ai instance (see
   [`docs/runbooks/dev-vllm-lora-endpoint.md`](../runbooks/dev-vllm-lora-endpoint.md))
   confirmed the adapter serves correctly, but the per-hour GPU cost is not
   sustainable for iterative development. `Qwen/Qwen3.5-9B` is available
   API-hosted (OpenRouter, $0.10/M input + $0.15/M output tokens at time of
   writing) — three orders of magnitude cheaper for the token volumes this
   project needs during development.
2. **The team has already told mentors there is no deterministic Python
   controller in the shipped design.** ADR 0011 already decided this; it is
   restated here only because it constrains this ADR's fallback design in
   §3 — a deterministic escape hatch is not an option to reach for when a
   guardrail is needed.

A live test (base model, no adapter, via OpenRouter, the real
`agent.DEFAULT_SYSTEM_PROMPT`, no retrieved context) surfaced a finding this
ADR's guardrails respond to directly: asked a single ambiguous question, the
model **fabricated citations** — "(American College of Obstetricians and
Gynecologists, 2022)", "(Mayo Clinic, 2023)" — to sources that are not among
this project's five approved ones, because it was instructed to always cite
something and had nothing real available. It also produced a decision that
does not fit `TriageDecision`'s shape at all: a full `CONCLUDE` (action code
and all) followed by an `ASK`-shaped question tacked on the end, when the
schema requires exactly one or the other. Both findings shaped the decisions
below.

## Decision

Three changes to ADR 0011's step 4, all reversible, none touching the
schema or the controller-removal decision itself:

1. **`ReasoningClient` is implemented against OpenRouter's chat-completions
   API**, not a self-hosted vLLM server, for both the base model and (once
   retrained) the adapter. Structured output is requested via OpenRouter's
   `response_format` JSON-schema parameter, passing
   `TriageDecision.model_json_schema()` directly — the same guided-decoding
   contract ADR 0011 already specifies, just enforced by a different server.
   Pydantic re-validates on receipt regardless, per `agent.py`'s existing
   docstring rationale.
2. **`RetrievalClient` calls a small, CPU-only `services/model` over HTTP**,
   as ADR 0011 already required — the only change is that this service does
   *not* also serve the reasoning model. It loads a `PassageIndex` (built by
   the existing `python -m herhealth_data.cli index` — not yet wired into the
   root `Makefile`; that gap predates this ADR) and exposes one endpoint that
   embeds the query with `SentenceTransformerEmbedder` (`bge-m3`, CPU) and
   returns `RetrievedPassage` hits. A few thousand short sentences on CPU is
   the case `index.py`'s own docstring says brute-force cosine search is
   built for; nothing here needs a GPU.
3. **A bounded, logged web-search fallback fires only when retrieval returns
   nothing usable** (empty, or every hit below a minimum score) — see §3 for
   the exact rules. This is new; ADR 0011 did not describe it, and the
   default before this ADR would have been "the model answers ungrounded,"
   which the OpenRouter test above just showed produces fabricated citations.

## Why not just retrain first, or just add more retrieval

Both were considered and are not what this ADR does:

- **Retraining the adapter** (ADR 0011's own actual fix for ask-vs-conclude
  collapsing to always-conclude) is unaffected by anything here and remains
  migration-checklist item 5, not started. Nothing in this ADR is a substitute
  for it — the base model's OpenRouter test above still produced a decision
  that doesn't fit the schema's ask/conclude exclusivity, which retraining
  targets and this ADR does not.
- **More retrieval does not fix a citation the model invented from nothing.**
  The fabrication happened *because* no real passage was available to cite,
  not because retrieval was configured wrong. A wider search radius over the
  same five-source corpus does not manufacture a source that was never
  ingested. Something has to be the answer to "the corpus has nothing here" —
  §3 is this ADR's answer, chosen instead of silent ungrounded generation.

## §3. The web-search fallback, exact rules

Fires only when `RetrievalClient.search()` returns zero hits, or every hit
scores below a minimum threshold (`min_score`, tunable, defaulting to the
same conservatism as `weights.yaml`'s tie-breaks: prefer the fallback firing
too often over an unmoored citation slipping through).

1. **Domain-restricted, not open web.** Only the five domains in
   `sources.yaml` (medlineplus.gov, nichd.nih.gov, womenshealth.gov, cdc.gov,
   nhs.uk) are eligible targets. No general web search API, no arbitrary URL.
2. **`RobotsPolicy` and existing licence exclusions apply identically, live.**
   The same check `services/data`'s ingestion path already runs against a
   URL's live `robots.txt`, and the same `/ency/` MedlinePlus exclusion,
   gate a live fetch exactly as they gate a batch one. NHS content fetched
   this way is `citable_only`: quotable with attribution in that one
   response, never persisted as a reusable passage (rule 3 makes this moot
   for NHS specifically, since nothing from this path is persisted anyway).
3. **Nothing fetched this way enters `passages.parquet` or the reviewed
   index.** It is used once, to ground the single response that triggered
   it, then logged to a review queue (a new, append-only log — table or file,
   implementation detail left to step 4 below) as a candidate for a properly
   authored, second-reviewed `evidence_batches/*.yaml` entry. This is the
   existing "model proposes, a human disposes" discipline (`propose.py`),
   applied to a source instead of a row, deferred to after the response
   instead of blocking it.
4. **Provenance quality caps the action code.** A `CONCLUDE` decision
   grounded *only* in a fallback-fetched passage (no reviewed-evidence
   citation, no `red_flag_id`) may not resolve to `SELF_CARE`. Floor it at
   `ROUTINE_APPOINTMENT`, or the decision should be `ASK` instead. This
   extends `CLAUDE.md`'s existing "the bar for `SELF_CARE` is strictly higher
   than for `ROUTINE_APPOINTMENT`" rule along a new axis — provenance, not
   only evidence strength — and is enforced the same way that rule already
   is: a check the caller runs on the decision before it reaches a user, not
   a request made of the model in the prompt alone.
5. **It cannot introduce a new `matching_conditions` value.** The schema's
   closed vocabulary (19 authored conditions) is unaffected by what a live
   page says. A fallback-grounded decision may inform `rationale`'s prose;
   it may not name a condition `conditions.yaml` does not contain — the
   schema already refuses this structurally, and this rule changes nothing
   about the schema, it just states plainly that the fallback path does not
   get an exception.
6. **Every response produced via this path is tagged.** A boolean
   (`grounded_in_reviewed_kb: bool` or equivalent, exact field left to
   implementation) is stored alongside the persisted decision, so this path's
   outcomes are separately auditable and reportable — not silently
   indistinguishable from a fully reviewed answer, matching `CLAUDE.md`'s
   standing rule to state limitations wherever results are reported.

**What these six rules do not remove, stated plainly rather than left
implicit**: a response can still go out before any human has read the page it
cites. Rules 3–6 contain the consequences of that (it cannot become permanent
trusted content, cannot unlock the safest action code, cannot invent a
condition, and is auditable after the fact) — none of them make the citation
reviewed *before* the user sees it. That gap is accepted here the same way
ADR 0011 accepted its own under-triage risk: named, not softened, and revisited
if evidence says it should be.

## What's new, what's kept, what's gone

**New:**

- `services/model/` — a CPU-only FastAPI service, `bge-m3` embeddings only
  (no reasoning model served locally). One endpoint: query in, `RetrievedPassage`
  list out.
- `OpenRouterReasoningClient` (`services/backend/.../triage/clients.py`,
  not yet built) — implements `ReasoningClient` against OpenRouter's
  chat-completions API with structured output.
- `HttpRetrievalClient` (same file) — implements `RetrievalClient` against
  `services/model`, with the web-search fallback of §3 as a second path
  inside `search()` when the primary path returns nothing usable.
- A fallback-fetch review-queue log — new, append-only, read by whoever
  authors the next evidence batch.

**Kept, unchanged:** everything ADR 0011 already kept — the seven knowledge
files, `TriageDecision`'s schema and its validators, `TriageAgent`'s loop,
`bge-m3` as the embedding model (ADR 0010).

**Explicitly not affected by this ADR:** the retraining plan. The adapter
still stays phrasing-only, per `CLAUDE.md`, until it is retrained on
multi-turn data and that retrain is reviewed. Swapping `OpenRouterReasoningClient`
from the base model to the adapter (once retrained) is a one-line model-name
change in the client, not an architecture change — that is the point of the
seam already being a `Protocol`.

## Migration checklist

1. `services/model`: CPU embedding service (`bge-m3`, `SentenceTransformerEmbedder`),
   one search endpoint. **Not started.**
2. `OpenRouterReasoningClient`: implements `ReasoningClient`, structured
   output against `TriageDecision.model_json_schema()`, base model first.
   **Not started.**
3. `HttpRetrievalClient`: implements `RetrievalClient` against step 1, plus
   the §3 fallback (domain allowlist, `RobotsPolicy` reuse, provenance cap on
   `SELF_CARE`, tagging, review-queue logging). **Not started.**
4. Wire `TriageAgent` in `services/backend` to the two real clients above,
   replacing `ScriptedReasoningClient` for anything beyond tests. **Not
   started.**
5. A runnable end-to-end demonstration (script or route) exercising a full
   consultation against the real clients, so this ADR's claims are checked
   against a real run before being trusted. **Not started.**
6. Run `python -m herhealth_data.cli index` for the first time in this repo
   (`build/index` does not exist yet) so step 3 has a real corpus to query.
   Needs the `retrieval` extra (`sentence-transformers`) and downloads
   `bge-m3` weights on first run — a one-time, CPU-feasible cost given the
   corpus is a few thousand sentences, but a real network call, so per
   `CLAUDE.md`'s working convention this is asked for explicitly before it is
   run, not bundled silently into another step. **Not started.**
7. Supervisor/mentor review; flip this ADR's status to `accepted`. **Not
   started.**

## Risk register

Additive to ADR 0011's, not a replacement for it:

- **Retraining is still not done.** Every risk ADR 0011's own register named
  about the untrained adapter deciding ask-vs-conclude is unchanged by this
  ADR. Using the base model instead of the untrained adapter is not a fix for
  that risk — the OpenRouter test in this ADR's Context shows the base model
  has its *own* version of the same shape problem (concluding and asking at
  once).
- **A fallback response is unreviewed before it reaches a user.** Named
  without softening in §3's closing paragraph. This is the one place this ADR
  knowingly accepts a gap the rest of the project's design otherwise refuses
  to accept anywhere else (every other row, everywhere, is reviewed before
  it is trusted).
- **OpenRouter is a third-party dependency this project does not control.**
  Pricing, model availability, and structured-output behaviour can change
  without this repo's knowledge. `ReasoningClient` being a `Protocol` is the
  existing mitigation — a different provider is a new implementation of the
  same interface, not a rewrite.
