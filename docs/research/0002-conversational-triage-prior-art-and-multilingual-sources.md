---
status: research
date: 2026-09-10
---

# Conversational triage: prior art, and candidate sources for Arabic and French

## What this is, and what it is not

**This is research, not a decision.** Like
[`0001`](0001-llm-triage-architecture.md), it is a reading of primary sources
against questions the team asked — here: *how do comparable systems and papers
make a model ask questions and then stop; and what sources could give the
knowledge base native Arabic and French content?* Nothing here supersedes
[`CLAUDE.md`](../../CLAUDE.md) or any accepted ADR, and nothing here reopens
[ADR 0011](../adr/0011-controller-free-triage.md). If a finding should change
the architecture, that change belongs in an ADR that cites this note.

**Every source below was read over the network on 2026-09-10 and is cited by
URL.** None were captured to [`sources/`](sources/) — unlike `0001`, this note
has no on-disk corpus behind it yet. Where a number came from a fetched page's
own text it is quoted; where it came only from a search summary, the line says
so. **No claim here has been checked against a paper PDF read page by page**,
and the licence readings in Part B are readings, not legal advice.

**Nothing in Part B has been fetched, ingested, or written into
`sources.yaml`.** Adding any of it is a separate decision requiring a network
call, which this repo requires be asked for first.

---

## Part A — how comparable systems ask questions

### A.1 The two architectures in the field, and where we sit

There are two live answers to "who decides the triage level", and both are
shipping.

