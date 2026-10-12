# Retrieval on LangChain with the Qwen3 embedder and reranker — design

Date: 2026-10-12. Status: draft, awaiting review.

Step 2 of three. Step 1 (the model-serving stack) is done:
`docs/superpowers/specs/2026-10-11-model-serving-stack-design.md`. Step 3 is
the LLM chain, removing OpenRouter, and connecting the EC2 backend to the
campus endpoints.

## What was decided, and by whom

Decided by Mazen Bahgat on 2026-10-11 and 2026-10-12:

- All three models (the fine-tuned Qwen3.5 chat model, `Qwen3-Embedding-4B`,
  `Qwen3-Reranker-4B`) run on the campus GPU box. The backend and frontend
  run on the EC2 instance and are given the model endpoints.
- The RAG pipeline is rewritten on LangChain.
- The `bge-m3` code and everything tied to it is deleted, including the CPU
  retrieval service and its place in the production deploy.
- Until production can reach the campus endpoints, production triage reports
  "not configured". That is accepted.
- The new pipeline is judged by an automatic recall check built from
  `evidence.csv`, on the new pipeline only, with the reranker on and off.

This supersedes ADR 0010 (bge-m3, no reranker). A new ADR records that; ADR
0010 stays in the tree, marked superseded.

## Where each part runs

| Part | Runs on | Notes |
|---|---|---|
| Embedding model | campus box, port 8003 | called over HTTP |
| Reranker model | campus box, port 8004 | called over HTTP |
| Retrieval index | beside the backend | a data file, not a model |
| Retriever code | inside the backend process | loads no model weights |
| Index build | wherever the corpus and the embedding endpoint are reachable | the campus box today |

Per query the backend sends the query text to the embedding endpoint,
searches the index locally, sends the candidates to the reranker endpoint,
and returns the top passages.

## Goals

1. Build the retrieval index with `Qwen3-Embedding-4B` through LangChain.
2. Retrieve with embed → vector search → rerank, behind the backend's
   existing `RetrievalClient` interface, so the triage agent is unchanged.
3. Remove `bge-m3`, the numpy index and the retrieval service.
4. Measure retrieval, which nothing in the repo does today.

## Rules that carry over unchanged

- **Sentence-level passages.** `make verify-quotes` depends on them.
- **Evidence statements are passages too.** Each `evidence.csv` row is
  rendered as one retrievable statement carrying `condition_id`,
  `feature_id`, `value` and `strength`.
- **Evidence statements keep reserved slots** in every result (3 of 8 today).
  They are 3% of the index and the only passages that carry a `feature_id`;
  without the reservation the model has no real feature id to ask about.
- **No NHS text in anything served.** NHS is `citable_only`.
- **The backend imports nothing from `services/data`.** The two sides share
  the on-disk index format and the `herhealth_contracts` package only.
- **No model weights load inside the backend process.**

## Part 1: the index build (`services/data`)

`herhealth_data/retrieval/passages.py` is unchanged: `Passage`,
`load_passages`, `evidence_statement_passages`, `split_sentences`.

New module `herhealth_data/retrieval/vectorstore.py`:

- Turns each `Passage` into a LangChain `Document`. `page_content` is the
  passage text. Metadata: `id`, `passage_type`, `source_id`, `slug`,
  `heading`, `citation`, `url`, `condition_id`, `feature_id`, `value`,
  `strength`.
- `url` is resolved at build time from `services/data/ingest.lock.jsonl`,
  using the logic now in `services/model/src/herhealth_model/source_urls.py`,
  which moves to `herhealth_data/retrieval/source_urls.py` with its tests.
- Embeds through `langchain_openai.OpenAIEmbeddings` pointed at the vLLM
  endpoint, with token-length checking switched off so plain text is sent.
  Documents are embedded without an instruction prefix, as the model expects.
- Builds a `langchain_community.vectorstores.FAISS` store using inner
  product over normalised vectors, which is cosine similarity.

### On-disk format

Three files in the index directory. No pickle: LangChain's own
`FAISS.save_local` pickles the document store, and unpickling executes code,
which is not acceptable for a file that is copied to a server.

| File | Content |
|---|---|
| `index.faiss` | the native FAISS index, written by `faiss.write_index` |
| `passages.jsonl` | one JSON object per line, in vector order: `text` plus the metadata fields |
| `manifest.json` | see below |

`manifest.json` fields: `format_version` (1), `embedding_model`,
`embedding_revision`, `dimensions`, `passages`, `evidence_statements`,
`contains_quote_only` (true or false), `built_at`.

The manifest model lives in `herhealth_contracts` so the builder and the
backend validate the same shape.

### Two indexes

| Index | Directory | NHS passages | Used by |
|---|---|---|---|
| served | `build/index` | never | the backend |
| authoring | `build/index-authoring` | included | the evidence-proposal tool, on the authoring machine only |

`herhealth-data index` builds the served index and refuses to write
quote-only text into it. `herhealth-data index --authoring` builds the other.
The existing `--exclude-quote-only` flag is removed: exclusion is no longer
optional for the served index.

