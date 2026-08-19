# HerHealthGPT — project status

Three things, in order: what the core system looks like (UML), what's built
versus what's next, and where we are in the overall build sequence.

Counts below are as of **2026-08-19** — the same date as `CLAUDE.md`. If you
change the knowledge base, update both files in the same commit.

---

## 1. UML — the triage core

This is the part of the system that actually runs today: load the knowledge
base, walk a consultation turn by turn, decide when to stop. Frontend, model
serving, and the eval harness's benchmark data are not shown — they either
don't exist yet or aren't what this document is about (see §2).

### Class diagram

```mermaid
classDiagram
    class KnowledgeBase {
        +tuple~Feature~ features
        +tuple~Condition~ conditions
        +tuple~EvidenceRow~ evidence
        +tuple~RedFlagRule~ red_flags
        +tuple~Source~ sources
        +Weights weights
    }

    class Feature {
        +Identifier id
        +FeatureKind kind
        +tuple allowed_values
        +int burden
        +map probe
    }

    class Condition {
        +Identifier id
        +str icd11
        +ActionCode baseline_action
        +tuple source_ids
        +str single_source_reason
    }

    class EvidenceRow {
        +Identifier condition_id
        +Identifier feature_id
        +str value
        +EvidenceStrength strength
        +Identifier source_id
        +str source_quote
    }

    class RedFlagRule {
        +Identifier id
        +tuple~Clause~ all_of
        +ActionCode action
        +Identifier source_id
        +str source_quote
    }

    class Clause {
        +Identifier feature_id
        +ComparisonOp op
        +union value
    }

    class Weights {
        +map log_odds
        +float plausibility_floor
        +float stop_confidence
        +float self_care_stop_confidence
        +float stop_margin
        +int max_questions
    }

    class TriageEngine {
        -KnowledgeBase base
        -Weights weights
        +initial_state() TriageState
        +update(state, feature_id, value) TriageState
        +should_stop(state) Decision
        +next_question(state) Identifier
        +escalation_probe(state, fired) Identifier
        -_first_matching_red_flag(answers) Identifier
        -_could_change_action(state, feature_id) bool
        -_separation(state, feature_id) float
    }

    class TriageState {
        +Mapping~str,float~ scores
        +tuple~Answer~ answers
        +str fired_red_flag_id
        +questions_asked() int
        +asked_feature_ids() frozenset
        +plausibilities() dict
        +live(floor) dict
        +ranked() list
    }

    class Answer {
        +str feature_id
        +str value
        +is_known() bool
    }

    class Decision {
        +StopReason reason
        +ActionCode action
        +str next_feature_id
        +tuple differential
        +str red_flag_id
    }

    class StopReason {
        <<enumeration>>
        RED_FLAG
        SHARED_ACTION
        NO_INFORMATIVE_QUESTION
        CONFIDENT
        MAX_QUESTIONS
        ASK
    }

    class ActionCode {
        <<enumeration>>
        SELF_CARE
        ROUTINE_APPOINTMENT
        URGENT_SAME_DAY
        EMERGENCY
    }

    class EvidenceStrength {
        <<enumeration>>
        strong_support
        weak_support
        neutral
        argues_against
        rules_out
    }

    KnowledgeBase "1" *-- "37" Feature
    KnowledgeBase "1" *-- "19" Condition
    KnowledgeBase "1" *-- "135" EvidenceRow
    KnowledgeBase "1" *-- "16" RedFlagRule
    KnowledgeBase "1" *-- "1" Weights
    RedFlagRule "1" *-- "1..*" Clause
    EvidenceRow --> EvidenceStrength : strength
    EvidenceRow --> Condition : condition_id
    EvidenceRow --> Feature : feature_id
    Condition --> ActionCode : baseline_action
    RedFlagRule --> ActionCode : action
    TriageEngine "1" o-- "1" KnowledgeBase : reads
    TriageEngine ..> TriageState : produces
    TriageEngine ..> Decision : produces
    TriageState "1" *-- "0..*" Answer
    Decision --> StopReason : reason
    Decision --> ActionCode : action
```