**Hybrid: LLM at the edges, deterministic engine at the centre.** Infermedica's
Conversational Triage puts an LLM on natural-language understanding and
conversation, and keeps the triage decision in a Bayesian inference engine over
a curated medical knowledge graph. Their stated reason is that Bayesian
inference is *"explainable, deterministic, and fully transparent"* and
*"significantly reduces hallucinations"*
([Infermedica](https://infermedica.com/blog/articles/launching-conversational-triage)).
Ada Health is the same shape — a conversational front end over a Bayesian
network and knowledge graph
([search summary; not read from an Ada primary source](https://marketplace.aviahealth.com/compare/62098/46803)).
This is, structurally, the architecture
[ADR 0011](../adr/0011-controller-free-triage.md) retired.

**Model-driven: the LLM runs the dialogue.** Google's AMIE is the reference
point — *"an LLM-based AI system optimized for diagnostic dialogue"*, evaluated
against 20 primary care physicians in a randomised, double-blind crossover OSCE
study over 159 cases, and rated superior on *"30 out of 32 axes according to the
specialist physicians and 25 out of 26 axes according to the patient-actors"*
(Tu, Schaekermann, Palepu et al., *Towards conversational diagnostic artificial
intelligence*, **Nature 642(8067):442–450, 2025**,
[doi:10.1038/s41586-025-08866-7](https://pmc.ncbi.nlm.nih.gov/articles/PMC12158756/)).
This is the architecture ADR 0011 chose.

**The relevant finding is what AMIE needed to get there.** Not a prompt — a
training regime. A four-agent self-play environment (vignette generator,
dialogue generator, patient agent, self-play critic) with an inner loop of
in-context critic feedback and an outer loop feeding refined dialogues back into
fine-tuning; *"each iteration produced 11,686 dialogues spanning 5,230 medical
conditions"*, on top of 98,919 real clinical conversation transcripts (same
source). The model-driven architecture is viable; it was made viable by
purpose-built multi-turn data, at a scale several orders of magnitude above our
18-row [`bootstrap_multi_turn.jsonl`](../../services/data/eval/benchmark/bootstrap_multi_turn.jsonl).

### A.2 Prompting a model to ask questions does not work

This is the single most directly relevant finding for us, and it is measured,
not asserted.

**MediQ** (Li, Balachandran, Feng, Ilgen, Pierson, Koh, Tsvetkov,
[arXiv:2406.00922](https://arxiv.org/abs/2406.00922), NeurIPS 2024) builds an
interactive benchmark with a Patient system holding a full case and an Expert
system that must decide when it has enough to answer. Findings:

- State-of-the-art LLMs *"struggle to proactively seek information in a
  realistic interactive setting with incomplete initial information"*, while
  performing well when handed the complete case.
- **Directly prompting a state-of-the-art model to ask questions *degrades*
  performance.** Instruction alone is not a mechanism.
- What did work was an explicit abstention step — estimating confidence and
  deciding whether to ask — worth *"improving diagnostic accuracy by 22.3%"*,
  and still short of the complete-information upper bound.

Read against our own numbers, this is the same failure from the other side: our
evaluation measured clarification-seeking collapse to 0.000 after fine-tuning on
single-turn data; MediQ measures that even un-fine-tuned frontier models will not
ask well when merely told to. **Our current design's only mechanism for asking is
an instruction in the system prompt** (`DEFAULT_SYSTEM_PROMPT`: *"in most
consultations ask at least two or three clarifying questions"*). That is the
intervention MediQ reports as counter-productive.

### A.3 What does work: attribute-level supervision on the question itself

**ALFA** (Li, Mun, Brahman, Hosseini, Thomas, Sin, Ren, Ilgen, Tsvetkov, Sap,
*Aligning LLMs to Ask Good Questions*,
[arXiv:2502.14860](https://arxiv.org/abs/2502.14860), Feb 2025) decomposes "a
good question" into theory-grounded attributes (clarity, relevance, and
diagnostic-bias mitigation among them), synthesises attribute-specific question
variants, and aligns by preference optimisation. The dataset — **MediQ-AskDocs**,
17k real clinical interactions augmented to 80k attribute-specific preference
pairs — yields a *"56.6% reduction in diagnostic errors"* against SoTA
instruction-tuned baselines and a 64.4% question-level win rate. The paper also
reports that fine-grained attributes beat coarse-grained objectives downstream.

The transferable idea for us is not the preference optimisation. It is that
**question quality was made supervisable by decomposing it into attributes that
can be labelled without a clinician.** That is precisely the constraint our
[verification protocol](../../CLAUDE.md) operates under: we cannot adjudicate
clinical correctness, but "does this question target a feature that would change
the action?" is a mechanical check against `red_flags.yaml` clauses and
`evidence.csv`, and "is this question clear and answerable in the listed value
vocabulary?" is a reading-comprehension check.

### A.4 How many questions is the right number

Infermedica report their Conversational Triage asking **18.0 questions on
average against GPT-4o's 7.1**, with higher triage accuracy, and benchmarking
*"on par with Symptomate, which is certified as a Class 1 Medical Device in the
EU"*
([Infermedica](https://infermedica.com/blog/articles/launching-conversational-triage)).
Their real-world completion rate is *"approaching 60%"* — i.e. 18 questions costs
roughly 40% abandonment.

Two things follow. First, our `max_turns = 12` and our prompt's "two or three
clarifying questions" sit far below what a certified comparable asks. Second,
the abandonment number is the honest counterweight, and it is the same trade-off
[ADR 0007](../adr/0007-what-the-first-real-consultations-showed.md) recorded when
the escalation screen pushed a severe-pain case from four questions to ten. Both
numbers should be reported; neither settles it alone.

### A.5 Multilingual retrieval and the answer-language problem

Our embedding choice is already settled on published Arabic RAG results — see
[ADR 0010](../adr/0010-multilingual-embeddings-beat-arabic-specific-ones.md).
What the broader multilingual-RAG literature adds is about everything *around*
retrieval:

- Two families of approach: translate the query into the corpus language before
  retrieval (tRAG), or retrieve directly in a shared multilingual space (our
  approach, via bge-m3). A third — **CrossRAG**, translating *retrieved
  documents* into a common language before generation — is reported to improve
  knowledge-intensive tasks for both high- and low-resource languages
  ([arXiv:2504.03616](https://arxiv.org/html/2504.03616v1)).
- Multilingual retrieval *"introduces inconsistencies due to cross-lingual
  variations in the retrieved content"* (same source), and a body of work
  studies whether a model prefers evidence in its own query language
  ([arXiv:2502.11175](https://arxiv.org/pdf/2502.11175),
  [arXiv:2504.00597](https://arxiv.org/pdf/2504.00597)).
- The named failure mode most relevant to us: **ensuring the model answers in the
  user's language when the retrieved passages are in another** — reported as a
  standing challenge, not a solved one
  ([arXiv:2510.00908](https://arxiv.org/html/2510.00908v1)).

That last point has a concrete consequence recorded outside this note: our
runtime carries no locale, and nothing instructs the model to reply in the user's
language.

### A.6 Bilingual Arabic–English medical models

**BiMediX2** (MBZUAI,
[arXiv:2412.07769](https://huggingface.co/papers/2412.07769), EMNLP Findings
2025) is a Llama-3.1-based bilingual Arabic–English medical LMM trained on 1.6M
bilingual medical interactions, with **BiMed-MBench**, described as the first
expert-verified Arabic–English medical LMM benchmark. Reported gains: *"over 9%
improvement in English and over 20% in Arabic"*, with the 70B at 84.6% average
against GPT-4's 82.9% and Med42-70B's 83.0% (numbers from the paper's own
summary pages, not read from the PDF).

Relevance is indirect — it is a QA/VQA model, not a triage dialogue system, and
it is not multi-turn triage. It matters as **evidence that the Arabic gap is a
data gap, not a capability ceiling**: 20% Arabic improvement came from bilingual
training data. Its benchmark is also a candidate external yardstick for the
Arabic half of our evaluation, which today is measured with English-derived
labels only.

---

## Part B — candidate sources for more conditions, and for Arabic and French

**None of these have been fetched.** Each needs a licence reading confirmed
against the source's own page and a `sources.yaml` entry with **precedence** and
**status** recorded separately, per `CLAUDE.md`.

### B.1 WHO fact sheets — the multilingual candidate

The only candidate that could put **native Arabic and French clinical text into
the corpus** rather than relying on cross-lingual retrieval into English.

WHO publications are licensed **CC BY-NC-SA 3.0 IGO**, which *"allows users to
freely copy, reproduce, reprint, distribute, translate and adapt"* the work for
non-commercial purposes with attribution; adaptations must carry the same or a
compatible licence, and translations must carry a disclaimer that WHO did not
create them and that the original edition is authoritative. Required citation
form: `[Title]. [Place]: World Health Organization; [Year]. Licence: CC BY-NC-SA
3.0 IGO`. Coverage explicitly includes fact sheets and website content
([WHO copyright policy](https://www.who.int/about/policies/publishing/copyright)).

Reading: **ingestable, `available`**, subject to attribution and share-alike —
not `citable_only`. Relevant topic coverage plausibly includes anaemia,
infertility, STIs, HPV/cervical cancer, maternal health and FGM, and WHO EMRO
carries Arabic content with Eastern-Mediterranean framing. Precedence would need
deciding relative to NHS (2).

**The clause to record, not gloss.** `NC` forbids commercial use. That is the
same clause that removed NICE CKS. It is fine for a capstone and it is a
constraint on any future product, and it belongs in `sources.yaml`'s own note
rather than in a decision made once and forgotten. `SA` additionally propagates
to anything derived from it, which is a stronger claim than any current source
makes on us.

### B.2 StatPearls (NCBI Bookshelf) — the blocked-conditions candidate

The likeliest source of real clinical depth for the three conditions
`CLAUDE.md` records as **confirmed blocked** — hyperprolactinaemia, endometrial
polyp, functional hypothalamic amenorrhoea — and for pregnancy-related bleeding,
which was declined for the single-source exception specifically.

Licensed **CC BY-NC-ND 4.0**
([StatPearls on NCBI Bookshelf](https://www.ncbi.nlm.nih.gov/books/NBK430685/)).
Reading: quoting into `source_quote` with attribution is clearly permitted;
`ND` (no derivatives) is the problem for `passages.parquet`, since redistributing
adapted text is what `ND` forbids. Text and data mining for internal analysis is
generally accepted as not producing a shared derivative, but that is a reading,
and the safe classification is **`citable_only`, like NHS** — which means it
would strengthen the differential and not RAG. Worth having anyway. One further
caution: it is written at clinician level, so it may fail our "restatement of a
source" protocol on readability grounds. Read one page before committing.

### B.3 Deepening what we already have — the cheapest wins

Read from [`build/clean/`](../../build/clean/) on 2026-09-10: 66 documents
across five sources.

| Source | Docs on disk | Position |
|---|---|---|
| `womenshealth` | 19 | Public domain, ingestable, already the largest contributor. **Deepen first.** |
| `medlineplus` | 15 | Public domain outside `/ency/`. Many topic pages unfetched. **Deepen second.** |
| `nhs` | 17 | `citable_only`. Every NHS passage is filtered out of every search (see below). Deepening it does nothing for RAG. |
| `nichd` | 12 | Public domain *(unverified)*. |
| `cdc` | 3 | Public domain *(unverified)*, and only 2 evidence rows. Thinnest by far. |

**The measurement that reorders this list.** The built index holds 4,454
passages, of which 707 are NHS and carry `may_be_ingested=False`; the served
`/search` filters on that field
([`services/model/src/herhealth_model/app.py:188`](../../services/model/src/herhealth_model/app.py#L188)).
So the searchable corpus is 3,747 passages — and of the 140 evidence statements,
**47 are NHS and can never be retrieved, leaving 93 servable.** A third of the
reviewed evidence grid is invisible to retrieval. That is the strongest argument
both for re-fetching against public-domain sources and for adding WHO.

### B.4 Native French — needs investigation, licence unknown

No candidate here is confirmed. Worth probing, in this order: **WHO French fact
sheets** (same licence as B.1, so already cleared if B.1 is), then
**Santé publique France**, then **ameli.fr** (CNAM — likely restrictive; check
before fetching). Canadian federal health content is a further option and is
published bilingually.

### B.5 What is not worth re-investigating

`CLAUDE.md`'s excluded table stands: NICE CKS, RCOG/ACOG, UMLS, WHO ICD (beyond
`TODO_VERIFY` resolution), NCBI E-utilities and openFDA. Nothing found here
changes any of those readings. Note that **WHO ICD and WHO fact sheets are
different things** — the former is excluded as cosmetic, the latter is a new
candidate under a different licence.

---

## Part C — what this implies, stated as questions for an ADR

Not decisions. Each of these is something this note found and cannot settle.

1. **Instruction is not a mechanism for question-asking** (A.2). ADR 0011 moved
   the ask-vs-conclude decision to the model; the only thing currently making it
   ask is prompt text, which MediQ measures as counter-productive. What supplies
   the mechanism — retrieved state made visible, an abstention step, or trained
   preference on questions?
2. **The retrain has a shape, and a scale** (A.1, A.3). AMIE needed ~11.7k
   simulated dialogues per iteration; ALFA needed 17k interactions and 80k
   preference pairs. We have 18 bootstrap rows generated by the controller ADR
   0011 retired. What generates the data, and what makes its labels derivable
   rather than judged?
3. **Question count is a product decision with a measured cost** (A.4).
   Infermedica: 18 questions, ~60% completion. Ours: 12-turn cap, "two or three"
   in the prompt. Which number, and reported against which abandonment figure?
4. **Locale is absent from the contract** (A.5). Cross-lingual retrieval is
   handled; reply language, locale-resolved safety strings and dialectal input
   are not. Does locale become a first-class field?
5. **A third of the evidence grid is unservable** (B.3). Does that change source
   priority, and does WHO's CC BY-NC-SA licence clear the bar the NC clause
   already set for NICE CKS?

---

## Sources

Read over the network 2026-09-10; none captured to disk.

- Tu, Schaekermann, Palepu et al. *Towards conversational diagnostic artificial intelligence.* Nature 642(8067):442–450, 2025 — https://pmc.ncbi.nlm.nih.gov/articles/PMC12158756/
- Li, Balachandran, Feng, Ilgen, Pierson, Koh, Tsvetkov. *MediQ: Question-Asking LLMs and a Benchmark for Reliable Interactive Clinical Reasoning.* arXiv:2406.00922 — https://arxiv.org/abs/2406.00922
- Li, Mun, Brahman et al. *ALFA: Aligning LLMs to Ask Good Questions — A Case Study in Clinical Reasoning.* arXiv:2502.14860 — https://arxiv.org/abs/2502.14860
- Infermedica. *Launching Conversational Triage: Combining LLMs with Bayesian Models.* — https://infermedica.com/blog/articles/launching-conversational-triage
- BiMediX2. arXiv:2412.07769, EMNLP Findings 2025 — https://huggingface.co/papers/2412.07769
- *Multilingual Retrieval-Augmented Generation for Knowledge-Intensive Task.* arXiv:2504.03616 — https://arxiv.org/html/2504.03616v1
- *Investigating Language Preference of Multilingual RAG Systems.* arXiv:2502.11175 — https://arxiv.org/pdf/2502.11175
- *On the Consistency of Multilingual Context Utilization in RAG.* arXiv:2504.00597 — https://arxiv.org/pdf/2504.00597
- *Bridging Language Gaps: Advances in Cross-Lingual Information Retrieval with Multilingual LLMs.* arXiv:2510.00908 — https://arxiv.org/html/2510.00908v1
- World Health Organization. *Copyright and permissions.* — https://www.who.int/about/policies/publishing/copyright
- StatPearls, NCBI Bookshelf. — https://www.ncbi.nlm.nih.gov/books/NBK430685/
