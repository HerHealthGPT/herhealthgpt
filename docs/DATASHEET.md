# HerHealthGPT datasheet

What the system is built from, what has been measured, and what has not.
Counts are read from the files on 2026-10-19. Figures are quoted with the run
they came from; read the linked records before comparing any two of them.

**This is an urgency-triage and information tool. It does not diagnose.** It
tells a user how soon to seek care and why, with citations, and may say that
her answers "match patterns our sources associate with" a condition. It never
says she has one.

## Stated limitations

These apply to every result below, and to any result reported elsewhere.

- **The knowledge base is source-traceable, not clinician-adjudicated.** No
  clinician has reviewed it. Every clinical row restates a sentence from a
  cited source; a second team member checks that the sentence supports the
  row. That checks provenance, not clinical correctness. Do not describe the
  knowledge base as clinically validated, expert-reviewed or verified.
- **Evaluation labels are silver.** They were derived from the benchmark's
  reference answers, not adjudicated by a clinician.
- **Red-flag recall is a measured rate, not a proof.** Under the retired
  rule-based controller every warning-sign rule was evaluated by code, so
  escalation was guaranteed. Since
  [ADR 0011](adr/0011-controller-free-triage.md) the reasoning model
  decides, and escalation is measured on a sample (see below). A code gate
  now concludes at the rule's urgency when the recorded answers satisfy a rule
  and the model does not escalate, which restores the guarantee for answers
  that are recorded; it cannot catch a warning sign the extract step failed to
  record.
- **Coverage gaps are deliberate and reported.** Cancers are not modelled; they
  are served by warning-sign rules that escalate without naming a cause.
  Hyperprolactinaemia, endometrial polyp, functional hypothalamic amenorrhoea
  and pregnancy-related bleeding are not modelled because no second usable
  source was found. See "Coverage" below.
- **Arabic and French wording has not been reviewed by a native speaker.**

## The knowledge base

Seven files under `knowledge/`, plain text in git, every change a reviewable
diff.

| File | Rows | What it is |
|---|---|---|
| `features.yaml` | 39 | everything the system may ask about |
| `conditions.yaml` | 19 | everything the system may suggest a match with |
| `evidence.csv` | 150 | the sparse grid connecting features to conditions |
| `red_flags.yaml` | 17 | warning-sign rules, derived only from explicit escalation language |
| `sources.yaml` | 5 | provenance, licence, precedence |
| `actions.yaml` | 4 | `SELF_CARE`, `ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`, `EMERGENCY` |
| `weights.yaml` | — | ordinal weights (used by the retired controller) |

`evidence.csv` by source: womenshealth 61, NHS 53, MedlinePlus 26, NICHD 8,
CDC 2. By strength: `weak_support` 94, `strong_support` 46, `argues_against`
10, `rules_out` 0. 150 of 741 possible cells (19 × 39) carry a row; a missing
row means the sources do not connect the two, not a gap to fill. No
probabilities, likelihood ratios or prevalence figures are stored.

## Sources and licences

| Source | Licence | Use |
|---|---|---|
| MedlinePlus | public domain, **except** the A.D.A.M. encyclopedia (`/ency/`), which is excluded by path | quoted and retrieved |
| NICHD | US federal, public domain (unverified) | quoted and retrieved |
| Office on Women's Health | US federal, public domain | quoted and retrieved |
| CDC | US federal, public domain (unverified) | quoted and retrieved |
| NHS website | Crown copyright, no reuse grant | **quoted only**: never in the retrieval index |

NICE CKS, RCOG and ACOG are excluded on their terms. Source content is UK and
US; users are in Egypt, so locale-specific instructions ("call 111") are
stripped and replaced by action codes resolved per locale.

## Coverage

Nineteen conditions are modelled. The thinnest are bacterial vaginosis and
iron-deficiency anaemia (three evidence rows each), then inherited bleeding
disorder and pelvic organ prolapse (four); the differential is likeliest to be
weak there.
Adenomyosis rests on a single source (NHS), admitted under
[ADR 0006](adr/0006-a-condition-may-cite-one-source-if-it-says-why.md). Primary ovarian insufficiency carries a documented
source conflict about its relation to premature menopause.

