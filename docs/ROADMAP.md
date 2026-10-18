# What we are doing, what is next, and how

**Audience:** the team, the supervisor, and the Deloitte mentors.
**Updated:** 2026-08-04. Update the status table whenever something ships.

---

## The deadline that governs everything

```mermaid
gantt
    title Milestones — Group 1-RF
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Done
    Knowledge base            :done, kb, 2026-07-29, 2026-08-04
    Triage controller         :done, tc, 2026-08-03, 2026-08-04
    Evaluation harness        :done, eh, 2026-08-04, 1d

    section Critical path
    Annotate + translate cases :active, an, 2026-08-05, 10d
    Retrieval + passages       :crit, rt, 2026-08-05, 12d
    Model service (Qwen)       :crit, ms, 2026-08-12, 12d
    Backend API                :crit, api, 2026-08-19, 10d
    Frontend web app           :crit, fe, 2026-08-26, 12d
    End-to-end integration     :crit, e2e, 2026-09-05, 7d

    section Milestones
    MVP due                   :milestone, m1, 2026-09-12, 0d
    Phase 2 due               :milestone, m2, 2026-10-17, 0d
    Code due                  :milestone, m3, 2026-10-31, 0d
    Final presentation        :milestone, m4, 2026-11-01, 0d
```

**MVP is due 12 September — five weeks and four days from today.** The MVP *is*
the chatbot. Everything on the critical path above is currently unbuilt.

---

## Where we actually are

```mermaid
pie showData
    title Lines of the system that exist
    "Knowledge + data tooling" : 24
    "Triage + evaluation" : 17
    "Shared contracts" : 7
    "Model service (0)" : 0
    "Frontend (0)" : 0
```

| Component | Status | Notes |
|---|---|---|
| Knowledge base | ✅ **done** | 37 features, 19 conditions, 135 rows, 16 red flags (2026-08-19) |
| Provenance checking | ✅ **done** | 151/151 quotes verbatim in source |
| Ingestion pipeline | ✅ **done** | 67 documents fetched and cleaned, robots-checked |
| Triage controller | ✅ **done** | Six stopping rules, 399 tests passing |
| Evaluation harness | ✅ **done** | Metrics + gates written; **no cases to run** |
| Benchmark cases | 🔴 **empty** | The bottleneck — blocks every gated metric |
| Retrieval / RAG | 🔴 **not started** | Cleaned text exists; nothing chunked or embedded |
| Model service | 🔴 **not started** | Qwen3.5-9B not deployed |
| Backend API | 🔴 **not started** | Controller runs from CLI only |
| Frontend | 🔴 **not started** | Nothing exists |

**The honest summary:** the hard, defensible, research-grade part is finished to
a high standard. The visible deliverable does not exist yet. A marker on
1 November needs to *see a working chatbot*, and right now the most impressive
part of this project is invisible without one.

---

## The plan: three tracks, in parallel

Four people, one track each, one shared. Sequential work will not fit.

```mermaid
flowchart LR
    subgraph T1["Track 1 — Knowledge & Evaluation"]
        A1["annotate 30 cases"] --> A2["translate to fr/ar"]
        A2 --> A3["native-speaker check"] --> A4["make eval passes gates"]
        A4 --> A5["tune thresholds<br/>against real numbers"]
    end
    subgraph T2["Track 2 — Retrieval & Model"]
        B1["chunk build/clean/<br/>→ passages.parquet"] --> B2["embed + FAISS index"]
        B2 --> B3["serve Qwen3.5-9B"] --> B4["extract features from prose"]
        B4 --> B5["phrase the answer"]
    end
    subgraph T3["Track 3 — API & Frontend"]
        C1["FastAPI over the controller"] --> C2["session state per user"]
        C2 --> C3["Next.js chat UI"] --> C4["RTL for Arabic"]
        C4 --> C5["citations + links"]
    end
    T1 -.->|"gates the claims"| DONE(["MVP<br/>12 Sep"])
    T2 --> DONE
    T3 --> DONE
```

### Track 1 — Knowledge & Evaluation *(1 person)*

The knowledge base is **frozen for the MVP**. It is already past the quality the
MVP needs and it is not the bottleneck. Remaining work is evaluation only:

1. **Annotate ~30 canonical cases** from `gold_seeds_styled.csv`, in batches of
   10 for review. Each gets feature values, an expected action, a clarification
   flag, and the sentence the label was read from.
2. **Translate those 30 to French and Arabic.** Not the knowledge base — only the
   test questions. See the box below.
3. **Author red-flag cases separately**, from escalation sentences in the fetched
   corpus. The benchmark has almost none (~2 of 90), and red-flag recall is the
   metric that gates merges.
4. **Run `make eval`, then tune.** Findings 1–4 in ADR 0007 all wait on this.

> ### Why the test cases must be translated even though the model is multilingual
>
> Dropping translation from the **knowledge base** is correct — Qwen renders
> probes at response time, and maintaining three copies of 37 probes buys
> nothing.
>
> Dropping it from the **evaluation set** breaks the thesis. The whole problem
> statement is that models degrade in Arabic and French. An English-only test
> set cannot measure per-language under-triage or cross-language action
> agreement — so the central claim goes untested and the baseline comparison
> exists in English only.
>
> This is small: ~30 questions, not 135 evidence rows. NLLB-200 plus a
> native-speaker pass, exactly as the proposal budgeted. The schema already
> carries `Language` on variants and propagates labels from English by
> `canonical_case_id`, so the asymmetry bug cannot recur.

