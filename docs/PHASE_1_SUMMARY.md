# Phase 1 — seed knowledge

What was built, what the numbers are, and what is wrong with it.

Completed 2026-08-04. Everything below is reproducible from `make fetch` onward.

---

## What exists

| | Count | |
|---|---|---|
| Features | 37 | Everything the system may ask about |
| Conditions | 12 | Everything it may consider |
| Evidence rows | 89 | The sparse grid connecting them |
| Red flags | 14 | 7 `EMERGENCY`, 7 `URGENT_SAME_DAY` |
| Sources | 5 | 4 public domain, 1 `citable_only` |
| Documents fetched | 49 | Immutable, hashed, in `raw/2026-08-04/` |
| Tests | 230 | None touch the network |
| Validator warnings | 0 | |
| Quotes verified verbatim | 103 / 103 | |

Grid density is **89 of 444 possible cells (20.0%)**, which is the sparseness the
design intends — `neutral` is expressed by omitting a row.

**Scope grew well beyond the brief**, from three conditions to twelve. Each
addition was individually justified — the differential was missing the benign
and infective alternatives, so several features pointed at the wrong condition —
but the growth happened without the reasoning core ever being run. That is worth
recording as a process observation, not just a count: the phase order exists
precisely to test elimination early, and enrichment is easier to justify one
step at a time than to stop.

## The headline finding: elimination barely works

| Condition | Rows | Eliminating rows |
|---|---|---|
| `normal_variation` | 10 | **6** |
| `endometriosis` | 12 | 1 |
| `pcos` | 11 | 1 |
| `uterine_fibroids` | 10 | 1 |
| `ovarian_cyst` | 11 | **0** |
| `pelvic_inflammatory_disease` | 9 | **0** |
| `perimenopause` | 8 | **0** |
| `urinary_tract_infection` | 6 | **0** |
| `adenomyosis` | 5 | **0** |
| `sexually_transmitted_infection` | 3 | **0** |
| `thrush` | 3 | **0** |
| `bacterial_vaginosis` | 1 | **0** |

**Eight of twelve conditions have no way down**, and the ratio got worse as the
knowledge base grew: 9 eliminating rows out of 89. They can be raised by evidence and
never lowered, so once live they persist until `max_questions` runs out.

This is not an authoring failure. It follows directly from the verification
protocol: an `argues_against` row may only be written where a source explicitly
frames a feature as distinguishing or excluding, and **patient-facing sources
almost never do that**. They list what a condition causes. They rarely say what
argues against it, and several say the opposite outright:

- *"Fibroids do not always cause symptoms"* — NHS
- *"Not everyone with pelvic inflammatory disease (PID) will have symptoms"* — NHS
- *"Many STIs have no symptoms"* — NHS
- *"Most ovarian cysts are small and don't cause symptoms"* — Office on Women's Health
- *"Half of women with bacterial vaginosis do not have any symptoms"* — NHS
- *"Some people with adenomyosis have no symptoms"* — NHS

Where a condition is often silent, absence of a symptom genuinely does not argue
against it, and inventing a row that said otherwise would be the exact failure
the protocol exists to prevent.

**Consequence for Phase 2.** `should_stop` rule 2 — "all conditions above the
floor share one action" — is the workhorse of the controller, and it depends on
conditions dropping below the floor. With eight that cannot, the differential will
stay wide and the controller will lean on `max_questions`. Since PID carries an
`URGENT_SAME_DAY` baseline and cannot be eliminated, it will also hold urgency up.

Whether that is correct caution or systematic over-triage is a question for the
evaluation set. It should be the **first thing measured**, not argued about.

## Design decisions

Recorded as ADRs, because each is hard to reverse and surprising without context.

| ADR | Decision |
|---|---|
| [0001](adr/0001-source-traceability-replaces-clinician-review.md) | Source traceability replaces clinician review |
| [0002](adr/0002-yaml-for-nested-files-csv-for-the-evidence-grid.md) | YAML for nested files, CSV for the evidence grid |
| [0003](adr/0003-evidence-csv-is-generated-from-approved-batches.md) | `evidence.csv` is generated from approved batches |
| [0004](adr/0004-severe-pelvic-pain-is-urgent-not-emergency.md) | Severe pelvic pain is urgent, not emergency |
| [0005](adr/0005-plausibility-is-an-independent-logistic.md) | Plausibility is an independent logistic, not a softmax |
| [0006](adr/0006-a-condition-may-cite-one-source-if-it-says-why.md) | A condition may cite one source, if it says why |

The vocabulary is in [`CONTEXT.md`](../CONTEXT.md); the code in
[`docs/CODE_GUIDE.md`](CODE_GUIDE.md).

## The pipeline

```
make fetch-plan → fetch → clean → evidence → validate → verify-quotes → tables
```

Every stage is a module with tests. Four properties are structural rather than
remembered:

