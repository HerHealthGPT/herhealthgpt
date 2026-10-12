---
status: superseded by 0017
---

# Multilingual embeddings beat Arabic-specific ones, and the chunk is a sentence

`retrieval/embed.py` and `retrieval/passages.py` have cited this ADR since they
were written. **The file did not exist.** Written now, after the fact, from the
paper the docstrings quote — not reconstructed from memory. Every number below
was read out of the PDF and carries a page.

The source is Alsubhi et al., *Optimizing RAG Pipelines for Arabic: A Systematic
Analysis of Core Components*, [arXiv:2506.06339](https://arxiv.org/abs/2506.06339),
kept at `docs/research/sources/q3-arxiv-2506.06339-alsubhi-arabic-rag-embedding-chunking-evaluation.pdf`.
It evaluates six embedding models and four chunking strategies across six Arabic
datasets — ARCD, ArSQUAD, SaudiWiki, QA4MRE, Quran Tafseer and Hindawi Books.

## The embedding model is `BAAI/bge-m3`

Table 2, page 9. Overall RAG score, mean across the six datasets:

| Model | Average | Kind |
|---|---|---|
| **BGE-M3** | **70.99** | multilingual |
| E5-Large (multilingual-e5-large) | 70.31 | multilingual |
| Arctic-Embed (snowflake-arctic-embed-l-v2.0) | 69.48 | multilingual |
| GTE-Base (gte-multilingual-base) | 68.48 | multilingual |
| Matryoshka (Arabic-Triplet-Matryoshka-V2) | 66.46 | **Arabic-specific** |
| Arabic-MPNet (Arabic-mpnet-base-all-nli-triplet) | 45.92 | **Arabic-specific** |

**The intuitive move would have been wrong.** Reaching for an Arabic-specialised
encoder because a third of our users read Arabic is exactly what the evidence
does not support: both Arabic-specific models placed last, and the weaker of them
by 25 points. The paper attributes the gap to "strong cross-lingual training and
large model capacity" (p8).

The margin over multilingual-e5-large is **0.68 points**, which is not decisive.
Two considerations broke the tie, neither of them the score:

- One model must serve English, French and Arabic. A model chosen on Arabic
  results that is also strong elsewhere is worth more than a marginal Arabic win,
  and the same paper notes e5-large's strength is concentrated in structured
  corpora like SaudiWiki (88.74) rather than being uniform.
- bge-m3 is **MIT** licensed; the reranker below is **Apache-2.0**. Both are
  self-hostable with no licence question, which matters because
  `sources.yaml` already carries enough licence constraints.

`multilingual-e5-large` is the named fallback. At 0.68 points it is a swap, not a
rewrite, and `embed.py` carries `QUERY_PREFIX`/`PASSAGE_PREFIX` precisely so a
model that needs asymmetric prefixes can replace bge-m3 without touching callers.

## The chunk is a sentence

Table 1, page 8. Mean across the same six datasets:

| Strategy | Average |
|---|---|
| **Sentence-aware** | **74.78** |
| Fixed-size | 69.41 |
| Recursive | 69.13 |
| Semantic (embedding-based) | 66.92 |

Semantic chunking — the most sophisticated option and the one that sounds most
like what a careful team would choose — came **last**, below fixed-size splitting.

**But the benchmark is not what decides this for us.** Every clinical row carries
a `source_quote` that must appear verbatim in its source, and `make verify-quotes`
checks exactly that. If a passage straddled a chunk boundary, the sentence a
reviewer needs to quote might not exist as a retrievable unit. Retrieving
sentences means anything retrieved can be quoted directly.

That structural reason would hold **even if sentence-aware chunking had scored
worst**. The benchmark is corroboration, not the argument. Recorded that way so
nobody later "improves" the chunker on a benchmark and silently breaks quote
verification.

## The reranker is deferred, not rejected

Table 3, page 9. Adding `bge-reranker-v2-m3` raised the overall average from
**70.99 to 74.15**, with the largest gain on ARCD (80.29 → 86.31). The paper
notes the benefit is concentrated where "initial retrieval lacks semantic
precision" and was smallest on highly structured datasets — SaudiWiki actually
fell slightly (88.31 → 87.39).

Our corpus is small: `evidence.csv` holds 89 rows over 12 conditions and 30
features, and `passages.parquet` is built from a handful of documents per
condition. A reranker earns its latency when there is a long tail of candidates
to reorder. We do not yet have one, and the paper's own framing says the gain
shrinks as retrieval gets cleaner.

**Deferred, with a trigger:** revisit when retrieval evaluation shows the correct
passage is being retrieved but ranked outside the top *k*. That is the failure a
reranker fixes. Adding one before observing that failure is paying latency for a
problem we have not demonstrated.

## What this ADR does not establish

- The paper evaluates **Arabic** retrieval. It says nothing about French, and our
  French coverage rests on bge-m3 being multilingual rather than on measurement.
  Unverified, and stated as such.
- Scores are RAGAS-based means on general-domain Arabic corpora, not on
  reproductive-health text. Domain transfer is assumed, not shown.
- The 0.68-point gap over multilingual-e5-large is inside the range where
  dataset choice could plausibly reverse the ordering. The decision is defensible
  on licence and breadth; it is not defensible as "bge-m3 is the best model".

## Consequences

- `DEFAULT_MODEL = "BAAI/bge-m3"` in `embed.py`, chosen on published Arabic
  results rather than popularity.
- Sentence-aware chunking in `passages.py`, load-bearing for `make verify-quotes`
  and therefore not a tuning knob.
- No reranker in the MVP serving path. `bge-reranker-v2-m3` (Apache-2.0) is the
  candidate if the trigger above is hit.
- The three dangling citations — `embed.py:22`, `embed.py:42`, `passages.py:9` —
  now resolve.
- Model weights stay out of the backend process; embedding is an HTTP call to
  `services/model`, unchanged by this decision.