**Reading it:** `KnowledgeBase` is loaded once, validated, and handed to
`TriageEngine`, which is stateless — every method takes a `TriageState` and
returns a new one or a `Decision`. Nothing mutates. `EvidenceRow` is the only
class with no surrogate key: its identity is the triple
`(condition_id, feature_id, value)`, enforced at load so the same cell can't
be asserted twice with different strengths.

### Sequence — one consultation turn

```mermaid
sequenceDiagram
    participant U as User
    participant M as Model (phrasing only)
    participant E as TriageEngine
    participant S as TriageState

    U->>M: free-text answer
    M->>E: update(state, feature_id, value)
    E->>S: add matching evidence weights
    E->>E: _first_matching_red_flag(answers)
    E-->>S: new TriageState
    E->>E: should_stop(state)
    alt red flag fired, more severe rule 1 answer away
        E->>E: escalation_probe(state, fired)
        E-->>M: ask that feature next
    else red flag fired, nothing more severe pending
        E-->>M: STOP — escalate, no model reasoning
    else all live conditions share one action
        E-->>M: STOP — conclude
    else no unasked feature could change the action
        E-->>M: STOP — conclude
    else one condition confidently ahead
        E-->>M: STOP — conclude
    else max_questions reached
        E-->>M: STOP — conclude with differential
    else otherwise
        E->>E: next_question(state)
        E-->>M: ask that feature
    end
    M->>U: phrased question or final answer
```

The model never appears left of `TriageEngine` in this diagram — it converts
prose to a `(feature_id, value)` pair on the way in, and a `Decision` to prose
on the way out. Every branch inside `should_stop` is plain Python.

---

## 2. What's implemented, and what's next

### Done

| Area | State |
|---|---|
| **Knowledge base** | 37 features · 19 conditions · 135 evidence rows · 16 red flags · 5 sources. `make validate` — 0 warnings. `make verify-quotes` — 151/151 verbatim. |
| **Triage controller** | `TriageEngine` — six-branch `should_stop`, escalation screen (ADR 0007), deterministic question ranking. No LLM in the decision path. |
| **Contracts schema** | `packages/contracts` — Pydantic models for all seven knowledge files, cross-file validation, the log-odds ↔ plausibility conversion (ADR 0005). |
| **Ingestion pipeline** | `services/data` — fetch (robots-checked) → clean → evidence-batch authoring → generate `evidence.csv`. 67 documents fetched and cleaned across 5 sources. |
| **Provenance protocol** | Every evidence row and red flag carries a verbatim `source_quote`, checked by `make verify-quotes`. Second-reviewer approval gate on every batch (ADR 0003). |
| **Tests** | 399 passing, 1 pinned xfail (a known, documented under-triage risk — see ADR 0007 problem 4). |
| **Backend service skeleton** | FastAPI app (`services/backend/app/`), Postgres integration, health check. Triage and evaluation CLIs run standalone. |

### Not started

| Area | State |
|---|---|
| **Frontend** | `services/frontend/` does not exist on disk. No UI. |
| **Model serving** | `services/model/` does not exist on disk. No embeddings, no reranker, no generation endpoint. |
| **Retrieval corpus** | `passages.parquet` is not built. Chunking `build/clean/` into embeddable passages (NHS excluded — `citable_only`) hasn't started. |
| **Benchmark cases** | The 540-case-per-language evaluation set referenced throughout `CLAUDE.md` and the ADRs is not present in this checkout. Every gated eval metric is blocked on it. |
| **TypeScript contracts** | `packages/types-ts/` does not exist. Nothing generates it from the OpenAPI spec because there's no OpenAPI spec yet — no HTTP triage endpoint. |
| **`passages.parquet` → retrieval index** | No embeddings, no FAISS/vector index, no `make index` output on disk. |

### Immediate next step

**Backfill the remaining thin conditions and eliminating rows, then build the
retrieval corpus.** In order:

1. `bacterial_vaginosis` (1 row) and `thrush` (3 rows) are genuinely
   source-exhausted at their current sources — either accept the limitation
   in the eval writeup, or find a source not yet tried.
