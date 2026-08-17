---
status: research
date: 2026-08-17
---

# Reconsidering the deterministic controller: what the primary sources say

## What this is, and what it is not

**This is research, not a decision.** It is a reading of primary sources —
official documentation, model cards, arXiv papers, regulator guidance, library
source and docs — against five questions the team raised about replacing or
reducing the deterministic Python stopping controller. Nothing here supersedes
[`CLAUDE.md`](../../CLAUDE.md) or any accepted ADR. If a finding here should
change the architecture, that change belongs in an ADR that cites this note.

**It is not a literature review, and it is not complete.** It answers the five
questions that were asked, with the sources that could actually be fetched.

**Every factual claim below links to the source that owns it.** Where a source
could not be retrieved, or where a number appeared only in a search summary and
not in a document this note could open, that is stated in the text rather than
smoothed over. This repository's rule against inventing content applies to
research notes as much as to `evidence.csv`.

**The primary PDFs and HTML captures are on disk** in
[`docs/research/sources/`](sources/) (44 files, named `q<N>-<slug>`). Quotations
marked with a page number were read from those files directly. The remainder were
read over the network and are cited by URL only.

**Four caveats that recur below, stated once here:**

- **The repo's own benchmark numbers are silver, not gold.** Under-triage 0.718,
  clarification 0.856 → 0.000, French/Arabic under-triage 0.994 — all come from
  the team's own evaluation over labels that are not clinician-adjudicated. They
  are cited here as *this project's observations*, never as published findings.
- **This project is not a regulated device and this note is not legal advice.**
  Regulatory framing appears in Q1 because it bears directly on *where the
  urgency decision may sit*, which is the architectural question. It is
  descriptive.
