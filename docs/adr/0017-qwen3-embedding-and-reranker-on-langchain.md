---
status: accepted
date: 2026-10-12
supersedes: 0010
---

# Retrieval uses Qwen3-Embedding-4B and Qwen3-Reranker-4B, built on LangChain

## Context

[ADR 0010](0010-multilingual-embeddings-beat-arabic-specific-ones.md) chose
`BAAI/bge-m3` on published Arabic RAG results and deferred a reranker until
retrieval evaluation showed the right passage retrieved but ranked outside the
top *k*. Retrieval ran as a CPU service, `services/model`, which the backend
called over HTTP.

On 2026-10-11 the repo owner decided that all three models run on the campus
GPU box, that the backend and frontend run on the EC2 instance and are given
the model endpoints, and that the RAG pipeline is rewritten on LangChain. On
2026-10-12 the owner decided that the `bge-m3` code and everything tied to it
is deleted.

## Decision

- **Embedding model:** `Qwen/Qwen3-Embedding-4B`, 2560 dimensions, served by
  vLLM. Queries carry the instruction prefix the model expects; documents do
  not.
- **Reranker:** `Qwen/Qwen3-Reranker-4B`, served by vLLM, applied to about 50
  candidates per query.
- **Pipeline:** LangChain components. `services/data` builds a FAISS index;
  the backend loads it into a LangChain FAISS store and retrieves through a
  `BaseRetriever` subclass with a custom reranking compressor.
- **Where it runs:** the retriever runs inside the backend process and holds
  the index. It loads no model weights; the embedder and the reranker are
  HTTP calls. `services/model` is deleted.
- **Index format:** three plain files (`index.faiss`, `passages.jsonl`,
  `manifest.json`), never pickled, because the index is copied between
  machines and unpickling executes code.
- **Unchanged:** sentence-level passages, evidence statements as passages,
  three reserved evidence-statement slots of eight, and no quote-only (NHS)
  text in anything served. The served index now excludes that text when it is
  built; a second, local-only index keeps it for the evidence-proposal tool.

## What was not established

This decision was **not** made on a measurement that the new models retrieve
better than `bge-m3`. No comparison was run: there was no retrieval evaluation
in the repo, and the campus box had no disk space for both embedders. ADR
0010's reasoning from the Arabic RAG literature is not refuted by anything
here. If retrieval quality in Arabic or French is questioned, that comparison
is the first thing to run.

## Measurement

A recall check now exists (`herhealth-eval-retrieval`). For each evidence row
from an ingestable source it builds a query from the row's condition and
feature labels and looks for two things in the top 8: the source sentence the
row quotes, and the evidence statement generated from the row.

Run on the campus box on 2026-10-12:

```
reranker_on: 93 rows scored, 53 quote-only rows excluded
  sentence   recall@1=0.000  recall@3=0.140  recall@8=0.280  mrr=0.087
  statement  recall@1=0.925  recall@3=1.000  recall@8=1.000  mrr=0.962

reranker_off: 93 rows scored, 53 quote-only rows excluded
  sentence   recall@1=0.000  recall@3=0.108  recall@8=0.323  mrr=0.091
  statement  recall@1=0.914  recall@3=0.978  recall@8=1.000  mrr=0.950

Queries are built from the knowledge base's own labels, in English only; the statement target is the easier one.
The knowledge base is source-traceable, not clinician-adjudicated. Reported, not gated.
written to build/retrieval_eval.json
```

What they show, and what they do not:

- **The evidence statement for a row comes back essentially every time**
  (recall at 3 is 1.000 with the reranker, 0.978 without). That is the easy
  target, because the statement contains the query's own words.
- **The source sentence itself comes back in the top 8 for under a third of
  rows** (0.280 with the reranker, 0.323 without), and never at rank 1. Two
  likely reasons, neither tested: three of the eight slots are reserved for
  evidence statements, and the row's own statement quotes the same sentence
  and may outrank it.
- **The reranker did not improve the source-sentence target here.** The
  difference between 0.280 and 0.323 is four rows of 93, too few to call
  either way. Nothing in this run shows the reranker earning its GPU.
- The index was built from 146 evidence rows (93 from ingestable sources, 53
  from NHS), not the 140 `CLAUDE.md` states; that count needs updating.

Read these numbers with their limits. The queries come from the knowledge
base's own labels, not from how users write. The statement target is the
easier one, because the statement contains the query's words. It is English
only. Rows from NHS cannot be scored, because their text is not in the served
index. The knowledge base is source-traceable, not clinician-adjudicated.

One live turn through `TriageAgent` with the new retriever. Retrieval took 1.4
seconds and returned five source passages and three evidence statements, each
with its source url. The chat model's reply then failed validation because it
cited nothing; making the model's output valid is step 3, not this change:

```
decision attempt 1/2 failed (reasoning model returned malformed JSON: Expecting value: line 1 column 1 (char 0)) — retrying with feedback
retrieved 8 passage(s) in 1.42s for: 'My periods have been irregular for three months.'
  0.996 source_passage      medlineplus/menstruation § What are menstrual ir https://medlineplus.gov/menstruation.html
  0.996 source_passage      nichd/menstruation § Menstruation and Menstrual  https://www.nichd.nih.gov/health/topics/menstruation
  0.995 source_passage      medlineplus/menopause § What are the symptoms of https://medlineplus.gov/menopause.html
  0.995 source_passage      cdc/heavy_menstrual_bleeding § Causes            https://www.cdc.gov/ncbddd/blooddisorders/women/menorrhagia.html
  0.994 source_passage      medlineplus/pcos § What is polycystic ovary synd https://medlineplus.gov/polycysticovarysyndrome.html
  0.987 evidence_statement  medlineplus/evidence/pcos/cycle_regularity/irreg https://medlineplus.gov/polycysticovarysyndrome.html
  0.981 evidence_statement  medlineplus/evidence/primary_ovarian_insufficien https://medlineplus.gov/primaryovarianinsufficiency.html
  0.978 evidence_statement  womenshealth/evidence/pcos/cycle_length/under_21 https://womenshealth.gov/a-z-topics/polycystic-ovary-syndrome
reasoning did not return a valid decision after 55s: ValueError reasoning model returned malformed JSON: 1 validation error for TriageDecision
  Value error, a decision must be grounded in at least one citation or a red_flag_id [type=value_error, input_value={'observed': {'cycle_regu...you ha
    For further information visit
```

## Consequences

- **Production triage is off** until the EC2 backend has an index and a route
  to the campus endpoints. They listen on localhost inside a pod today and
  have no API key. The backend reports "not configured" in the meantime.
- **Every query needs two network calls to the campus box.** If the box is
  down or its pod was culled, retrieval fails and so does triage.
- **`langchain-community` is being wound down** by its maintainers; it is
  where the FAISS vector store lives. If it is removed, the store has to move
  to whichever standalone package replaces it. The index files do not depend
  on it.
- The deploy pipeline builds two images, not three. The Terraform resources
  for the retrieval image and the index bucket role still exist and can be
  removed in a later `terraform apply`.
- `torch` and `sentence-transformers` are no longer dependencies of anything
  in the workspace.