- **Tests never hit the network** — the transport is injected, so no test can
  reach it even by accident.
- **Raw content is immutable** — `RawStore.save` refuses to overwrite; a
  re-fetch on a later date makes a new snapshot.
- **Licence guards run before the request** — `/ency/` on MedlinePlus is barred
  by path because its terms forbid ingestion into a health IT system.
- **robots.txt is parsed, not assumed** — every URL is checked against the live
  file before any request.

Two lockfiles, answering different questions. `ingest.lock.jsonl` records what
bytes arrived. `content.lock.jsonl` records what the words say — added after the
raw-byte hash proved useless for drift detection, changing on 14 of 19 documents
when no clinical content had moved.

## Errors found and corrected

Recorded because a summary that omits them is not a summary.

| Error | How it was caught |
|---|---|
| 5 quotes contained a space before punctuation, inserted by our own extractor — not verbatim | Audit, then a cleaner fix and a regression test |
| 3 quotes had straight punctuation where the source has curly, so were unfindable | `make verify-quotes`, on its first run |
| 3 quotes transcribed from a browser, not the fetched document | `make verify-quotes`, before review |
| A row mapped "upper right abdomen" onto `lower_back_pain` | Human review; deleted, not softened |
| `pain_with_sex` claimed as highly discriminating; it supports 3 of 9 conditions | Found when NHS fibroids listed it |
| `large_clots` had no source tying it to any condition | Validator dead-weight warning; feature deleted |

The first three are the same class: text that reads correctly and cannot be found
in its source. None was catchable by careful reading, which is why the check is
now a pipeline stage.

## Limitations

State these wherever results are reported.

**Not clinician-adjudicated.** Every row is traceable to a cited sentence. No
row has been reviewed by a clinician, and there is deliberately no field
claiming otherwise. Outputs are **silver annotations**.

**Thresholds are untuned.** Every number in `weights.yaml` was chosen by us.
Converting them into log-odds showed the bars are low: one `strong_support` row
reaches 0.818 and clears `stop_confidence` of 0.65 **on its own**, so the
controller could stop after a single answer. Left as authored and pinned by a
test — it should be set by the evaluation set, not by argument.

**One condition rests on a single source.** Adenomyosis is authored under the
documented exception in ADR 0006 — NHS covers it across three documents, but no
second source exists. If NHS is wrong about something in it, nothing catches it.

**Two conditions remain blocked.** Hyperprolactinaemia (MedlinePlus only) and
endometrial polyp (no dedicated page anywhere usable). Five more are sourceable
but unauthored: primary ovarian insufficiency, inherited bleeding disorder,
hypothyroidism, ectopic pregnancy and miscarriage. Authoring stopped
deliberately, to run the controller before enriching further.

**Two conditions cannot be told apart.** Adenomyosis and endometriosis both
present with severe cyclical pain and heavy bleeding, and no feature separates
them. Fibroids claims heavy bleeding too. The differential will routinely carry
all three.

**Discharge separates in one direction only.** `abnormal_discharge` is a boolean,
so it cannot distinguish thrush's "cottage cheese, does not usually smell" from
bacterial vaginosis's "strong fishy smell" — detail a user could easily report.
`vulval_itching` raises thrush but, because two sources contradict each other on
whether bacterial vaginosis itches, its absence lowers nothing.

**Cancers are deliberately unmodelled.** Sources name womb and ovarian cancer as
causes of these presentations. Modelling them would invite the system to suggest
cancer to a worried user. They are served by red flags instead.

**Source coverage is uneven.** 37 rows from NHS, 30 from the Office on Women's
Health, 13 from MedlinePlus, 8 from NICHD, **1 from CDC**. CDC is effectively
unused, and endometriosis rests far more on MedlinePlus than its two-source
citation suggests. NHS being the largest contributor is notable given it is the
only `citable_only` source — its text can be quoted but never enter the corpus.

**Two features strain.** `pain_opening_bowels_or_urinating` covers two questions
in one and has been stretched twice; splitting it would touch four batches.
`extreme_tiredness` overlaps `anaemia_symptoms`, so a user may answer yes to both
and have fatigue counted twice — correlated features are a known weakness of
additive log-odds.

**Probes are English only.** French and Arabic are rendered by the serving model
at response time, so their wording is unreviewed. The benchmark that motivated
this architecture found severe non-English regressions, so a sample should be
read before Phase 2 ships.

## Ready for Phase 2

The reasoning core is unblocked. It needs:

- `plausibility()` — exists, in `packages/contracts`
- `weights.yaml` thresholds in log-odds — exist, as derived properties
- A knowledge base that loads and validates — exists
- Benchmark cases — **do not exist**; `services/data/eval/cases/` is empty

The first Phase 2 task is not the controller. It is deciding how the four action
codes map onto the benchmark's risk labels, which affects every under-triage
number that will ever be reported.