- **Two findings in this note were acted on while it was being written, and are
  already fixed in the working tree.** They are kept below because they are the
  reason the fixes happened, but **neither is a live defect**:
  - `CLAUDE.md`'s knowledge-base counts were stale (~350 evidence rows, 17
    conditions, ~50 features, four sources, against 89 / 12 / 37 / five on disk).
    `CLAUDE.md` has since been rewritten with the parsed counts, the by-source and
    by-strength breakdowns, the twelve authored condition ids, and a warning not
    to count `evidence.csv` with `wc -l`. Finding and comparison in
    [§2d](#2d-documentation-drift-between-claudemd-and-the-files-on-disk).
  - `docs/adr/0010` was cited three times and did not exist —
    [`embed.py:22`](../../services/data/src/herhealth_data/retrieval/embed.py),
    [`embed.py:42`](../../services/data/src/herhealth_data/retrieval/embed.py),
    [`passages.py:9`](../../services/data/src/herhealth_data/retrieval/passages.py).
    `docs/adr/0010-multilingual-embeddings-beat-arabic-specific-ones.md` has since
    been written from the page-cited evidence in
    [§3b](#3b-what-size-of-model-this-corpus-actually-justifies) and
    [§3c](#3c-is-a-reranker-warranted).

  Both changes are **uncommitted working-tree edits made by another agent**, not
  by this note. This note edited only itself. Anyone reading a committed revision
  of the repo should re-check whether they landed.

---

## Q1. Open-vocabulary input against a closed knowledge base

**The worry as stated:** a user types a symptom that is not in
[`features.yaml`](../../knowledge/features.yaml), so the deterministic
controller has nothing to match, and therefore the controller should be replaced
by an end-to-end LLM.

The evidence separates these into two independent claims. The first — that
open-vocabulary input needs a mapping layer — is well supported. The second —
that the fix is to move the urgency decision into the model — is contradicted by
every primary evaluation found.

### 1a. The standard mitigation is retrieve-then-constrain, not free generation

The named task is *medical concept normalisation* / *entity linking*: mapping
free text onto a closed, coded vocabulary. The primary architecture in the
current literature is two-stage — an embedding retriever proposes candidates
from the closed vocabulary, then a model **selects among the retrieved
candidates** rather than generating an identifier.

[Generalizable and scalable multistage biomedical concept normalization
leveraging large language models](https://pmc.ncbi.nlm.nih.gov/articles/PMC12527512/)
reports F1 improvements of **+7.3% to +21.7%** over rule-based normalisation
baselines by adding LLM stages around a retriever, with the best configuration
(embeddings + Vicuna) at **+21.7 F1**. The paper's own framing is that the LLM
generates synonyms and *prunes candidates* — it is never the thing that emits
the code.

That constraint is not stylistic. [Predicting Failures of LLMs to Link
Biomedical Ontology Terms to Identifiers](https://arxiv.org/pdf/2509.04458)
studies exactly what happens when a model is asked to emit ontology identifiers
from memory, and finds substantial, model- and ontology-dependent failure. *This
note could only partially extract that PDF — the compressed content streams did
not yield the abstract verbatim, so the specific rates are not quoted here.*
The direction of the finding is nonetheless the same one this repo already
enforces in [`conditions.yaml`](../../knowledge/conditions.yaml), which forbids
hand-written ICD-11 codes and requires `TODO_VERIFY` until the WHO API resolves
them. **The repo reached that rule independently and the literature agrees with
it.**

The scoping review of SNOMED CT use in LLMs (indexed at
[PubMed 39374057](https://pubmed.ncbi.nlm.nih.gov/39374057/)) reports concept
normalisation as the most frequent end task and describes the same
retrieve-then-rerank shape. *This note could not open the full text; the
characterisation is from the abstract-level record and search index, not from
the article body.*

**What this means for the repo.** The mitigation for out-of-vocabulary input is
an embedding layer between the user's prose and `features.yaml`, not the removal
of the controller. That layer is already half-built:
[`PassageIndex`](../../services/data/src/herhealth_data/retrieval/index.py)
does exact brute-force cosine search over sentence passages, and
[`propose.py`](../../services/data/src/herhealth_data/retrieval/propose.py)
already applies the "model proposes, human disposes" discipline for authoring.
The serving-side analogue — map her prose onto feature ids, refuse below a
similarity floor — is the same mechanism pointed at a different target.

### 1b. There must be an explicit "not covered" path, and the repo already has one

[ADR 0005](../adr/0005-plausibility-is-an-independent-logistic.md) rejected
softmax precisely because *"a softmax cannot express 'none of these fit'"* — it
normalises to 1 whatever it is given, so a user with an unmodelled condition
would still see the least-bad candidate float to the top. That is the
architectural form of an out-of-vocabulary path, and it is the single most
important thing in this repo for the Q1 worry. An independent logistic lets
every condition be implausible at once.

The gap is that this exists at the *scoring* layer and not yet at the *input*
layer. There is no code path today that says "her words matched no feature above
threshold." That is the concrete deliverable Q1 actually implies.

The abstention literature says the same thing from the model side.
[Know Your Limits: A Survey of Abstention in Large Language
Models](https://arxiv.org/html/2407.18418) frames abstention as recognising that
an answer is unknown *or out of scope* and explaining why. Note the direction:
the literature is adding abstention machinery to models that lack it, not
removing controllers from systems that have it.

### 1c. On removing the deterministic layer: the primary evidence is against it

No primary source found supports handing the urgency decision to an LLM. Four
lines of evidence, all from published evaluations:

**Models under-ask.** [MediQ: Question-Asking LLMs and a Benchmark for Reliable
Interactive Clinical Reasoning](https://arxiv.org/abs/2406.00922) (NeurIPS 2024)
identifies the obstacle in its abstract: *"LLMs are trained to answer any
question, even with incomplete context or insufficient knowledge."* Its results
show that **directly prompting state-of-the-art LLMs to ask questions degrades
performance** — the [v3 full text](https://arxiv.org/html/2406.00922v3) reports
naive question-asking dropping accuracy roughly **11.3% relative** to the
non-interactive incomplete-information baseline, with the paper's analysis
noting that *"most models don't tend to ask follow-up questions."*

**Fixing it required an external module, not better prompting.** MediQ's gain
comes from an explicit **Abstention Module** — a separate confidence-estimation
step with a threshold, evaluated in numerical, binary, Likert-scale,
rationale-generation and self-consistency variants — which improved diagnostic
accuracy by **22.3%** over the basic interactive setup. Even then it closed only
**51.2%** of the gap to an upper bound with complete information supplied
upfront. **This is the single most load-bearing citation in this note:** the
best-performing configuration in the primary benchmark for ask-or-answer
behaviour puts the ask-or-answer decision *outside* the model's free generation.
That is structurally the same choice as `should_stop`.

**Frontier models are weakest at exactly the behaviour this system needs.**
[HealthBench](https://arxiv.org/html/2505.08775) (OpenAI, 262 physicians, 60
countries, 5,000 conversations, 48,562 physician-written rubric criteria) reports
performance *highest* on emergency referrals and *lagging* on **context-seeking**,
which it defines as whether models *"could recognize when key context was missing
and seek the most informative context. Failures here can lead to incomplete,
irrelevant or unsafe responses."* It also reports a worst-case reliability
finding directly relevant to a safety-critical deployment: while o3 scores 60%
overall, **its worst-at-16 score is reduced by about a third**. A triage system
is judged on its worst case, not its mean.

**HealthBench does not report per-language results.** The paper notes physician
contributors spoke 49 languages, but this note found **no disaggregated
English-vs-Arabic or English-vs-French performance figures** in it. So HealthBench
cannot be used to argue that a frontier model would be safe in Arabic. The repo's
own French/Arabic collapse to 0.994 under-triage remains the only
language-disaggregated evidence anyone here has, and it is silver-labelled.

**Emergency-department triage evaluations show systematic acuity bias.**
[From Promising Capability to Pervasive Bias: Assessing Large Language Models for
Emergency Department Triage](https://arxiv.org/abs/2504.16273) finds LLMs
robust to distribution shift and missing data, *and* that they "encode
demographic preferences that may emerge in specific clinical contexts or
particular combinations of characteristics," with sex-based differences most
pronounced in certain racial groups. Note that this paper is **partly favourable**
to LLMs — it reports "superior robustness" versus classical ML — and it is
reported that way here rather than trimmed to fit.

[EQUITRIAGE: A Fairness Audit of Gender Bias in LLM-Based Emergency Department
Triage](https://arxiv.org/abs/2605.03998) evaluated five models across **374,275
evaluations on 18,714 patient vignettes**, and found **all models exceeded a 5%
fairness threshold for decision-flip rates, ranging 9.9% to 43.8%**, with some
showing directional **female under-triage**. Demographic blinding reduced one
model's flip rate to 0.5%. *A search summary attributed to this paper an
exact-match accuracy of 44.3% and an ESI-1 under-prediction of 1.6% against a
16.8% ground-truth rate; those figures are **not** in the abstract this note
fetched and are therefore not asserted here.* Given that this system's users are
women and the dominant failure mode is under-triage, directional female
under-triage in LLM triage is the most adverse single finding in this note.

**The one counter-current, reported honestly.** The strongest pro-LLM triage
result found is [Multi-Evidence Clinical Reasoning With Retrieval-Augmented
Generation for Emergency Triage](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12887567/),
which reports MECR-RAG at **QWK 0.902 / accuracy 0.802** against a baseline LLM
at **QWK 0.801 / accuracy 0.542**, and under-triage held at **3/236 (1.3%)**
versus 4/236 (1.7%). Read carefully: **the thing that produced the good numbers
was adding structured evidence and retrieval around the model, not removing
structure.** The baseline — the LLM deciding on its own — scored 0.542 accuracy.
That paper is evidence for grounding, not for end-to-end LLM triage.

### 1d. Regulatory framing: where the urgency decision may sit

**EU MDR / MDCG 2019-11.** The primary text is
[MDCG 2019-11, *Guidance on Qualification and Classification of Software in
Regulation (EU) 2017/745 – MDR and Regulation (EU) 2017/746 – IVDR*](https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2019_11_guidance_en_0.pdf).
Fetched and read directly. What matters:

- **Rule 11, verbatim:** *"Software intended to provide information which is used
  to take decisions with diagnosis or therapeutic purposes is classified as class
  IIa, except if such decisions have an impact that may cause: death or an
  irreversible deterioration of a person's state of health, in which case it is
  in class III; or a serious deterioration of a person's state of health or a
  surgical intervention, in which case it is classified as class IIb."*
- The guidance explains sub-rule 11a as covering *"in very general terms, the
  'mode of action' which is characteristic of all MDSW,"* and sets the higher
  classes by *"the significance of the provided information and the potential
  impact of an (incorrect) decision made using information from the MDSW."*
- **Lay users are explicitly in scope.** Note 4: *"MDSW may be intended to be used
  by healthcare professionals or laypersons (e.g. patients or other users)."* One
  of the guidance's own examples of independent MDSW placed on the market in its
  own right is *"MDSW app that provides a 10-year risk of cardiovascular disease
  from data input by a lay user."*
- Qualification turns on **intended purpose**, not on risk: *"the risk of harm to
  patients, users of the software, or any other person, related to the use of the
  software within healthcare, including a possible malfunction is not a criterion
  on whether the software qualifies as a medical device."* And *"'Simple search',
  which refers to the retrieval of records by matching record metadata against
  record search criteria or to the retrieval of information does not qualify as
  medical device software."*

The architectural reading: under MDCG 2019-11 the classification driver is the
**significance of the information to the decision and the severity if it is
wrong** — which is precisely the axis this repo's four action codes sit on. A
system whose worst output is `EMERGENCY`-vs-`SELF_CARE` sits high on that axis
regardless of what produced the output. **Nothing in MDCG 2019-11 says the
decision may not be produced by a model.** What it does is make the *severity of
being wrong* the classification driver, which favours a decision path that can be
inspected, unit-tested and pinned by cases — the properties `should_stop` has and
a model does not. A note on scope: the EU regime is cited here for its reasoning,
not because it applies — users are in Egypt. Revision 1 of MDCG 2019-11 was
reportedly published on 17 June 2025; **this note read the original and did not
verify the revision's contents.**

**US FDA Clinical Decision Support Software.** The guidance is on disk at
[`sources/q1-fda-cds-software-guidance.pdf`](sources/q1-fda-cds-software-guidance.pdf)
(27 pages, from <https://www.fda.gov/media/109618/download>). Title page: *"Document
issued on January 29, 2026. This document supersedes 'Clinical Decision Support
Software' issued on January 6, 2026."* All quotations below are verbatim from that
document, with page numbers.

**The four criteria, verbatim (p6).** Software is excluded from the device
definition by § 520(o)(1)(E) only if it meets **all four**:

> (1) not intended to acquire, process, or analyze a medical image or a signal from
> an in vitro diagnostic device or a pattern or signal from a signal acquisition
> system (section 520(o)(1)(E) of the FD&C Act);
>
> (2) intended for the purpose of displaying, analyzing, or printing medical
> information about a patient or other medical information (such as peer-reviewed
> clinical studies and clinical practice guidelines) (section 520(o)(1)(E)(i) of
> the FD&C Act);
>
> (3) intended for the purpose of supporting or providing recommendations to a
> health care professional about prevention, diagnosis, or treatment of a disease
> or condition (section 520(o)(1)(E)(ii) of the FD&C Act); and
>
> (4) intended for the purpose of enabling such health care professional to
> independently review the basis for such recommendations that such software
> presents so that it is not the intent that such health care professional rely
> primarily on any of such recommendations to make a clinical diagnosis or
> treatment decision regarding an individual patient (section 520(o)(1)(E)(iii) of
> the FD&C Act).

*Citation correction: Criterion 4 is **§ 520(o)(1)(E)(iii)**, not (iv). The
guidance cites (iii) both in the list on p6 and again in the Criterion 4
discussion on p14. Criterion 3 is (E)(ii). The offset exists because Criterion 1
cites the subparagraph itself rather than a clause.*

**The sentence that decides this project (p13, Criterion 3 discussion):**

> Software functions that support or provide recommendations to patients or
> caregivers – not HCPs – meet the definition of a device.

**Every one of the four criteria is HCP-facing.** Criterion 3 requires
recommendations *to a health care professional*; Criterion 4 requires enabling
*that same health care professional* to review the basis. HerHealthGPT recommends
an urgency action **to a patient**. On its face the § 520(o)(1)(E) carve-out
does not apply to it, **and this is true regardless of whether the decision is
made by Python or by a model.** The architecture question and the device-status
question are independent, and it would be wrong to argue that the deterministic
controller buys non-device status. It does not.

**But "meets the device definition" is not "requires clearance", and the guidance
says so directly (p5):**

> This guidance further clarifies that FDA's existing digital health policies
> continue to apply to software functions that meet the definition of a device,
> including those that are intended for use by patients or caregivers. For
> example, some decision support software functions may be identified in other
> guidance documents as software functions for which, based on our current
> understanding of the risks of these software functions, FDA does not intend at
> this time to enforce compliance with applicable device requirements of the FD&C
> Act, including, but not limited to, premarket clearance and approval
> requirements.

Reinforced at p13, where FDA states it *"understands the importance of CDS for
patients and caregivers and supports increased access to innovative, safe, and
effective CDS for non-HCP users"* and intends to be consistent with existing
policies, naming *Policy for Device Software Functions and Mobile Medical
Applications*, *SaMD: Clinical Evaluation*, *Medical Device Data Systems…*, and
*General Wellness: Policy for Low Risk Devices*. **Do not overstate this section
in the write-up.** The accurate statement is: a patient-facing urgency
recommender is not inside the CDS carve-out, and enforcement discretion under
separate policies is a distinct question this note has not researched.

**Two findings that do bear on architecture, both verbatim:**

1. **Time-critical tasks are called out explicitly (p14, Criterion 4):** *"FDA
   does not consider software functions intended for a critical, time-sensitive
   task or decision to meet Criterion 4, because an HCP is unlikely to have
   sufficient time to independently review the basis of the recommendations."*
   Urgency triage is definitionally time-sensitive. Restated at p15: *"FDA
   considers the (a) level of software automation and (b) time-critical nature of
   the HCP's decision making when determining whether a software function allows
   an HCP to independently review the basis for the recommendations."*
2. **Automation bias is named as the mechanism (p15):** *"Automation bias is the
   propensity of humans to over-rely on a suggestion from an automated system. In
   the context of CDS, automation bias can result in errors of commission
   (following incorrect advice) or omission (failing to act because of not being
   prompted to do so). In situations that require urgent action, automation bias
   increases…"* This is the regulator naming, in its own words, the risk this
   system runs with a worried user: she may not seek care because the system did
   not tell her to. That is under-triage, framed as a human-factors problem
   rather than a model-accuracy one — and it is an argument for the conservative
   tie-breaks already in `weights.yaml` and `should_stop`.

**What FDA expects a recommendation to disclose (p14–15)** is strikingly close to
what this repo already produces: *"a plain language description of the underlying
algorithm development and validation that forms the basis for the CDS
implementation"*; *"relevant patient-specific information and other
knowns/unknowns for consideration"*; and *"regardless of the complexity of the
software and whether or not it is proprietary, the software or associated labeling
should provide adequate background information about underlying sources in plain
language."* `source_id` plus verbatim `source_quote` on every clinical row, the
citation-bearing final answer, and the plausibility trace are exactly that shape,
and they are a direct consequence of the deterministic controller. An end-to-end
LLM cannot produce it: a post-hoc explanation of a decision the model made
internally is not the basis for that decision. **This is a design argument, not a
compliance claim** — the disclosure expectations quoted here attach to Criterion 4,
which this system does not reach.

**Verification status:** both MDCG 2019-11 and the FDA CDS guidance quotations
above are verbatim from PDFs on disk in
[`docs/research/sources/`](sources/). This note is still not legal advice, and
the § 520(o)(1)(E) analysis is a reading of the guidance's plain text, not a
regulatory opinion.

### Q1 verdict

Supported: open-vocabulary input needs a semantic mapping layer plus an explicit
out-of-scope path. Contradicted: that this requires removing the deterministic
controller. The two best-performing systems found for interactive clinical
question-asking ([MediQ](https://arxiv.org/abs/2406.00922)) and for triage
accuracy ([MECR-RAG](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12887567/))
both *added* external structure around the model.

---

## Q2. Knowledge-file compatibility with RAG and with fine-tuning

Read against the actual files on disk on the `data` branch. Current shapes:

| File | On-disk shape | Rows/size today |
|---|---|---|
| `features.yaml` | YAML list; `id`, `label`, `kind`, `allowed_values`, `burden`, `probe.{lang}`, `note` | **37** features, 19 KB |
| `conditions.yaml` | YAML list; `id`, `label`, `icd11`, `baseline_action`, `source_ids`, `search_term`, `note` | **12** conditions, 16 KB |
| `evidence.csv` | flat CSV, header `condition_id,feature_id,value,strength,source_id,source_quote,note` | **89 data rows**, 37 KB |
| `red_flags.yaml` | YAML; `id`, `label`, `action`, `all_of[]` clauses, `source_id`, `source_quote` | **14** rules, 11 KB |
| `sources.yaml` | YAML; `id`, `name`, `url`, `precedence`, `licence`, `access`, `status` | **5** sources, 7.7 KB |
| `weights.yaml` | single record of constants + heavy commentary | 8.4 KB |
| `actions.yaml` | 4 records; `code`, `severity`, `description` | 1.8 KB |
| `passages.parquet` | generated; sentence-level passages, `may_be_ingested` carried per row | not present on this branch |

**Counts are parsed, not line-counted.** `wc -l` reports 110 lines for
`evidence.csv`; a `csv.DictReader` parse reports **89 data rows**. The difference
is embedded newlines inside quoted `source_quote` and `note` fields. Anything
quoting a row count off a line count will overstate the knowledge base by ~23%.
The parsed breakdown:

- **By source:** nhs 37, womenshealth 30, medlineplus 13, nichd 8, cdc 1.
- **By strength:** `weak_support` 46, `strong_support` 34, `argues_against` 9,
  **`rules_out` 0**. The absence of `rules_out` rows is what makes
  [ADR 0009](../adr/0009-rules-out-does-not-override-accumulated-support.md)'s
  known defect currently harmless, and it is half of why elimination barely works
  (ADR 0007 finding 1).
- **Coverage:** 12 distinct conditions and **30 distinct features** appear in
  evidence rows, so 7 of the 37 defined features carry no evidence row.
  `features.yaml`'s own header says a feature with no evidence row *and* no
  red-flag clause *"is dead weight"*. **That check has now been run, and there is
  no dead weight:** 30 features are used by `evidence.csv` and 15 by
  `red_flags.yaml`, and the union covers all 37 — the 7 without evidence rows are
  exactly the red-flag-only features, which is what emergency screening
  questions should look like. Referential integrity is clean in both directions:
  no feature id appears in `evidence.csv` or `red_flags.yaml` that is absent from
  `features.yaml`.

**The whole knowledge base is ~100 KB of text.** That number decides most of
this section.

### 2a. Retrieval

**`evidence.csv` is not usefully retrievable as text, and should not be made so.**
A row is `(condition_id, feature_id, value, strength)` plus provenance. Its
meaning is *relational and ordinal* — it exists to be summed into a log-odds
score, which is what
[`scoring.py`](../../packages/contracts/src/herhealth_contracts/scoring.py) and
the engine do. Embedding "adenomyosis, bleeding_heaviness, heavy, strong_support"
as a sentence and retrieving it by cosine similarity discards the arithmetic that
is the entire point. [LlamaIndex's own RAG
overview](https://developers.llamaindex.ai/python/framework/understanding/rag/)
defines a Node as *"the atomic unit of data in LlamaIndex and represents a
'chunk' of a source Document"* and describes indexing as producing *"vector
embeddings which are stored in a specialized database called a vector store"* —
a framing built for prose, with metadata filters and structured query paths kept
as a separate track. `evidence.csv` belongs on the structured track. It already
is on it: it is loaded into Pydantic models and queried by key.

**The `source_quote` column is the retrievable part, and it is already retrieved.**
Every clinical row carries a verbatim sentence. That is prose, it is
sentence-sized, and [`passages.py`](../../services/data/src/herhealth_data/retrieval/passages.py)
already makes the sentence the retrieval unit specifically so that anything
retrieved can be quoted verbatim and pass `make verify-quotes`. Nothing needs to
change here.

**`features.yaml` is the right retrieval target for Q1's mapping problem.** ~37
short natural-language labels and probes. Embedding those and matching a user's
prose against them is a small, cheap, closed-vocabulary nearest-neighbour
problem — exactly the shape the concept-normalisation literature in Q1 handles.

**`conditions.yaml`, `red_flags.yaml`, `actions.yaml`, `weights.yaml`: not
retrieval targets at all.** Red flags in particular must never be retrieved —
retrieval is approximate and lossy, and `make eval` gates red-flag recall at
100%. A rule that fires because a sentence scored 0.71 cosine is not a
deterministic rule.

**`passages.parquet` is the only genuine RAG corpus**, and it is small: the
knowledge base was authored from **49 cleaned documents**
([KNOWLEDGE_BASE.md](../KNOWLEDGE_BASE.md), and
[`propose.py`](../../services/data/src/herhealth_data/retrieval/propose.py)
states it directly). Sentence-level chunking over 49 documents is a few thousand
vectors. [`index.py`](../../services/data/src/herhealth_data/retrieval/index.py)
already justifies brute-force exact cosine over FAISS at that size, and that
reasoning holds.

### 2b. Fine-tuning

**None of the seven files is SFT data, and `evidence.csv` least of all.** TRL's
[dataset formats page](https://huggingface.co/docs/trl/en/dataset_formats)
enumerates exactly what the tooling accepts, and there is no tabular type:

```json
{"text": "The sky is blue."}
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
{"prompt": "The sky is", "completion": " blue."}
{"prompt": [{"role": "user", ...}], "completion": [{"role": "assistant", ...}]}
```

[`SFTTrainer`](https://huggingface.co/docs/trl/en/sft_trainer) accepts
*language modeling* or *prompt-completion* types, in *standard* or
*conversational* format, and nothing else. A CSV grid can of course be
*serialised* into `{"text": ...}` strings, but that is the point: you would be
training a model to reproduce a lookup table it cannot then be queried
deterministically against. The table already exists, is already exact, is already
diffable in git, and is already checked by `make validate` and
`make verify-quotes`. Fine-tuning on it converts a checked artefact into an
unchecked approximation of itself — and it destroys the property the whole
verification protocol rests on, that every row traces to a sentence.

**What *would* be legitimate SFT data does not exist yet.** Two candidates:

1. **Feature extraction.** `{"prompt": <her prose>, "completion": <feature_id: value JSON>}`
   — a bounded, checkable transduction task with a closed output vocabulary. The
   pairs would have to be authored; they are not in the repo.
2. **Probe phrasing.** English probe text into fr/ar_eg renderings.
   `CLAUDE.md` currently forbids authoring `fr`/`ar`/`ar_eg` probe keys, so this
   is out of scope today.

Note what both have in common: neither is the triage decision.

**Multi-turn is representable and the mechanism matters for Q4.** TRL supports
conversational datasets and `assistant_only_loss=True`, which *"ensures that loss
is computed **only** on the assistant responses, ignoring user or system
messages"*, and `completion_only_loss` which is the default for prompt-completion
data. Single-turn QA rows have no user turns after the first, so no amount of
masking recovers turn-taking behaviour that is absent from the data. This is the
mechanical explanation for the collapse the repo observed; see Q4.

### 2c. NHS `citable_only` under both paths

The constraint is clear and both paths respect it differently:

- **RAG: compatible, already enforced.** NHS text may be quoted into
  `source_quote` and **must never enter `passages.parquet`**. The
  [retrieval package docstring](../../services/data/src/herhealth_data/retrieval/__init__.py)
  says `may_be_ingested` is carried on every passage *"rather than looked up at
  the end"* — the licence filter is a field on the data, not a step someone can
  forget. That is the correct design.
- **Fine-tuning: incompatible, and structurally so.** NHS backs **37 of 89
  evidence rows and all 14 red flags** ([KNOWLEDGE_BASE.md §9](../KNOWLEDGE_BASE.md)).
  Training on NHS text puts Crown-copyright content into model weights, from
  which it cannot be filtered, audited or removed — there is no
  `may_be_ingested` flag inside a weight matrix. `sources.yaml` records NHS as
  Crown copyright with **no reuse grant** and no Open Government Licence. **A
  fine-tune over the corpus that backs the red flags is not available to this
  project.** That alone rules out the most valuable-looking fine-tuning target.

### 2d. Documentation drift between `CLAUDE.md` and the files on disk

> **Status: fixed in the working tree, after this section was written.**
> `CLAUDE.md` now carries the parsed counts, the by-source and by-strength
> breakdowns, the twelve authored condition ids, and an explicit warning that
> `wc -l` gives the wrong row count. The comparison below is kept as the record
> of what was found and why the correction was made — **not** as a description
> of the repository's current state.

**Reported as an observation about the documentation, not as a defect in the
knowledge base.** The files are internally consistent and pass their own
validators; it is the prose description of them that had moved on. This mattered
because `CLAUDE.md` is the binding context document, so anything written from it
— including the first draft of this note — inherited the drift.

| | `CLAUDE.md` says | On disk (parsed) |
|---|---|---|
| Evidence rows | ~350 | **89** |
| Conditions | 17 | **12** |
| Features | ~50 | **37** defined, 30 used |
| Sources in the table | **4** (MedlinePlus, NICHD, CDC, NHS) | **5** |
| Red flags | ~25 | **14** |

Three specifics worth naming:

1. **A fifth source exists and is absent from `CLAUDE.md`'s source table.**
   `womenshealth` (Office on Women's Health) is in `sources.yaml` with status
   `available`, and it **backs 30 of the 89 evidence rows — the second-largest
   contributor after NHS.** `CLAUDE.md`'s licence table lists only four sources.
   Anything reasoning about licence coverage from `CLAUDE.md` alone is reasoning
   from an incomplete list.
2. **The condition roster differs in both directions.** On disk but not in
   `CLAUDE.md`'s 17-row table: `thrush`, `bacterial_vaginosis`. In `CLAUDE.md` but
   not on disk: primary ovarian insufficiency, inherited bleeding disorder,
   hypothyroidism, functional hypothalamic amenorrhoea, hyperprolactinaemia,
   endometrial polyp, pregnancy-related bleeding. `CLAUDE.md`'s table is a
   *roadmap* — it marks most of those "sources confirmed, not authored" or
   "blocked" — so this is largely planned-vs-built rather than contradiction. But
   `thrush` and `bacterial_vaginosis` are built and undocumented, which is the
   direction that surprises a reader.
3. **`docs/KNOWLEDGE_BASE.md` was the accurate document throughout.** It states 37
   features, 12 conditions, 89 evidence rows, 14 red flags, 5 sources, and it names
   the Office on Women's Health as backing "30 of 89 rows". Its numbers match a
   parse of the files exactly. The drift was confined to `CLAUDE.md`.

**The general lesson, which outlives this particular fix:** two documents
restating the same counts will diverge, and the one that diverges is the one
nobody regenerates. `CLAUDE.md`'s repair adds the instruction *"If you change a
file, change the number here in the same commit"*, which is a discipline rather
than a mechanism. A `make` target that regenerates the counts — the parse in this
section is four lines of Python — would make the drift unrepresentable instead of
merely forbidden, which is the pattern this repo already prefers everywhere else
(generated `evidence.csv`, `may_be_ingested` as a field, `allowed_values` on
features).

### Q2 verdict

Retrieval: `passages.parquet` and `features.yaml` yes; `evidence.csv` no, and
that is correct rather than a limitation. Fine-tuning: no file is SFT data as it
stands, the only defensible targets are bounded sub-tasks whose data does not
exist yet, and the NHS licence structurally bars the highest-value corpus.

---

## Q3. A smaller model or an API for semantic search

**Start from the corpus size, because it settles most of the question.** 37
features, 12 conditions, **89** evidence rows, 14 red flags, and a passage
corpus derived from **49 documents** — a few thousand sentences. Embedding the
entire knowledge base once is on the order of **tens of thousands of tokens**,
not millions. At API list prices that is **fractions of a US cent per full
re-index**. Cost is not a decision variable here; latency, licence, data
residency and operational simplicity are.

### 3a. The options

Prices are per million tokens, from first-party pricing pages, read 2026-08-17.

| Option | Type | Multilingual / Arabic | Dims | Context | Licence | Self-host on 1 GPU | Price |
|---|---|---|---|---|---|---|---|
| [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | open weights | 100+ langs | ≤1024, MRL 32–1024 | 32K | Apache 2.0 | yes, comfortably | free |
| [Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | open weights | 100+ langs | ≤2560, MRL | 32K | Apache 2.0 | yes | free |
| [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | open weights | 100+ langs | ≤4096, MRL | 32K | Apache 2.0 | yes, tighter | free |
| [Qwen3-Reranker-0.6B / 4B / 8B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) | open weights | 100+ langs | n/a (scores pairs) | 32K | Apache 2.0 | yes | free |
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | open weights | 100+ langs | 1024 | 8192 | **MIT** | yes (XLM-R large class) | free |
| [intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large) | open weights | 100 langs | 1024 | **512** | MIT | yes | free |
| [jina-embeddings-v3](https://arxiv.org/abs/2409.10173) | open weights + API | multilingual | 1024, MRL 32–1024 | 8192 | see model card | yes (570M params) | see Jina pricing |
| [voyage-4-large](https://docs.voyageai.com/docs/pricing) | hosted API | not stated on pricing page | — | — | proprietary | no | **$0.12** (200M free) |
| [voyage-4](https://docs.voyageai.com/docs/pricing) | hosted API | — | — | — | proprietary | no | **$0.06** (200M free) |
| [voyage-4-lite](https://docs.voyageai.com/docs/pricing) | hosted API | — | — | — | proprietary | no | **$0.02** (200M free) |
| [voyage-multilingual-2](https://docs.voyageai.com/docs/pricing) | hosted API | multilingual (by name) | — | — | proprietary | no | **$0.12** (50M free) |
| [rerank-2.5 / rerank-2](https://docs.voyageai.com/docs/pricing) | hosted API | — | n/a | — | proprietary | no | **$0.05** (200M free) |
| [rerank-2.5-lite / rerank-2-lite](https://docs.voyageai.com/docs/pricing) | hosted API | — | n/a | — | proprietary | no | **$0.02** (200M free) |
| [text-embedding-3-large](https://developers.openai.com/api/docs/pricing) | hosted API | multilingual | 3072 (shortenable) | — | proprietary | no | **$0.13** |
| [text-embedding-3-small](https://developers.openai.com/api/docs/pricing) | hosted API | multilingual | 1536 | — | proprietary | no | **$0.02** |
| [Cohere Embed 4 / Rerank](https://cohere.com/pricing) | hosted API | multilingual | — | — | proprietary | no | **not verified — see below** |

**Verification notes, because several cells above are honestly incomplete:**

- **`voyage-3-large`, `voyage-3.5`, `voyage-3.5-lite` no longer appear on Voyage's
  pricing page.** The [current page](https://docs.voyageai.com/docs/pricing)
  lists a generation-4 line (voyage-4-large / voyage-4 / voyage-4-lite /
  voyage-context-4 / voyage-code-4) and lists `voyage-multilingual-2` among older
  models. The models named in the original question are superseded; do not plan
  against them.
- **Cohere per-token pricing could not be verified.**
  [cohere.com/pricing](https://cohere.com/pricing) surfaced only Model Vault
  dedicated-instance rates (Embed 4 at $4.00–$5.00/hour; Rerank 3.5 / 4 Fast /
  4 Pro at $5.00–$10.00/hour) and
  [the pricing-model doc](https://docs.cohere.com/docs/how-does-cohere-pricing-work)
  states only that *"Our Embedding models are priced based on the number of
  tokens embedded"* and *"Our Rerank models are priced based on the quantity of
  searches"*, defining a search unit as *"one query with up to 100 documents to
  be ranked"* with documents over 500 tokens split into chunks. **The per-million
  and per-search figures are not asserted here.**
- **Qwen3-Embedding dimensions and context** are from the 0.6B card, which
  documents the whole series; the 4B and 8B rows above are that card's own
  statements about its siblings, not separately fetched cards.
- **Arabic-specific per-language MTEB scores were not obtained.** The
  [MMTEB paper](https://arxiv.org/abs/2502.13595) covers *"over 500
  quality-controlled evaluation tasks across 250+ languages"*, but this note did
  not retrieve a per-language Arabic or French breakdown from the leaderboard.
  Do not claim an MTEB Arabic ranking without fetching it. (Arabic *retrieval*
  evidence does exist and is used above — it comes from Alsubhi et al.'s six-dataset
  RAGAS study, not from MTEB.)
- **jina-embeddings-v3 licence not verified.** The model card exceeded the fetch
  size limit. The [paper](https://arxiv.org/abs/2409.10173) gives 570M params,
  1024 dims with Matryoshka down to 32, 8192 context, and five task-specific LoRA
  adapters (retrieval-query, retrieval-passage, clustering, classification, text
  matching). Jina models have historically carried a CC-BY-NC restriction on
  some weights; **check the card before assuming commercial reuse.**

### 3b. What size of model this corpus actually justifies

**Small.** Two independent lines of evidence:

[MMTEB](https://arxiv.org/abs/2502.13595) reports that *"the best-performing
publicly available model is multilingual-e5-large-instruct with only 560 million
parameters"* — i.e. a sub-1B encoder beat much larger LLM-based embedders on a
250-language benchmark. Parameter count is not the axis that decides embedding
quality.

[Optimizing RAG Pipelines for Arabic: A Systematic Analysis of Core
Components](https://arxiv.org/abs/2506.06339) (Alsubhi et al. — **this is the
paper the repo's `embed.py` and `passages.py` cite as "ADR 0010"**) evaluates
chunking, embedding models, rerankers and LLMs across six Arabic datasets with
RAGAS, and concludes in its abstract: *"sentence-aware chunking outperforms all
other segmentation methods, while BGE-M3 and Multilingual-E5-large emerge as the
most effective embedding models."* Both are ~560M-parameter XLM-R-class encoders.

**The scores quoted in the repo's docstrings are accurate and are now
page-citable.** PDF on disk at
[`sources/q3-arxiv-2506.06339-…pdf`](sources/q3-arxiv-2506.06339-alsubhi-arabic-rag-embedding-chunking-evaluation.pdf),
12 pages:

- **Embedding models — Table 2, p9** (averages across the six datasets):
  **BGE-M3 70.99**, **E5-Large 70.31**, Arctic-Embed 69.48, GTE-Base 68.48,
  Matryoshka (Arabic-Triplet-Matryoshka-V2) **66.46**, Arabic-MPNet **45.92**.
  Body text, p7: *"bge-m3 achieved the highest overall score (70.99) across the
  six datasets, closely followed by multilingual-e5-large (70.31)."* The paper's
  own conclusion, p8: *"multilingual, contrastively trained models such as bge-m3
  and multilingual-e5-large provide superior retrieval performance in Arabic RAG
  pipelines, even compared to Arabic-specialized models."* **`embed.py`'s
  docstring is correct in every figure.**
- **Chunking — Table 1, p8** (averages): fixed-size **69.41**, recursive
  **69.13**, sentence-aware **74.78**, semantic **66.92**. Body text, p7:
  *"sentence-aware chunking achieves the highest average overall score across all
  datasets (74.78), outperforming fixed-size (69.41), recursive (69.13), and
  semantic chunking (66.92)."* **`passages.py`'s docstring is correct.** One
  precision worth adding when it is cited: sentence-aware wins on the *average*
  and leads in **four of six** datasets — fixed-size wins SaudiWiki (86.69),
  recursive wins ArSQUAD (52.35), and semantic wins Quran Tafseer (82.45). The
  claim is "best overall", not "best everywhere".

**Concrete implication:** the current plan of serving embeddings from
**Qwen3.5-9B** is oversized for this corpus by roughly an order of magnitude in
parameters. Either `bge-m3` (MIT, 1024 dims, 8192 context, already the code's
`DEFAULT_MODEL`) or `Qwen3-Embedding-0.6B` (Apache 2.0, MRL down to 32 dims, 32K
context) is the right class. `bge-m3` has the stronger Arabic-specific evidence;
`Qwen3-Embedding-0.6B` has the more permissive dimension flexibility and matches
the serving model family. **Either is defensible; the 9B is not, on retrieval
grounds.**

### 3c. Is a reranker warranted?

**No, not at serving time — and reading the full Alsubhi paper strengthens this
from a judgement call into a source-grounded one.**

The abstract says only that the reranker *"significantly boosts faithfulness in
complex datasets"*, which on its own reads as a point in favour. **The body says
when, and why, and the condition is not met here.** Table 3, p9 (`bge-reranker-v2-m3`,
overall mean RAGAS scores without → with reranker):

| Dataset | Without | With | Δ |
|---|---|---|---|
| ARCD | 80.29 | 86.31 | **+6.02** |
| ArSQUAD | 51.97 | 56.47 | **+4.50** |
| QA4MRE | 48.97 | 53.57 | **+4.60** |
| Hindawi Books | 73.70 | 77.74 | **+4.04** |
| Quran Tafseer | 82.72 | 83.45 | +0.73 |
| **SaudiWiki** | **88.31** | **87.39** | **−0.92** |
| Average | 70.99 | 74.15 | +3.16 |

The paper's own explanation, p8: *"SaudiWiki saw a slight drop in overall score
despite improvements in precision, suggesting that reranking may offer limited
benefits when the initial retrieval quality is already high."* And its summary
answer to RQ3, p9: *"Its impact was less pronounced in highly structured
datasets, suggesting reranking is most beneficial when initial retrieval lacks
semantic precision."*

**That is precisely this repo's situation, and the one dataset where the reranker
*hurt* is the one that most resembles it.** SaudiWiki is described on p7 as
benefiting from the *"structured and uniform nature of Wikipedia articles"* — a
clean, well-formed corpus with high baseline retrieval. This project's corpus is
sentence-split text from 49 curated public-health pages, searched by **exact**
brute-force cosine, not approximate ANN:
[`index.py`](../../services/data/src/herhealth_data/retrieval/index.py) already
argues that FAISS earns its place only above ~100k vectors and that below that an
exhaustive dot product returns *exact* nearest neighbours. **A reranker's job is
repairing imprecise first-stage retrieval. There is no imprecision here to
repair.** It would add a second model, a second HTTP hop, and latency to every
turn of a consultation that already runs to ten questions in the escalation-screen
case (ADR 0007).

**Where it might still earn its place:** the *authoring* path
([`propose.py`](../../services/data/src/herhealth_data/retrieval/propose.py)),
where precision at the top of the candidate list directly determines how much
reading a human reviewer does, and where latency is irrelevant. The Alsubhi
result that reranking helps most on *"inference-heavy"* and semantically
ambiguous retrieval (p8) fits gap-filling for `argues_against` rows — which ADR
0007 finding 1 identifies as the knowledge base's biggest hole. If one is tried,
[`bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) is the
model the paper actually tested;
[Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) (Apache
2.0, 32K context, 100+ languages, MMTEB-R 66.36 / MLDR 67.28) is the alternative.
Either way it is a measurable question, not an argued one.

### 3d. Hosting health data on a US API, with users in Egypt

Stating what can be stated and no more. **This note did not review Egyptian data
protection law and makes no legal claim.** Three factual observations:

1. A hosted embedding API means **the user's free-text symptom description leaves
   the deployment** and reaches a third-party US processor. That is a different
   data-flow than the self-hosted plan, and it is a disclosure that would have to
   appear in `DATASHEET.md` and in any user-facing privacy notice.
2. The repo's stated deploy target is **a self-hosted GPU server** with
   `services/model` behind HTTP (`CLAUDE.md`, "Deploy"). A hosted API is a
   material architectural change, not a swap of one URL for another.
3. **Cost gives no reason to make that change.** At ~100 KB of knowledge text,
   even the most expensive option in the table costs a fraction of a cent per
   full re-index, and Voyage's free tier alone (200M tokens) exceeds this
   project's lifetime embedding volume by orders of magnitude — as would running
   `bge-m3` locally for free.

### Q3 verdict

The corpus justifies a ~0.6B encoder, self-hosted, and the code already names
one. A serving-time reranker is **not** warranted — the Arabic paper's own
condition for reranker benefit ("when initial retrieval lacks semantic
precision") is not met by exact brute-force cosine over a few thousand vectors,
and the one dataset in that study with high baseline retrieval quality got
*worse* with a reranker. It may be worth measuring on the authoring path. Hosted
APIs solve a cost problem this project does not have while creating a data-flow
question it does not currently have.

---

## Q4. Reusing the fine-tuned model from the team's own paper

### 4a. What is actually in the repo

Searched exhaustively (excluding `.venv`) for LoRA/PEFT adapters, training
configs, checkpoints, model ids and meeting notes. Findings:

- **No adapter, no checkpoint, no training config, no `trl`/`peft` dependency.**
  Nothing in `services/data/`, `services/backend/`, `pyproject.toml` files or
  `infra/` refers to a fine-tuned artefact.
- **`docs/meetings/` is empty.**
- **`docs/adr/0010` does not exist** (see the header caveat).
- **The QA dataset is present, and it is the important find.**
  [`services/data/eval/benchmark/gold_seeds_styled.csv`](../../services/data/eval/benchmark/gold_seeds_styled.csv)
  is **540 rows** with columns `Question, Answer, Topic, Keywords, Style` —
  **90 canonical seed questions × 6 register styles** (`canonical`, `clinical`,
  `layperson`, `indirect_cultural`, `ambiguous`, `emotionally_concerned`), across
  13 topics (PCOS 180, Pregnancy 180, then Irregular Periods, Menarche,
  Menopause, Menstrual Cycle/Flow/Health/Pain/Problems, Menstruation, PMS,
  Symptoms at 12–18 each).

**That file is single-turn QA, and its shape explains the collapse.** Each row is
one question and one complete answer. There is no row anywhere in it where the
correct response is *another question*. The
[benchmark README](../../services/data/eval/benchmark/README.md) confirms this is
the artefact "as it came out of the earlier evaluation" and is to be kept
immutable.

The supervisor's request can therefore be stated precisely: **use a model that
was SFT'd on 540 (question → complete answer) pairs, inside a system whose
required behaviour is (partial information → one clarifying question).** The
training data contains zero examples of the required behaviour.

### 4b. The primary literature on why that collapses

**Format and behaviour follow the training distribution.**
[TRL's dataset formats](https://huggingface.co/docs/trl/en/dataset_formats)
make the mechanism explicit: SFT minimises token-level cross-entropy on the
completion, and the *"prompt-only output includes a `'<|assistant|>\n'`,
indicating the beginning of the assistant's turn and expecting the model to
generate a completion"*. Train on 540 examples where every assistant turn is a
finished answer and the model learns that an assistant turn *is* a finished
answer. Clarification-seeking at 0.000 is not a mysterious regression; it is the
model doing exactly what it was shown. TRL's `assistant_only_loss` exists so that
loss can be restricted to assistant turns in **conversational** data — a facility
that is inapplicable when the data has only one assistant turn per example.

**Catastrophic forgetting is documented and is the general case.**
[Improved Supervised Fine-Tuning for Large Language Models to Mitigate
Catastrophic Forgetting](https://arxiv.org/abs/2506.09428) frames the phenomenon
directly: SFT degrades the model's general abilities. Its proposed mitigation is
to **reconstruct the base model's likely instruction distribution and mix it back
into the fine-tuning set** — i.e. replay. [Mapping Post-Training Forgetting in
Language Models at Scale](https://arxiv.org/pdf/2510.17776) studies the same
effect systematically. *These two were located via search; abstracts were read,
full texts were not.*

**The repo's specific pattern is the known worst case.** 540 examples,
narrow-topic (two-thirds of rows are PCOS or Pregnancy), single-turn, single
output shape. That is a small, homogeneous, format-uniform SFT set — precisely
the configuration the forgetting literature identifies as maximally distorting.
And the observed result matched: French under-triage 0.994 means "routine" for
538 of 540 cases, i.e. **the model collapsed onto the majority output shape of
its training data** rather than losing accuracy diffusely.

**Cross-language consistency improving during that collapse is diagnostic, not
reassuring**, and the repo already says so in
[`actions.yaml`](../../knowledge/actions.yaml)'s header: *"a model that collapses
onto one answer in every language scores perfectly on text consistency while
being maximally unsafe."* No external source is needed for that; it is arithmetic.

**LoRA would have reduced but not removed the damage.**
[LoRA Learns Less and Forgets Less](https://arxiv.org/abs/2405.09673) finds that
LoRA *"substantially underperforms full finetuning"* on target-domain
performance while *"better maintain[ing] the base model's performance on tasks
outside the target domain"*, mitigating forgetting more than weight decay or
dropout and helping *"maintain more diverse generations"*, with full fine-tuning
learning perturbations of rank **10–100×** greater than typical LoRA
configurations. **Read carefully in this context:** clarification-seeking is an
*outside-the-target-domain* behaviour relative to a QA fine-tune, so LoRA is the
right tool if a fine-tune is used at all — but "forgets less" is not "does not
forget", and the same paper says the target-task gain is smaller. LoRA changes
the trade, it does not remove it.

### 4c. Practical options that honour the request

**Option A — serve the adapter alongside the base model, and route per task.**
This is fully supported infrastructure.
[vLLM's LoRA documentation](https://docs.vllm.ai/en/latest/features/lora.html)
gives: `--enable-lora`; `--lora-modules` to register adapters at startup, e.g.

```
vllm serve <base-model> \
    --enable-lora \
    --lora-modules '{"name": "herhealth-qa", "path": "<adapter-path>", "base_model_name": "<base-model>"}'
```

Multiple adapters run against one base model; `/v1/models` shows the hierarchy
with `parent` linking each adapter to its base. Adapters can be loaded and
unloaded at runtime via `POST /v1/load_lora_adapter` and
`/v1/unload_lora_adapter` (requires `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True`), and
`--max-lora-rank` / `--max-loras` bound the memory cost. **Clients select an
adapter by passing its name as the `model` parameter** — so the backend can call
the fine-tune for one job and the base model for another, over the same server,
with no second GPU and no second deployment. This makes "use the paper's model"
and "do not let it decide urgency" simultaneously satisfiable, which is the key
point for the supervisor conversation.

*Caveat:* this presumes the paper's artefact **is** a LoRA adapter. Nothing in the
repo establishes that; if it was a full fine-tune, it is a second full model and
the memory argument changes entirely. **Ask which it is before planning around
this.**

**Option B — use the fine-tune only for a bounded sub-task.** The two candidates
identified in Q2:

- **Answer phrasing.** The model was trained on 540 answers *in this exact
  domain, in six registers including `layperson`, `indirect_cultural` and
  `emotionally_concerned`*. That is genuinely valuable and genuinely hard to get
  elsewhere: it is a register and tone model for women's reproductive health
  questions. Phrasing the controller's decision into her language is a task where
  the fine-tune is plausibly *better* than the base model, and where being wrong
  costs tone rather than safety.
- **Feature extraction.** Turning prose into `(feature_id, value)` pairs. Riskier
  — the fine-tune was not trained on this and its output vocabulary is closed —
  but it is checkable: the extraction either yields legal values from
  `features.yaml` or it is rejected, and `allowed_values` makes an illegal value
  unrepresentable. That validation is the safety net.

Note that Option B is not a concession — **it is the role `CLAUDE.md` already
assigns to the model**: *"The model extracts feature values and phrases text."*
The fine-tune slots into the existing architecture without changing it.

**Option C — mix multi-turn data into the SFT set.** The mitigation the
forgetting literature recommends is replay
([2506.09428](https://arxiv.org/abs/2506.09428)), and the format fix is
conversational data with `assistant_only_loss=True`
([TRL](https://huggingface.co/docs/trl/en/sft_trainer)). Concretely that means
authoring multi-turn examples where the assistant's turn is *a clarifying
question* rather than an answer. **The repo can generate those.** Every
consultation run by `herhealth-triage` produces a
[`Transcript`](../../services/backend/src/herhealth_backend/triage/dialogue.py)
of turns; the controller's chosen question at each step is a ground-truth
"correct next question" label produced by deterministic code. That is a
genuinely attractive path — but note what it does: **it trains the model to
imitate the controller, which means the controller has to exist and be right
first.** It is an argument for keeping `should_stop`, not for replacing it.

### 4d. The supervisor-facing framing

**What the fine-tuned model can safely own:**

- Phrasing the controller's chosen probe as a question in her language and
  register.
- Phrasing the controller's final decision, with the citations the controller
  supplies.
- Feature extraction, *if* every output is validated against
  `features.yaml.allowed_values` and anything illegal is rejected rather than
  coerced.

**What it must not own, and the evidence to show:**

- **Whether to ask another question.** Show
  [MediQ](https://arxiv.org/abs/2406.00922): naive prompting to ask degrades
  accuracy; the fix that recovered **+22.3%** was an *external* abstention module
  with a confidence threshold, and even that closed only **51.2%** of the gap to
  full information.
- **What urgency to assign.** Show the repo's own 0.718 English under-triage and
  0.994 French/Arabic under-triage after fine-tuning; show
  [EQUITRIAGE](https://arxiv.org/abs/2605.03998) (decision-flip rates 9.9–43.8%,
  directional female under-triage, across 374,275 evaluations); show
  [MECR-RAG](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12887567/) where the
  bare LLM baseline scored **0.542 accuracy** and structure took it to 0.802.
- **Whether a red flag has fired.** No source needed. Red-flag recall is gated at
  100% in CI. A probabilistic component cannot be gated at 100%.

**The framing that makes this a yes rather than a no:** the supervisor's request
and the safety constraint are not in conflict, because
[vLLM multi-LoRA serving](https://docs.vllm.ai/en/latest/features/lora.html)
lets the paper's model be *in the deployed system, on the serving path, cited in
the write-up*, while the four action codes continue to come from Python. The
answer is "yes, here, for these jobs" — with a named mechanism and a named
boundary — not "no".

---

## Q5. How a model can reason like a clinician

The user's description — *"ask for clarifying questions, look for common symptoms
and then match with matching conditions and then eliminate based on other
clarifying questions"* — is an accurate description of **hypothetico-deductive
reasoning**, and it is what the primary literature actually implements. The
interesting finding is not whether that model of reasoning is right. It is
**where each system puts the decision**.

### 5a. AMIE — chain-of-reasoning inside the model, with staged structure

[Towards Conversational Diagnostic AI](https://arxiv.org/abs/2401.05654)
(Google; also in [Nature](https://www.nature.com/articles/s41586-025-08866-7))
is the strongest published result for LLM diagnostic dialogue. In a randomised,
double-blind crossover OSCE-style study — **149 case scenarios** from providers
in Canada, the UK and India, **20 PCPs** for comparison, evaluated by specialist
physicians and patient actors — AMIE *"demonstrated greater diagnostic accuracy
and superior performance on 28 of 32 axes according to specialist physicians and
24 of 26 axes according to patient actors."*

**What drives asking.** A **chain-of-reasoning** executed before every dialogue
turn — [Google's own description](https://research.google/blog/amie-a-research-ai-system-for-diagnostic-medical-reasoning-and-conversations/)
gives three sequential steps: (1) summarise positive and negative symptoms and
history, produce a current differential, **note the missing information needed**,
and assess confidence and urgency; (2) formulate the response and further
questions to acquire that missing information; (3) refine for factuality and
tone. **What drives stopping.** Confidence in the differential, plus an explicit
phase structure: history-taking → differential diagnosis and management →
follow-up questions.

**Where the decision sits: inside the model**, though decomposed into a scripted
sequence of model calls with a fixed schema — which is a controller in
everything but implementation language. And note the authors' own stated
limitation: *"Clinicians were limited to unfamiliar synchronous text-chat which
permits large-scale LLM-patient interactions but is not representative of usual
clinical practice."*

**Relevance here, stated carefully.** AMIE is the one primary source that
*partially supports* moving toward model-driven dialogue, and it should not be
argued away. Three real differences: AMIE performs **diagnosis**, which this
system is forbidden to do; AMIE was evaluated in English against PCPs, with no
Arabic or French result; and AMIE required a bespoke self-play training
environment with automated feedback, which is far outside a capstone's budget.
"AMIE works" is not evidence that "a QA-fine-tuned Qwen will work".

### 5b. MediQ — the ask-or-answer decision moved outside the model

Covered in Q1. The point that belongs here: MediQ's Expert System is a five-stage
pipeline — Initial Assessment, **Abstention**, Question Generation, Information
Integration, Decision Making — and the [full text](https://arxiv.org/html/2406.00922v3)
describes abstention as a **separate confidence-estimation module** with a
threshold, tested in numerical / binary / Likert / rationale / self-consistency
variants. **What drives asking:** estimated confidence below threshold. **What
drives stopping:** confidence above it. **Where the decision sits: outside the
model's free generation.**

This is the closest published analogue to `should_stop` rule 4
(`stop_confidence` and `stop_margin`), and it is a direct endorsement of that
rule's *shape*. The difference is the source of the confidence: MediQ uses the
model's self-reported confidence — which the paper found poorly calibrated,
improved by rationale generation (expected calibration error 2.1 vs 2.9) — while
this repo computes plausibility from cited evidence rows and a fixed weight
scale. **The repo's version is strictly more inspectable and does not depend on
model calibration at all.**

### 5c. Information-gain question selection — the decision-theoretic version

This is the literature that most directly formalises "which question should I ask
next", and it is exactly what
[`_separation`](../../services/backend/src/herhealth_backend/triage/engine.py)
is an approximation of.

[BED-LLM: Intelligent Information Gathering with LLMs and Bayesian Experimental
Design](https://arxiv.org/abs/2508.21184) (ICLR 2026) proposes *"a general-purpose
approach for improving the ability of large language models to intelligently and
adaptively gather information ... using the framework of sequential Bayesian
experimental design"*, **iteratively choosing questions or queries that maximise
the expected information gain (EIG)**, with EIG formulated *"in a principled way
using a probabilistic model derived from the LLM's predictive distributions"*.
**Where the decision sits: an external decision-theoretic loop** that consumes
the model's distributions. It reports substantial gains over *"purely
prompting-based design generation"*.

[Amortising Bayesian Experimental Design for Sequential Information Gathering in
LLMs](https://arxiv.org/abs/2607.03426) takes the next step — training the EIG
objective *into* a policy via multi-turn GRPO with an EIG reward — and reports
improved information-seeking **on MediQ**. [CA-BED](https://arxiv.org/html/2606.01182)
does inference-time probabilistic dialogue planning over multiple turns.

**This is the most directly actionable finding in the note for
[ADR 0007 finding 2](../adr/0007-what-the-first-real-consultations-showed.md).**
That ADR records that `_separation` *"sums the absolute weight a feature could
apply without modelling which answer is likely"*, so question selection barely
depends on the answers and the controller runs a near-fixed questionnaire —
`vulval_itching` was never asked in a case about vulval itching. **Expected
information gain is exactly the missing quantity.** With independent-logistic
plausibilities already computed per condition (ADR 0005), the machinery to weight
each candidate answer by its current probability and score a feature by expected
reduction in uncertainty is largely present. That is a change *within* the
deterministic controller, and the primary literature endorses the objective.

### 5d. CRAFT-MD — the evaluation warning

[An evaluation framework for clinical use of large language models in patient
interaction tasks](https://www.nature.com/articles/s41591-024-03328-5) (Nature
Medicine, 2024) — CRAFT-MD, Conversational Reasoning Assessment Framework for
Testing in Medicine — evaluates clinical LLMs through simulated multi-turn
dialogue with a patient-AI agent and a grader-AI agent, across GPT-4, GPT-3.5,
Mistral and LLaMA-2-7b over 12 medical specialties.

**This note could not retrieve the accuracy numbers.** nature.com redirected to
an authentication endpoint, medRxiv returned 403, PubMed returned a cookie wall,
and the OpenReview PDF returned a browser-verification page. The widely-repeated
finding is that accuracy drops substantially from structured multiple-choice
vignettes to conversational history-taking, but **no specific percentage is
asserted here because none could be verified.** If this claim is needed for the
thesis, obtain the paper through the university library and cite the page.

What *can* be stated from the framework description: CRAFT-MD exists because
**vignette benchmarks overstate conversational performance**, and it grades on
whether the model gathers the right history rather than on final-answer accuracy
alone. That is a warning about the repo's own evaluation, not just about LLMs —
see 5f.

### 5e. Abstention with external knowledge

[KnowGuard: Knowledge-Driven Abstention for Multi-Round Clinical
Reasoning](https://arxiv.org/pdf/2509.24816) (authors at Harvard and NUS)
addresses when a system should abstain versus ask another round, driving the
decision from **external structured knowledge rather than model confidence
alone**, evaluated against MediQ. **This note could not extract the abstract or
results** — the PDF's content streams did not decompress into readable text — so
only the framing is reported and no numbers are claimed. The framing alone is
worth recording: it is the same move this repo makes, using a knowledge base
rather than a logit to decide sufficiency.

### 5f. Mapping the findings onto this repo's controller

| Repo mechanism | Literature analogue | Verdict |
|---|---|---|
| `should_stop` rule 1 — red flag escalates, code-only | No direct analogue found; AMIE assesses urgency inside the chain-of-reasoning | **Stronger than the literature.** Nothing published gates emergency escalation deterministically at 100% recall. Keep |
| Escalation screen (most-severe rule wins; probe while a worse rule is one answer away) — [ADR 0007](../adr/0007-what-the-first-real-consultations-showed.md) | Closest is EIG probing ([BED-LLM](https://arxiv.org/abs/2508.21184)): each probe either fires or kills a rule, which is maximal information gain over the rule set | **Supported.** The "exactly one outstanding clause" bound is a structural termination guarantee no probabilistic scheme offers |
| Rule 2 — all live conditions share one action → stop | AMIE's "assess confidence in the differential" phase | Supported |
| Rule 3 — no unasked feature could change the action → stop | Value-of-information: a question with zero expected effect on the decision has zero value | **Directly supported** by the EIG literature |
| Rule 4 — `stop_confidence` + `stop_margin` | [MediQ](https://arxiv.org/abs/2406.00922) Abstention Module with a confidence threshold | **Directly supported, and the repo's version is better founded** — plausibility comes from cited rows, not from model self-report, which MediQ found miscalibrated |
| Rule 5 — `max_questions` = 6 | Not found in any primary source; AMIE and MediQ do not impose a hard budget | **Unsupported by literature, and defensible anyway** as a product judgement. `weights.yaml` already says it is a judgement, not a result |
| `next_question` ranks by `_separation` per burden | EIG ([BED-LLM](https://arxiv.org/abs/2508.21184), [ASIG](https://arxiv.org/abs/2607.03426), [CA-BED](https://arxiv.org/html/2606.01182)) | **This is the weak point, and the literature says how to fix it.** ADR 0007 finding 2 already diagnosed it; EIG is the named replacement |
| Independent logistic, not softmax ([ADR 0005](../adr/0005-plausibility-is-an-independent-logistic.md)) | Abstention / out-of-scope detection ([survey](https://arxiv.org/html/2407.18418)) | **Supported.** The ability to express "none of these fit" is what abstention research is trying to add |
| Cases expressed as feature values, so `make eval` measures the controller alone ([cases README](../../services/data/eval/cases/README.md)) | [CRAFT-MD](https://www.nature.com/articles/s41591-024-03328-5) exists precisely because structured-input evaluation overstates conversational performance | **Contradicted, and the repo already admits it.** The cases README states clarification recall is "near-vacuous" and cross-language agreement "unmeasurable here". CRAFT-MD is the published version of that same warning. Prose-to-feature evaluation is a gap, not a detail |

### 5g. Which questions each Q5 finding bears on

- **AMIE** partly supports Q1's instinct (models can conduct real diagnostic
  dialogue) and contradicts Q4's plan (AMIE needed bespoke self-play training,
  not a 540-row QA fine-tune).
- **MediQ** contradicts Q1's instinct and supports Q4's boundary — the
  ask-or-answer decision belongs outside the model.
- **BED-LLM / ASIG / CA-BED** contradict nothing in the current design and
  identify the one place it is genuinely weak: `_separation`.
- **CRAFT-MD** contradicts the repo's *evaluation*, not its architecture.
- **KnowGuard** supports the knowledge-driven sufficiency decision, with numbers
  unverified.

---

## What the evidence supports

Instinct by instinct, with the citation that decides each.

### 1. "A user can type something not in `features.yaml`, so the closed vocabulary is a problem." — **Supported, and the fix is a mapping layer, not a rewrite**

Real. The mitigation in the primary literature is retrieve-then-constrain:
embedding retrieval over the closed vocabulary, then selection among retrieved
candidates
([multistage concept normalisation, +7.3% to +21.7% F1](https://pmc.ncbi.nlm.nih.gov/articles/PMC12527512/)),
never free generation of identifiers
([ontology-linking failures](https://arxiv.org/pdf/2509.04458)). The out-of-scope
path is architecturally present already via
[ADR 0005](../adr/0005-plausibility-is-an-independent-logistic.md)'s independent
logistic — *"a softmax cannot express 'none of these fit'"* — but has no
input-side counterpart. **Concrete gap: nothing today says "her words matched no
feature."**

### 2. "So replace the deterministic controller with an end-to-end LLM." — **Contradicted, by every primary evaluation found**

- [MediQ](https://arxiv.org/abs/2406.00922): prompting LLMs to ask questions
  *degrades* performance (~11.3% relative); the +22.3% recovery came from an
  **external** abstention module and still closed only 51.2% of the gap.
- [HealthBench](https://arxiv.org/html/2505.08775): context-seeking is where
  frontier models *lag*, and worst-at-16 reliability drops by about a third from
  the mean.
- [EQUITRIAGE](https://arxiv.org/abs/2605.03998): decision-flip rates 9.9–43.8%
  across 374,275 evaluations, with directional female under-triage in some
  models — the exact failure mode this system exists to avoid, in the exact
  population it serves.
- [MECR-RAG](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12887567/): the bare
  LLM baseline scored **0.542** accuracy; adding retrieval and structured
  evidence took it to **0.802** with under-triage at 1.3%. The gain came from
  structure.
- Regulatory reasoning points the same way *as a design argument*.
  [MDCG 2019-11](sources/q1-eu-mdcg-2019-11-software-qualification.pdf) classifies
  by the severity of a wrong decision (Rule 11), and the
  [FDA CDS guidance](sources/q1-fda-cds-software-guidance.pdf) expects a
  recommendation's basis to be reviewable in plain language with its underlying
  sources named (p14–15) — a property the deterministic path has by construction
  and an end-to-end model does not. **Stated carefully:** the FDA carve-out is
  HCP-facing throughout and a patient-facing urgency recommender sits outside it
  *whatever* computes the answer (p13), so this is an argument about
  inspectability, **not** a claim that keeping the controller confers non-device
  status. It does not.

**The one honest counterweight:** [AMIE](https://arxiv.org/abs/2401.05654) beat
20 PCPs on 28 of 32 specialist-rated axes across 149 OSCE scenarios with the
decision inside the model. It is real and it should be cited in the write-up.
It is also English-only, diagnostic rather than triage, and required bespoke
self-play training — so it is not a template this project can follow.

### 3. "The knowledge files could feed RAG or a fine-tune." — **Half supported**

Retrieval: yes for `passages.parquet` and `features.yaml`; no for `evidence.csv`,
whose meaning is ordinal arithmetic that embedding destroys —
[LlamaIndex](https://developers.llamaindex.ai/python/framework/understanding/rag/)
keeps structured data on a different track for this reason. Fine-tuning: **no
file is SFT data**. [TRL](https://huggingface.co/docs/trl/en/dataset_formats)
accepts only language-modeling and prompt-completion types in standard or
conversational format; there is no tabular type, and serialising a checked grid
into training text replaces an exact, diffable, quote-verified artefact with an
approximation of itself. And **NHS `citable_only` structurally bars the
highest-value fine-tuning corpus** — NHS backs 37 of 89 evidence rows and all 14
red flags, and there is no `may_be_ingested` flag inside a weight matrix.

### 4. "A smaller model or an API could do semantic search." — **Strongly supported, and the current plan is oversized**

[MMTEB](https://arxiv.org/abs/2502.13595) reports the best publicly available
multilingual embedder at **560M parameters**. [Alsubhi et
al.](sources/q3-arxiv-2506.06339-alsubhi-arabic-rag-embedding-chunking-evaluation.pdf)
find **BGE-M3 (70.99) and multilingual-E5-large (70.31)** best for Arabic RAG,
ahead of every Arabic-specialised model tested including Arabic-MPNet at 45.92
(Table 2, p9) — both winners ~560M-class. Against a corpus of 37 features, **89**
evidence rows and passages from 49 documents, **serving embeddings from
Qwen3.5-9B is oversized by about an order of magnitude**;
[bge-m3](https://huggingface.co/BAAI/bge-m3) (MIT) or
[Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
(Apache 2.0) is the right class, and `embed.py` already names the first.

A **serving-time reranker is not warranted, and the same paper is the reason.**
Its reranker benefit is explicitly conditional — *"most beneficial when initial
retrieval lacks semantic precision"* (p9) — and on SaudiWiki, the one dataset with
high baseline retrieval quality, adding the reranker made the score **worse**
(88.31 → 87.39, Table 3 p9). Exact brute-force cosine over a few thousand vectors
is the high-baseline case. Worth *measuring* on the authoring path, not the
serving path. A **hosted API is not warranted** either: cost is a fraction of a
cent per re-index, and an API sends users' symptom text to a third-party US
processor, which the self-hosted plan does not.

### 5. "Use the fine-tuned model from our paper." — **Supported for bounded sub-tasks; contradicted for the triage decision**

The QA dataset is
[`gold_seeds_styled.csv`](../../services/data/eval/benchmark/gold_seeds_styled.csv):
540 rows, 90 seeds × 6 registers, **every row a complete answer and none a
clarifying question**. Clarification collapsing to 0.000 is the model reproducing
its training distribution, and the format mechanics are visible in
[TRL's own docs](https://huggingface.co/docs/trl/en/dataset_formats).
Catastrophic forgetting under narrow SFT is documented
([2506.09428](https://arxiv.org/abs/2506.09428)), and LoRA would have reduced but
not removed it — *"LoRA substantially underperforms full finetuning"* on target
tasks while *"better maintain[ing] the base model's performance on tasks outside
the target domain"*
([LoRA Learns Less and Forgets Less](https://arxiv.org/abs/2405.09673)).

**The request is satisfiable without reproducing the collapse.**
[vLLM multi-LoRA serving](https://docs.vllm.ai/en/latest/features/lora.html) —
`--enable-lora`, `--lora-modules`, runtime load/unload, adapter selected per
request via the `model` parameter — lets the paper's model sit on the serving
path for **answer phrasing** (where its six-register, in-domain training is a
genuine asset) and optionally **feature extraction** (where `allowed_values`
validation catches every error), while the four action codes keep coming from
Python. That is a "yes, for these jobs", not a "no".

**Prerequisite before planning:** confirm whether the artefact is a LoRA adapter
or a full fine-tune. Nothing in the repo establishes it, and `docs/meetings/` is
empty.

### 6. "A model can reason like a clinician: ask, match, eliminate." — **Supported as a description of the reasoning; the open question is where the decision sits**

Every primary system implements that loop.
[AMIE](https://arxiv.org/abs/2401.05654) puts it inside a scripted
chain-of-reasoning over three phases. [MediQ](https://arxiv.org/abs/2406.00922)
puts ask-or-answer in an external abstention module.
[BED-LLM](https://arxiv.org/abs/2508.21184) and
[ASIG](https://arxiv.org/abs/2607.03426) put question selection in an external
expected-information-gain loop. **Two of the three put the decision outside the
model — which is what this repo already does.**

The finding that should actually change something: **"eliminate" is the half this
repo cannot do**, and it is a knowledge problem, not a controller problem.
[ADR 0007](../adr/0007-what-the-first-real-consultations-showed.md) finding 1
records that 8 of 12 conditions have zero eliminating rows, so nothing ever
leaves the differential and every consultation returns `URGENT_SAME_DAY`. No
change of architecture fixes that. More `argues_against` and `rules_out` rows
would — and
[`propose.py`](../../services/data/src/herhealth_data/retrieval/propose.py)
exists to find candidates for exactly those, behind the human review gate.

### Two things this note recommends measuring rather than arguing

1. **Expected information gain in `next_question`.** ADR 0007 finding 2 already
   diagnosed `_separation` as answer-independent;
   [BED-LLM](https://arxiv.org/abs/2508.21184) names the objective that fixes it,
   and independent-logistic plausibilities are already computed. Effect on
   question count and on under-triage has to be measured.
2. **Prose-to-feature-value extraction, end to end.** The
   [cases README](../../services/data/eval/cases/README.md) already concedes that
   evaluating from feature values makes clarification recall near-vacuous and
   cross-language agreement unmeasurable.
   [CRAFT-MD](https://www.nature.com/articles/s41591-024-03328-5) is the
   published statement of the same warning. **This is the largest unmeasured
   risk in the system, and it is the layer Q1's worry actually lives in.**

### What could not be verified

Listed so nobody quotes a gap as a finding.

**Closed since the first draft** — the primary documents are now in
[`docs/research/sources/`](sources/) and the claims are quoted with page numbers:

- ~~FDA CDS criteria~~ → **verified.** All four § 520(o)(1)(E) criteria are quoted
  verbatim from p6 of the 29 January 2026 guidance, along with the decisive
  patients-or-caregivers sentence (p13), the time-critical exclusion and
  automation-bias discussion (p14–15), and the enforcement-discretion caveat (p5).
  *Two corrections to the first draft: Criterion 4 is § 520(o)(1)(E)**(iii)**, not
  (iv); and the earlier paraphrase understated the finding — the carve-out is
  HCP-facing throughout, which is a stronger and more adverse result than "the
  exclusion is not a route this project can rely on".*
- ~~Alsubhi et al. numeric scores~~ → **verified with page cites.** Embedding
  averages Table 2 p9 and body p7; chunking averages Table 1 p8 and body p7;
  reranker deltas Table 3 p9. The docstrings in `embed.py` and `passages.py` are
  accurate. Reading the body also **changed a conclusion**: the reranker finding
  is conditional (*"most beneficial when initial retrieval lacks semantic
  precision"*), and the one high-baseline dataset got worse with a reranker — see
  [§3c](#3c-is-a-reranker-warranted).
- ~~`evidence.csv` row count~~ → **verified by parse:** 89 data rows, not the 110
  lines `wc -l` reports. Full breakdown in [§2](#q2-knowledge-file-compatibility-with-rag-and-with-fine-tuning).

**Still open:**

- **CRAFT-MD accuracy numbers**: paywalled or blocked on all four routes tried
  (nature.com auth redirect, medRxiv 403, PubMed cookie wall, OpenReview browser
  check). No vignette-vs-conversation percentage is asserted. The PDF is *not* in
  `docs/research/sources/`. Obtain via the university library before citing a
  number.
- **EQUITRIAGE exact-match accuracy and ESI-1 under-prediction rates**: appeared
  in a search summary, not in the abstract fetched. Not asserted. The verified
  abstract figures (374,275 evaluations; flip rates 9.9–43.8%) are used instead.
- **KnowGuard results**: PDF content streams would not decompress. Framing only,
  no numbers.
- **Cohere Embed 4 / Rerank per-token and per-search prices**: not on any page
  fetched, including the captured
  [`q3-pricing-cohere.html`](sources/q3-pricing-cohere.html) and
  [`q3-docs-cohere-embed.html`](sources/q3-docs-cohere-embed.html). Only
  dedicated-instance hourly rates were found.
- **Arabic-specific MTEB/MMTEB per-language rankings**: not retrieved. Arabic
  *retrieval* evidence comes from Alsubhi et al. instead, which is verified.
- **jina-embeddings-v3 licence**: model card exceeded the fetch size limit; the
  capture [`q3-modelcard-jina-embeddings-v3.html`](sources/q3-modelcard-jina-embeddings-v3.html)
  is on disk at 10.9 MB but was not read. Historically some Jina weights carry
  CC-BY-NC. Check before use.
- **MDCG 2019-11 Revision 1 (reported 17 June 2025)**: this note read the
  original. Revision contents unverified. *(A related document,
  [`q1-eu-mdcg-2020-1-clinical-evaluation-mdsw.pdf`](sources/q1-eu-mdcg-2020-1-clinical-evaluation-mdsw.pdf),
  is on disk and was not read for this note.)*
- **Whether the team's fine-tuned model is a LoRA adapter or a full fine-tune.**
  **Partly answered:** the team reports it was trained with **QLoRA**, which makes
  the artefact an ordinary LoRA adapter and puts the vLLM adapter-serving path in
  scope. This is a recollection, not a verified fact — no adapter, training
  config or checkpoint exists anywhere in the repo, and `docs/meetings/` is empty.
  **Still needed before planning around it:** the adapter rank and target modules
  (for `max_lora_rank`), and confirmation of the base checkpoint it was fitted
  against. A QLoRA adapter is fitted against an NF4-quantised base, so serving it
  on an unquantised base is a small distribution shift that should be measured
  rather than assumed.
- ~~Seven defined features carry no evidence row.~~ **Closed.** The check was run
  after this note was drafted: all seven are load-bearing via `red_flags.yaml`
  clauses, and no feature is dead weight. See §2 for the numbers.

*(`docs/adr/0010` and the `CLAUDE.md` counts were open in the first draft and are
now closed — see the header caveats. Both were fixed by another agent in the
working tree, not by this note.)*

**Sources on disk but not read for this note**, listed so they are not mistaken
for gaps: MedHELM (`q1-arxiv-2505.23802`), MTEB original (`q3-arxiv-2210.07316`),
BGE-M3 paper (`q3-arxiv-2402.03216`), multilingual-E5 report
(`q3-arxiv-2402.05672`), Qwen3-Embedding paper (`q3-arxiv-2506.05176`), the LoRA
original (`q4-arxiv-2106.09685`), continual-finetuning forgetting
(`q4-arxiv-2308.08747`), ALFA (`q5-arxiv-2502.14860`), and the three later AMIE
papers (`q5-arxiv-2505.04653`, `q5-arxiv-2507.15743`, `q5-arxiv-2603.08448`).
ALFA and the AMIE follow-ups are the most likely to change Q5's conclusions and
are the obvious next reading.