### Track 2 — Retrieval & Model *(1–2 people)*

Start **now**, against the 19 conditions that already exist. Do not wait for the
knowledge base to be perfect — it already is, for this purpose.

1. Chunk `build/clean/` into `build/passages.parquet`. **NHS text must be
   excluded** — it is `citable_only` and may be quoted but never redistributed.
   The validator enforces this; do not work around it.
2. Sentence-BERT embeddings, FAISS index.
3. Serve Qwen3.5-9B behind HTTP. **No model weights load inside the backend
   process** — embeddings and reranking are HTTP calls.
4. Two prompts, and only two: **prose → feature values** on the way in, and
   **decision → sentence** on the way out. The model must never decide urgency.

### Track 3 — API & Frontend *(1–2 people)*

1. FastAPI wrapping `TriageEngine`, one turn per request, session state held
   server-side.
2. Next.js responsive web app. **Not a PWA** — no service worker, no manifest, no
   install prompt.
3. RTL layout for Arabic.
4. Render the answer as: **action → what it aligns with → citations with links**,
   per [ADR 0008](adr/0008-showing-what-symptoms-align-with.md).

---

## What the user will see

Agreed with mentors, specified in [ADR 0008](adr/0008-showing-what-symptoms-align-with.md).

```mermaid
flowchart TB
    D["Controller decision"] --> RF{"red flag<br/>fired?"}
    RF -->|yes| ONLY["Show the action ALONE.<br/>No alignment list —<br/>escalation must not be diluted."]
    RF -->|no| FILTER["Keep conditions that<br/>ACTUALLY MOVED<br/>(≥1 supporting row)"]
    FILTER --> TOP["Top 3, no numbers,<br/>never fewer than 2 or show none"]
    TOP --> OUT["1. What to do<br/>2. What it aligns with<br/>3. Source + link<br/>4. 'Not a diagnosis'"]
    style ONLY fill:#7f1d1d,color:#fff
```

**The line we hold:** diagnosing tells a person what they *have*. This tells a
person what a named source *associates with what they described*. The
grammatical subject is always the source and the symptom, never the user and a
condition.

> **What to do: see a GP within the next few weeks.**
>
> What you described overlaps with what these sources write about:
> - **Uterine fibroids** — NHS lists heavy periods and pelvic pressure among its symptoms. [nhs.uk]
> - **Adenomyosis** — NHS describes heavy, painful periods and fullness in the tummy. [nhs.uk]
>
> This is not a diagnosis, and this list is not complete. Only a clinician can
> tell you which, if any, applies to you.

---

## Deliberately after the MVP

Do not start these before 12 September:

- Suggested articles on women's health
- ~~Cycle-data export/import for context~~ — built 2026-10-18 on
  `feat/cycle-data-import`, [ADR 0019](adr/0019-cycle-data-is-imported-from-any-tracker-and-may-pre-fill-answers.md)
  (proposed). Apple Health and CSV-template converters are not yet checked
  against a real export.
- Fine-tuning (a documented contingency, **not** a deliverable)
- The remaining blocked conditions
- ICD-11 codes beyond what the WHO API already resolved

---

## Known problems we are carrying

All measured, none hidden. Full detail in
[ADR 0007](adr/0007-what-the-first-real-consultations-showed.md).

| # | Problem | Effect | Fix waits on |
|---|---|---|---|
| 1 | Nothing leaves the differential | Was true of all 12 conditions as of the last measured run; **not re-measured** since the 2026-08-19 knowledge base growth to 19 conditions and several new `argues_against` rows (`ovarian_cyst` gained its first). Re-run before citing this row. | More eliminating rows, or a higher floor |
| 2 | Question selection is nearly fixed | Same 6 questions regardless of answers | Making separation depend on current scores |
| 3 | **Every case returns `URGENT_SAME_DAY`** | Safe but uninformative | 1 and 2 above |
| 4 | Stopping rule 4 can under-triage | Latent; pinned by a strict xfail test | A policy decision on over-triage |
| 5 | Two conditions barely modelled | `bacterial_vaginosis` still has 1 row (confirmed 2026-08-19 — genuinely exhausted, not yet backfilled; see `CLAUDE.md`). `thrush` grew from its original count and is no longer the thinnest. | More rows, or drop them |
| 6 | Mid-range answers move nothing | "moderate" is invisible to the controller | ~8 more rows from existing sources |

Problem 3 is the one to explain to mentors: **the system currently tells
everyone to be seen today.** That is the conservative failure, chosen
deliberately — but making it informative without making it unsafe is the real
remaining research problem, and it needs the evaluation set to settle.

---

## What to show at the next mentor check-in

1. **The graph** — [`KNOWLEDGE_BASE.md` §4](KNOWLEDGE_BASE.md#4-the-graph--this-is-the-reason-like-a-doctor-part).
   Questions and conditions as nodes, evidence as typed edges. This is the
   "reason like a doctor" ask, delivered.
2. **A live consultation** — `make triage CASE=services/backend/cases/sudden_severe_pain.yaml`
   prints every question, why it was chosen, what each answer was worth, and
   which rule ended it, citing the NHS sentence.
3. **The provenance guarantee** — `make verify-quotes`, 151/151.
4. **The honest limitations** — the table above. Naming them is the strongest
   thing in the project.