### Commands

- `index`: as above. Needs the embedding endpoint; `--model hashing` keeps
  the offline stand-in for tests.
- `search`: queries an index by hand, embedding only.
- `propose`: ported to the new store, reading the authoring index. Its
  output format and its review gate do not change.

`make index` and `make index-authoring` are added.

## Part 2: the retriever (backend)

New module `herhealth_backend/triage/retrieval.py`. It reads the three files
above, rebuilds a LangChain FAISS store from them, and exposes
`LangChainRetrievalClient`, which satisfies the existing protocol:

```python
def search(self, query: str, *, k: int = 8) -> list[RetrievedPassage]: ...
```

Flow for one call:

1. **Query text.** Prefixed with the instruction `Qwen3-Embedding` expects on
   queries: `Instruct: Given a question about women's reproductive health,
   retrieve passages that answer it\nQuery:` followed by the query. The
   instruction is a constant in the module.
2. **Candidates.** Two FAISS searches: the top `candidates` (default 40) over
   everything, and the top `evidence_candidates` (default 12) restricted to
   evidence statements. Merged and de-duplicated by passage id.
3. **Rerank.** A LangChain `BaseDocumentCompressor` subclass posts the query
   and the candidate texts to the vLLM `/v1/rerank` endpoint and attaches
   each relevance score. LangChain has no built-in vLLM reranker.
4. **Select.** The best `evidence_slots` (default 3) evidence statements by
   rerank score are kept first; the remaining slots are filled by rerank
   score from everything left. The result is returned best-first.
5. **Map** each document to `RetrievedPassage`. `score` is the rerank score.

Behaviour at the edges:

- **Start-up.** The client refuses to load an index whose manifest
  `embedding_model` differs from the configured one, whose
  `contains_quote_only` is true, or whose vector count differs from the
  passage count. The message says which.
- **Reranker unreachable or erroring.** The call falls back to embedding
  order, keeps the evidence-slot rule, and logs a warning. Retrieval degrades;
  it does not fail the turn.
- **Embedding endpoint unreachable.** The call raises, and the route returns
  502 as it does today for a retrieval failure.
- **Empty query.** Returns an empty list without calling either endpoint.
- **No web fallback.** `web_fallback.py` is deleted. It was off by default.

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `HERHEALTH_INDEX_DIR` | `build/index` | where the three index files are |
| `HERHEALTH_EMBEDDING_URL` | `http://127.0.0.1:8003` | embedding endpoint |
| `HERHEALTH_EMBEDDING_MODEL` | `herhealth-embed` | served model name |
| `HERHEALTH_EMBEDDING_MODEL_ID` | `Qwen/Qwen3-Embedding-4B` | the model the index must have been built with |
| `HERHEALTH_RERANKER_URL` | `http://127.0.0.1:8004` | reranker endpoint |
| `HERHEALTH_RERANKER_MODEL` | `herhealth-rerank` | served model name |
| `HERHEALTH_MODELS_API_KEY` | unset | bearer token, sent when set |
| `HERHEALTH_EVIDENCE_SLOTS` | `3` | reserved evidence-statement slots |
| `HERHEALTH_RERANK` | `off` | added 2026-10-12 after measurement; `on` enables the reranker (ADR 0017) |

`HERHEALTH_MODEL_SERVICE_URL` is removed. With no index at
`HERHEALTH_INDEX_DIR`, triage is "not configured" and the rest of the app
still boots, the same way a missing reasoning key behaves today.

`app/main.py` builds `LangChainRetrievalClient` where it builds
`HttpRetrievalClient` now. `HttpRetrievalClient` is deleted.

## Part 3: the recall check

New command `herhealth-eval-retrieval`, in the backend's `evaluation`
package, because it must exercise the real retriever.

- **Queries.** One per evidence row, built from the row's condition label and
  feature label and value. No new clinical text is written.
- **Scored rows.** Only rows whose source may be ingested: 93 of 140 today.
  The 47 NHS rows are not in the served index and are reported as excluded.
- **Two targets, reported separately:**
  - *source sentence*: a returned passage whose text contains the row's
    `source_quote`, or is contained in it.
  - *evidence statement*: the returned passage built from that row.
- **Metrics.** Recall at 1, 3 and 8, and mean reciprocal rank, each with the
  reranker on and with it off.
- **Output.** A table on stdout and a JSON file under `build/`.

Reported, not gated: there is no earlier number to hold it to. Stated in the
output and in `README.md`:

- The queries are built from the knowledge base's own labels, not from how
  users write. The evidence-statement target is the easier of the two,
  because the statement contains the query's words.
- English only. The benchmark's French and Arabic text is not used here.
- The knowledge base is source-traceable, not clinician-adjudicated.

## Part 4: deletions