2. 14 of 19 conditions still have no eliminating row (`argues_against`) —
   each now carries a documented reason why, but only one condition
   (`ovarian_cyst`) has actually been fixed so far. This is what keeps
   nothing leaving the differential (ADR 0007, finding 1).
3. Chunk `build/clean/` → `passages.parquet`, excluding NHS by validator
   rule, and build the embedding index. This is the one piece of Track 2
   (Retrieval & Model, see `docs/ROADMAP.md`) that can start today against
   the existing 19-condition knowledge base — it does not need to wait for
   more rows.
4. Everything else — frontend, model serving, the benchmark set — is a
   separate, larger track each, not a next step from here.

---

## 3. Progress flow — where we are right now

```mermaid
flowchart TD
    A["Benchmark evaluated:<br/>general LLM under-triages 71.8%"] --> B["Architecture decision:<br/>deterministic controller,<br/>not fine-tuned urgency"]
    B --> C["Contracts schema written<br/>(packages/contracts)"]
    C --> D["Sources vetted, licensed,<br/>ingestion pipeline built"]
    D --> E["Phase 1: 3 conditions,<br/>14 red flags authored"]
    E --> F["Phase 1.5: benign/infective<br/>alternatives added<br/>(7 more conditions)"]
    F --> G["TriageEngine built:<br/>should_stop, escalation screen"]
    G --> H["2026-08-17: dataset generation<br/>paused for controller testing"]
    H --> I["2026-08-19: resumed —<br/>+1 red flag, +7 conditions,<br/>+46 evidence rows"]
    I -.-> J["HERE:<br/>135 rows, 19 conditions,<br/>0 validate warnings,<br/>399 tests passing"]

    J --> K["NEXT: eliminating rows<br/>for 14 conditions"]
    J --> L["NEXT: build passages.parquet<br/>+ embedding index"]
    K -.not started.-> M["Retrieval evaluation<br/>(grounding, recall@k)"]
    L -.not started.-> M
    M -.blocked on benchmark.-> N["540-case eval:<br/>under-triage, clarification,<br/>cross-language agreement"]
    N -.not started.-> O["Model serving<br/>(services/model)"]
    O -.not started.-> P["Frontend<br/>(services/frontend)"]
    P -.not started.-> Q["First real consultation<br/>end to end"]

    style J fill:#2d5a4a,color:#fff,stroke:#1a3d31,stroke-width:3px
    style A fill:#e8e8e8,color:#333
    style B fill:#e8e8e8,color:#333
    style C fill:#e8e8e8,color:#333
    style D fill:#e8e8e8,color:#333
    style E fill:#e8e8e8,color:#333
    style F fill:#e8e8e8,color:#333
    style G fill:#e8e8e8,color:#333
    style H fill:#e8e8e8,color:#333
    style I fill:#e8e8e8,color:#333
    style K fill:#fff3cd,color:#333
    style L fill:#fff3cd,color:#333
    style M fill:#f8d7da,color:#333
    style N fill:#f8d7da,color:#333
    style O fill:#f8d7da,color:#333
    style P fill:#f8d7da,color:#333
    style Q fill:#f8d7da,color:#333
```

**Legend:** solid arrows are completed steps in sequence. Dashed arrows are
steps not yet started, several of which can run in parallel once their
dependency clears (retrieval and the benchmark-case work do not block each
other, for instance). Green is "we are here."

**In one sentence:** the knowledge base and the deterministic controller that
reads it are built, tested, and growing; retrieval, model serving, the
frontend, and the evaluation benchmark are all still ahead, and none of them
have code on disk yet.

---

## Where to look next

| Question | File |
|---|---|
| Why the architecture is deterministic, not a fine-tuned model | `CLAUDE.md` §"Why it is built this way" |
| Full explanation of every knowledge file, with worked examples | `docs/KNOWLEDGE_BASE.md` |
| Every architectural decision and why | `docs/adr/` (10 records) |
| Repo layout, one line per file | `docs/REPO_MAP.md` |
| Track-by-track plan for what's not started | `docs/ROADMAP.md` |
| Vocabulary — what "condition", "evidence row", "plausibility" mean here | `CONTEXT.md` |