## Models

| Role | Model | Notes |
|---|---|---|
| Reads her message, decides ask or conclude | `Qwen/Qwen3.5-9B` (base) | output constrained to the `TriageDecision` schema |
| Words informational answers | QLoRA adapter on the same base | **phrasing only**; trained on 2,700 single-turn answers and never shown a clarifying question, so it may not decide anything until retrained on multi-turn data |
| Retrieval | `Qwen/Qwen3-Embedding-4B` over sentence-level passages | the reranker exists and is off: no measured gain |

All three run on the campus GPU server
([ADR 0018](adr/0018-local-models-decide-and-the-adapter-answers.md)).

## Data she gives the system

- **Profile:** date of birth (used as an age band) and an optional health note,
  treated as background, never as a symptom report.
- **Imported cycle data**
  ([ADR 0019](adr/0019-cycle-data-is-imported-from-any-tracker-and-may-pre-fill-answers.md),
  proposed): only dates, flow and a closed list of symptoms, kept after she
  confirms a preview. It may answer a question only when fresh, and a
  warning-sign question only in the alarming direction.
- **Kept files**
  ([ADR 0020](adr/0020-she-may-keep-an-uploaded-file-for-30-days.md),
  proposed): a copy of a tracker export she chooses to keep, deleted
  automatically after 30 days. Nothing reads it.

## What has been measured

All English unless stated; silver labels; one run at temperature 0.

| What | Result | Run |
|---|---|---|
| Red-flag recall of the live pipeline, one case per rule | 17 of 17, both modes (7/7 emergency, 10/10 same day) | 2026-10-19, `make eval-red-flags`, after the red-flag gate; 6 and 8 of 17 before it |
| First turns on the full benchmark (540 questions) | 402 informational answers, 102 questions, 30 declines, 3 conclusions, 3 invalid | 2026-10-13, ADR 0018 |
| Questions labelled see-doctor or urgent given a **lower** level | 0 of 192 | same run |
| Given an answer with **no** level (strict under-triage) | 0.630 (121 of 192) | same run |
| Clarification recall on the 90 vague rewordings | 0.189 | same run; later 18 of the 22 that were declined now get a question or answer (2026-10-19) |
| Scripted multi-turn consultations reaching a conclusion | 10 of 10 | 2026-10-19, after the repeat and invented-name fixes |
| Reply written in the question's language (EN/AR/FR) | 20/20 each | 2026-10-15, 20 items |
| Same urgency across English, Arabic and French, full consultations | 6 of 6 that concluded in all three; 0 lower than English (Arabic concluded 6 of 10) | 2026-10-19, `make eval-languages`; translated scripts unreviewed |

## What has not been measured

- **Cross-language agreement at scale.** It has been measured on ten scripted
  consultations only (above), with translations no native speaker has
  reviewed, and Arabic concluded in only 6 of 10.
- **Whether the urgency advice is right.** "Valid" means a reply passed the
  system's own checks. No measurement here judges the advice clinically.
- **Over-triage** on full consultations, and how many questions a
  consultation takes, at scale.
- **How often pre-filled answers from cycle data are correct.**
- **Model extraction from tracker files** other than the CSV template and
  Apple Health (export and shared PDF), which are read by code.

## The two benchmarks

`gold_seeds_styled` (90 seeds × 6 registers, 540 rows) is what the paper's
results and the figures above are computed on. `benchmark_multilingual_v1` is a
later, separate benchmark whose gold is 100% see-doctor. Figures from the two
are not comparable; quote each with its benchmark.

The paper's under-triage of 0.718 came from a model that had to pick a level
for every question. The 0.630 above is answers given with no level at all,
with none given a lower level. They measure different failures and are not an
improvement of one over the other.