| Path | Action |
|---|---|
| `services/data/src/herhealth_data/retrieval/embed.py` | `SentenceTransformerEmbedder` deleted; `HashingEmbedder` kept as the offline test stand-in |
| `services/data/src/herhealth_data/retrieval/index.py` | deleted (numpy `PassageIndex`) |
| `services/data/src/herhealth_data/retrieval/compose.py` and its test | deleted |
| `services/model/` | deleted entirely, and removed from the uv workspace |
| `services/backend/.../triage/clients.py` | `HttpRetrievalClient` deleted |
| `scripts/pin-bge-m3.py`, `scripts/publish-index.sh` | deleted |
| `.github/workflows/build-index.yml` | deleted |
| `.github/workflows/deploy.yml` | index fetch, index verification and the retrieval image build removed |
| `infra/compose.prod.yml` | `retrieval` service removed |
| `services/data/pyproject.toml` | `sentence-transformers` and `torch` removed; LangChain and FAISS added |
| `Makefile`, import-linter config, CI path filters | references to `services/model` removed |

Not deleted:

- **Terraform.** The retrieval log group, ECR repository and index role stay
  defined. `terraform apply` is manual and belongs to the repo owner.
- **ADR 0010, ADR 0012, research notes.** History. ADR 0010 is marked
  superseded by the new ADR.

Docs updated: `README.md`, `docs/runbooks/running-the-app.md`,
`docs/runbooks/aws-deploy.md`, `docs/FLOW_EXPLAINED.md`, `CLAUDE.md` (the
retrieval paragraph and the architecture block), and a new
`docs/adr/0017-qwen3-embedding-and-reranker-on-langchain.md`.

## Dependencies

- `services/data` retrieval extra: `langchain-core`, `langchain-community`,
  `langchain-openai`, `faiss-cpu`, `numpy`.
- `services/backend` api extra: the same four LangChain and FAISS packages.

Exact versions are whatever `uv lock` resolves, committed in `uv.lock`.

## Testing

Tests never hit the network and need no GPU.

- **Index build.** With `HashingEmbedder`: the three files round-trip; the
  served index contains no quote-only passage even when the corpus has some;
  the manifest counts match; evidence statements carry their four ids; URLs
  are resolved.
- **Retriever.** With a fake embeddings object and a fake reranker: evidence
  slots are honoured; the reranker's order is respected; duplicates across
  the two candidate pools collapse; reranker failure falls back to embedding
  order; a mismatched manifest is refused; an empty query calls nothing.
- **Reranker compressor.** Against `httpx.MockTransport`: request shape,
  score mapping, HTTP errors, and a malformed response body.
- **Recall check.** On a five-row fixture knowledge base with known answers.
- **Live.** One run of `herhealth-eval-retrieval` against the campus
  endpoints, with its output recorded in the README.

## Prerequisites needing a go-ahead

- **Fetching the corpus.** `raw/` and `build/` are absent on the campus box.
  `make fetch` requests the pages listed in `services/data/ingest.lock.jsonl`
  from the five sources, governed by each origin's `robots.txt`.
- **PyPI.** Installing LangChain and FAISS.
- **Disk.** The home volume has 2.6 GB free. The corpus and both indexes are
  expected to be well under 500 MB; this is checked before and after.

## Risks

- **Production triage is off until step 3.** The EC2 backend has no index and
  no route to the campus endpoints yet.
- **The campus endpoints are not reachable from EC2 today.** They listen on
  localhost inside a pod. The JupyterHub proxy cuts requests at about 60
  seconds, and the endpoints have no API key. Step 3 has to solve this.
- **Every query now needs two network calls to the campus box.** If the box
  is down or the pod was culled, retrieval fails and so does triage.
- **`OpenAIEmbeddings` against vLLM** is expected to work with length checking
  off; this is verified first in implementation, against the live endpoint.
- **The recall check can flatter the pipeline**, for the reasons listed in
  Part 3.
- **Schema-constrained output does not work on the chat serve** (step 1's
  finding). It does not affect retrieval, but step 3 inherits it.

## Out of scope

- The LLM call, the prompt, `agent.py`, and removing OpenRouter (step 3).
- Getting the index and the endpoint addresses onto EC2 (step 3).
- French and Arabic retrieval evaluation.
- Any change to `knowledge/`, the fetch and clean stages, or the frontend.

## Done when

- `make index` builds the served index on the campus box and its manifest
  shows `Qwen/Qwen3-Embedding-4B`, 2,560 dimensions, and
  `contains_quote_only: false`.
- One triage turn, run on the campus box through `TriageAgent` with the new
  retriever and the vLLM chat endpoint, shows retrieved passages reaching the
  model with their URLs. This is run from a script, not through the HTTP API:
  the API needs PostgreSQL, which this box cannot run in Docker. Whether the
  model's reply validates is step 3's concern, not this check's.
- `herhealth-eval-retrieval` has a recorded result for both targets, reranker
  on and off.
- `git grep -i bge-m3` finds matches only in ADRs, research notes and the
  superpowers documents.
- `make test`, `make lint` and the hygiene check pass.
- The deploy workflow no longer builds or expects a retrieval image.
