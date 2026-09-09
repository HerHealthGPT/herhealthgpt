# HerHealthGPT

Multilingual reproductive-health triage companion. English, French, Arabic.
Master's capstone, School of Computing, Queen's University. Group 1-RF, Team 4.
Supervisor: Dr. Rahatara Ferdousi. Mentors: Deloitte Innovation Hub, Egypt.

---

## What this system does

Urgency triage and informational guidance. **It never diagnoses.**

A user describes a symptom in her own words. The system asks a small number of
clarifying questions, then tells her how urgently to seek care and why, with
citations. If her answers match a red-flag rule at any point, it escalates
immediately without asking anything further.

No file, comment, docstring, string literal, commit message or UI copy may
describe this system as diagnosing.

## Why it is built this way

We evaluated a general-purpose multilingual model on a 540-case-per-language
benchmark of women's-health concerns. Findings that drive the architecture:

- **Under-triage 0.718** in English. Of cases whose correct answer was
  "see a doctor", 72% were routed to "routine".
- Aggregate risk accuracy 0.667 against a majority-class baseline of 0.644.
  The accuracy number hid the safety failure.
- Fine-tuning collapsed clarification-seeking from **0.856 to 0.000** and pushed
  French and Arabic under-triage to **0.994** — the model predicted "routine"
  for 538 of 540 French cases.
- Cross-language consistency *improved* during that collapse, because the model
  had collapsed onto one answer. Consistency alone is not a safety metric.

Consequences, all binding:

1. **The reasoning model decides ask-vs-conclude and the action code directly
   — the deterministic controller is retired.** This reverses what stood here
   before, accepted via
   [ADR 0011](docs/adr/0011-controller-free-triage.md) on **2026-08-31**,
   against the recommendation of
   [`docs/research/0001`](docs/research/0001-llm-triage-architecture.md) —
   that note's findings still stand and are not retracted by this line; the
   ADR's own risk register restates them unsoftened. The decision is grounded,
   never free judgement: every turn injects the full text of `red_flags.yaml`
   plus retrieved evidence-statement and source passages, and the model's only
   output channel is `TriageDecision`
   (`packages/contracts/src/herhealth_contracts/decision.py`), a
   schema-constrained structure enforced by vLLM guided decoding — the one
   hard rule left, in place of a log-odds score. **The current QLoRA adapter
   (trained on `gold_seeds_styled.csv`) may not be handed this decision as
   it stands** — it was shown no example where the correct move is a
   clarifying question, which is the documented cause of clarification
   collapsing to 0.000 in the original evaluation. It must be retrained on
   multi-turn conversational data before it decides anything; until that
   retrain ships and is reviewed, it stays phrasing-only.
2. **`TriageDecision`'s schema is the deterministic safety net that remains.**
   `ask` requires a `next_feature_id` from `features.yaml`'s closed
   vocabulary; `conclude` requires an `action_code` from `actions.yaml` and,
   unless the decision is red-flag-driven, up to five `matching_conditions`
   from `conditions.yaml`'s roster — nothing outside those vocabularies is
   representable. Which question, or which action, the model picks *within*
   that vocabulary is no longer checked by code. That gap is named, not
   hidden — see [ADR 0011's risk register](docs/adr/0011-controller-free-triage.md#risk-register).
3. **Under-triage is the dominant failure mode.** Whenever a design choice trades
   false alarms against missed escalations, choose false alarms.

   The FDA's Clinical Decision Support Software guidance (29 Jan 2026) describes
   this failure independently, as a human-factors risk: automation bias causes
   *"errors of … omission (failing to act because of not being prompted to do
   so)"*, and *"in situations that require urgent action, automation bias
   increases because there is not sufficient time for the user to adequately
   consider other information."* That is under-triage, named by a regulator. Our
   benchmark finding and the conservative tie-breaks in `weights.yaml` are not a
   local quirk — cite this when the bias toward false alarms is questioned.
4. Cross-language comparison is on the **action code**, never on text similarity.

---

## Architecture

Monorepo. Four independently deployable services, one contracts package.

```
services/frontend/    Next.js, responsive web app (NOT a PWA — see below)
services/backend/     FastAPI: triage, tracker, directory, visit prep,
                      retrieval, safety rules, orchestration
services/model/       vLLM: Qwen3.5-9B generation; bge-m3 embeddings (ADR 0010)
services/data/        ingestion, evaluation harness, benchmark cases
packages/contracts/   Pydantic schemas, error codes, safety policy
packages/types-ts/    TypeScript generated from the OpenAPI spec
knowledge/            the seven knowledge files (see below)
infra/                compose.yml, envs/*.env, Caddy, Prometheus
.github/workflows/    path-filtered CI
```

**Frontend is a normal responsive web app.** No service worker, no manifest, no
offline shell, no install prompt, no web push. Mobile-first responsive layout,
RTL support for Arabic. Do not add PWA scaffolding, and do not suggest it.

**Import rule:** nothing outside `packages/contracts/` may be imported across
service boundaries. Enforced by import-linter in CI.

**No model weights load inside the backend process.** Embedding is an HTTP call
to `services/model`.

**Retrieval is `BAAI/bge-m3` over sentence-level passages, and there is no
reranker.** Chosen on published Arabic RAG results — multilingual encoders beat
Arabic-specific ones, which is the counterintuitive direction. Sentence-level
chunking is load-bearing for `make verify-quotes`, not a tuning knob. A reranker
is deferred until retrieval evaluation shows the right passage retrieved but
ranked outside top *k*. See [`docs/adr/0010`](docs/adr/0010-multilingual-embeddings-beat-arabic-specific-ones.md).

**Deploy:** merge to main → path-filtered CI builds only what changed → image
tagged with the git SHA → PR bumps that tag in `infra/envs/staging.env` → merge
triggers a self-hosted runner on the GPU server. Rollback is `git revert`.
Nothing is ever edited directly on the server.

---

## The knowledge base

Seven files under `knowledge/`. Five are hand-authored and reviewed, kept as
plain text in git so every change appears as a reviewable diff.

Counts are **as built on 2026-09-02**, read from the files. They are not targets.
If you change a file, change the number here in the same commit.

**Batches 13–24 have landed.** Batches 13–23 (drafted 2026-08-19) completed
review, taking `evidence.csv` 98 → 135 rows and giving the seven conditions
added that day their evidence. Batch 24 followed on 2026-09-02: two new
features and 5 rows, 135 → 140. The numbers below are read from the files and
count every approved batch in `services/data/evidence_batches/` (`batch_04`
through `batch_24`).

| File | Rows | What it is |
|---|---|---|
| `features.yaml` | 39 | Everything the system may ask about |
| `conditions.yaml` | 19 | Everything the system may suspect |
| `evidence.csv` | 140 | The sparse grid connecting them |
| `red_flags.yaml` | 16 | Deterministic escalation rules |
| `sources.yaml` | 5 | Provenance, licence, precedence |
| `weights.yaml` | — | Ordinal-to-log-odds mapping, tunable |
| `actions.yaml` | 4 | Four action codes, resolved per locale |

`evidence.csv` rows by source: womenshealth 57, NHS 47, MedlinePlus 26, NICHD 8,
CDC 2. By strength: `weak_support` 85, `strong_support` 45, `argues_against` 10,
and **no `rules_out` row has ever been authored** — see ADR 0009, which must be
revisited before the first one is.

**Every condition now carries at least one evidence row.** The thinnest are
`bacterial_vaginosis`, `infertility`, `inherited_bleeding_disorder` and
`iron_deficiency_anaemia` (3 each), then `pelvic_organ_prolapse` (4) — these are
where the differential is most likely to be weak, and where the next authoring
pass should go before any new condition is added.

**`make verify-quotes` is the check that makes the protocol real, and it needs a
complete `build/clean`.** It reads the cleaned corpus, which is gitignored and
absent on a fresh clone, so it reports `NOT_FOUND` for any row whose source page
has not been fetched and cleaned locally — indistinguishable at a glance from a
fabricated quote. On 2026-09-02 it failed on 31 quotes for exactly this reason:
`build/clean` held 49 of 67 documents, all 18 missing ones belonging to the
conditions added on 2026-08-19. After re-fetching them, **all 156 quotes verify
verbatim**. Run `make fetch && make clean` before trusting a failure.

**Seven features carry no evidence row, and that is correct.**
`pregnancy_status`, `bleeding_after_menopause`, `feeling_faint`,
`shoulder_tip_pain`, `right_upper_quadrant_pain`, `difficulty_breathing` and
`sudden_confusion` appear only in `red_flags.yaml`. They exist to fire
escalation rules, not to raise a condition in the roster — the same discipline
that keeps cancers out of `conditions.yaml`. Do not "fill them in".

Counting `evidence.csv` with `wc -l` gives the wrong answer. `source_quote` and
`note` contain embedded newlines; parse it as CSV.

Plus `passages.parquet`, generated by ingestion, which is the only artifact
produced at scale.

### The conditions, and where each stands

**Nineteen conditions are authored.** These are the `id` values in
`conditions.yaml`, and nothing outside this list may be suspected.

| # | Condition | Note |
|---|---|---|
| 1 | `pcos` | |
| 2 | `endometriosis` | |
| 3 | `uterine_fibroids` | |
| 4 | `normal_variation` | without it `SELF_CARE` is unreachable |
| 5 | `pelvic_inflammatory_disease` | the only `URGENT_SAME_DAY` baseline |
| 6 | `perimenopause` | stops PCOS being over-suspected over 45 |
| 7 | `ovarian_cyst` | explains `pain_onset: sudden` |
| 8 | `urinary_tract_infection` | stops `urinary_symptoms` pointing at fibroids |
| 9 | `sexually_transmitted_infection` | the infective read on `abnormal_discharge` |
| 10 | `thrush` | the benign read on `abnormal_discharge` |
| 11 | `bacterial_vaginosis` | ditto, and the commonest cause |
| 12 | `adenomyosis` | single-source, admitted under ADR 0006 |
| 13 | `hypothyroidism` | added 2026-08-19; menstrual effects of thyroid disease |
| 14 | `primary_ovarian_insufficiency` | added 2026-08-19; age alone separates it from perimenopause |
| 15 | `inherited_bleeding_disorder` | added 2026-08-19; gives `bleeding_heaviness` a non-gynaecological explanation |
| 16 | `bladder_pain` | added 2026-08-19; the non-infective read on `urinary_symptoms` once UTI is excluded |
| 17 | `pelvic_organ_prolapse` | added 2026-08-19; the non-mass read on `abdominal_swelling_or_pressure` |
| 18 | `iron_deficiency_anaemia` | added 2026-08-19; gives `anaemia_symptoms` a condition of its own |
| 19 | `infertility` | added 2026-08-19; the general umbrella `difficulty_conceiving` needed |

**Conditions 13–19 have evidence drafted but not yet approved** — see the
pending-batches note above. `make validate` correctly warns on all seven until
that review lands; this is expected, not a defect.

**`adenomyosis` is authored on NHS alone.** It was blocked under the two-source
rule; ADR 0006 admits a single-source condition *when the row says why*, and NHS
names adenomyosis repeatedly alongside endometriosis as a cause of heavy and
painful periods. Its rows are the ones to read first when auditing provenance.
**Re-probed 2026-08-19** for a second source (MedlinePlus, NICHD) — both still
404. The exception stands, now checked as of this date rather than inherited
from 2026-08-04.

**`primary_ovarian_insufficiency` carries a documented source conflict.**
womenshealth treats "premature menopause" and "POI" as the same thing;
MedlinePlus explicitly says they differ (POI can still permit occasional
periods and pregnancy; premature menopause cannot). Authored under the task's
named framing regardless, because both sources agree closely on the *symptom*
picture this condition's evidence draws on — see the full note in
`conditions.yaml`. Read it before extending this condition.

**Confirmed still blocked, re-checked 2026-08-19 against all five sources**
(MedlinePlus, NICHD, womenshealth, CDC, NHS): hyperprolactinaemia, endometrial
polyp, functional hypothalamic amenorrhoea. All three were re-probed this
session — hyperprolactinaemia and endometrial polyp have zero usable content on
any source; functional hypothalamic amenorrhoea has one real but too-general
source (NICHD's amenorrhea page, which never names the hypothalamic mechanism
specifically). Also confirmed still blocked: **pregnancy-related bleeding** —
womenshealth has substantial content (already used for the `bleeding_in_pregnancy`
red flag) but no second source resolved after four URL attempts across
MedlinePlus and NICHD, and the single-source exception was considered and
declined for this condition specifically. **Coverage gaps are a stated
limitation, not an oversight — report them wherever coverage is reported.**

**Conditions 7–11 and 16–19 exist because of what the differential needs, not
because they are interesting.** 7–11 are the *benign or infective* alternatives
to the original phase-1 three; 16–19 are the differentials added 2026-08-19 to
close specific named holes. Without them the grid pulls every presentation
toward a chronic gynaecological condition: `urinary_symptoms` pointed at
fibroids when the answer is usually a UTI or bladder pain syndrome,
`abnormal_discharge` had nothing infective or benign to point at,
`pain_onset: sudden` had no torsion or rupture to explain it,
`abdominal_swelling_or_pressure` had no non-mass explanation, and
`anaemia_symptoms` and `difficulty_conceiving` had no condition of their own. A
differential made only of chronic conditions over-triages by construction.

**Cancers are deliberately absent.** NHS names womb and ovarian cancer as causes
of these presentations, but modelling them invites the system to suggest cancer
to a worried user, which is not what it is for. They are served by red flags
instead — postmenopausal bleeding routes to a GP without ever naming why, via
the `bleeding_after_menopause` red flag in `red_flags.yaml` (`URGENT_SAME_DAY`,
added 2026-08-19). **This mechanism did not actually exist before that date** —
`bleeding_after_menopause` appeared in no red-flag clause, only a single
`weak_support` evidence row pointing at `perimenopause`, so a postmenopausal
woman reporting bleeding was routed toward perimenopause at routine urgency
rather than escalated. That stale row was deleted the same day the red flag was
added; see `services/data/evidence_batches/batch_07_perimenopause_sti.yaml`'s
amended note.

**Red-flag conclusions name no condition — except at `EMERGENCY`.** ADR 0011
generalised the cancer rule above to every red flag: escalate on the symptom
pattern, never assert what it is.
[ADR 0013](docs/adr/0013-emergency-conclusions-may-name-conditions.md)
(**proposed**, 2026-09-02) narrows that to allow `matching_conditions`
alongside `red_flag_id` **only** when the action is `EMERGENCY` — so a woman
being sent to an emergency department is told what patterns the warning sign
relates to. `URGENT_SAME_DAY` red flags (most of `red_flags.yaml`, including
`severe_pelvic_pain`) keep the original restriction unchanged. This is a
product judgement, not a finding that the old rule was wrong, and ADR 0013's
risk register says so plainly. It does not touch "never diagnoses": a named
condition is still *"may match patterns our sources associate with…"*, never
*"you have…"*. Cancer stays unmodelled and therefore unnameable — it is not in
`conditions.yaml`, so the closed vocabulary still cannot produce it.

### The five evidence weights, and nothing else

`strong_support` `weak_support` `neutral` `argues_against` `rules_out`

`neutral` means **omit the row**. The file is sparse, and much sparser than it
looks: 19 conditions × 39 features is 741 possible cells, and 140 carry meaning —
**19% filled**. Seven of those 39 features are red-flag-only and will never carry
an evidence row (see above), so the reachable grid is smaller than 741 and the
real fill is higher than 19%. A missing row is not a gap to be filled in; it is
the correct representation of "this source does not connect these two things".

### The four action codes, and nothing else

`SELF_CARE` `ROUTINE_APPOINTMENT` `URGENT_SAME_DAY` `EMERGENCY`

Never store locale-specific instructions ("call 111", "see your GP") in any
knowledge file or passage. Those are stripped during cleaning and replaced with
action codes, resolved per locale at response time. Source content is UK and US;
users are in Egypt.

### Never invent

- **No probabilities.** No likelihood ratios, prevalence figures or confidence
  scores. Ordinal weights only.
- **No citations.** Every clinical row carries a `source_id` resolving to a real
  fetched document. No source, no row.
- **No ICD-11 codes from memory.** Write `TODO_VERIFY` and let the WHO ICD API
  lookup fill it. Codes recalled from training data are unreliable.

---

## Verification protocol (replaces clinician review)

**We do not have access to a clinician reviewer.** This is a resource constraint,
and it changes what the knowledge base is allowed to contain.

**The rule: every row must be a restatement of something a cited source says.
No row may be an independent clinical judgement by the team or by you.**

This makes verification a reading-comprehension task rather than a medical one,
which we *can* perform. The protocol:

1. Every row in `evidence.csv` and `red_flags.yaml` carries a `source_id` and a
   `source_quote` column holding the sentence or clause it was derived from.
2. A second team member reads the quote and confirms it supports the row as
   written. This checks provenance, not clinical correctness.
3. If a row cannot be traced to a specific sentence, it is deleted, not softened.
4. Anything requiring inference beyond what the source states is out of scope.
   Do not fill gaps with plausible clinical reasoning.

**The `argues_against` case needs care.** Sources list what a condition causes;
they rarely state what argues against it. Only write an `argues_against` row when
a source explicitly frames the feature as distinguishing, excluding, or
characteristic of an alternative. Do not infer it from absence in a symptom list.
If in doubt, omit the row — a missing row is neutral, which is safe.

**Compensating controls**, because unreviewed content means we bias conservative:

- Red-flag rules are derived only from explicit escalation language
  ("seek immediate care", "call 999", "go to the emergency room"). Never inferred.
- Thresholds in `weights.yaml` are set so the bar for concluding `SELF_CARE` is
  strictly higher than for `ROUTINE_APPOINTMENT`.
- Any condition where sources conflict on urgency takes the **higher** urgency,
  and the conflict is recorded — in the relevant row's or condition's own
  `note`, not in `build/conflicts.jsonl`. **That file is referenced throughout
  this document and the codebase as where conflicts are logged, but no pipeline
  stage currently writes to it** — confirmed 2026-08-19 while resolving the
  `primary_ovarian_insufficiency` source conflict; `docs/CODE_GUIDE.md`
  describes it only as a future `make build` artefact. Until that tooling
  exists, the durable, git-tracked record is the batch or condition note
  itself. Fix the sentence or build the tooling — do not keep citing a file
  that does not exist.
- `DATASHEET.md` states plainly that the knowledge base is source-traceable but
  not clinician-adjudicated, and that this is a stated limitation.

State this limitation wherever results are reported. Do not describe the
knowledge base as clinically validated, expert-reviewed, or verified.

---

## Sources

**No source may block the project.** NHS production API access requires NHS
England onboarding with an organisational ODS code. It has been requested via
the supervisor and is treated as a **future improvement**, never a dependency.
NHS public pages may be read and quoted now.

Two independent facts per source, both recorded in `sources.yaml`:
**precedence** decides who wins a disagreement, **status** decides whether the
source is usable at all. A high-precedence source can be unusable — NICE CKS is
exactly that.

Terms were read from the sources' own pages on 2026-08-03. Only usable sources
appear in `sources.yaml`; the rest were **removed** rather than listed, so
nothing unusable can be cited by accident.

**Five sources, and `sources.yaml` is the authority.** The table below must match
it.

| Source | `id` | Prec. | Licence | Status |
|---|---|---|---|---|
| MedlinePlus | `medlineplus` | 3 | Public domain **except** A.D.A.M. encyclopedia | **available** |
| NICHD | `nichd` | 3 | US federal, public domain *(unverified)* | **available** |
| Office on Women's Health | `womenshealth` | 3 | US federal, public domain | **available** |
| CDC | `cdc` | 4 | US federal, public domain *(unverified)* | **available** |
| NHS website | `nhs` | 2 | Crown copyright, no reuse grant | **citable_only** |

**`womenshealth` (womenshealth.gov) carries 57 of the 140 evidence rows and has
overtaken NHS (47) as the largest contributor.** That reversal matters more than
the count: womenshealth is public domain and ingestable, NHS is `citable_only`
and none of its rows may enter `passages.parquet`. So the ingestable corpus is
still smaller than the row count suggests, but the gap is closing from the right
side. MedlinePlus grew 17 → 26 across batches 13–23, CDC 1 → 2. **Prefer
womenshealth and MedlinePlus when a fact is available from more than one source
at equal precedence** — an NHS-only row is citable but unretrievable, so it
strengthens the differential without strengthening RAG.

**MedlinePlus has a split licence and it matters.** Health topic summaries are
public domain. The A.D.A.M. Medical Encyclopedia (`medlineplus.gov/ency/*`) and
drug monographs are not, and their terms state: *"You may not ingest and/or
brand the copyrighted content found on MedlinePlus in an EHR, patient portal, or
other health IT system."* That clause names systems like this one. **The
ingestion client must exclude `/ency/` by path.** Attribution required:
*"Courtesy of MedlinePlus from the National Library of Medicine."*

**NHS is `citable_only`, and that is a licence constraint rather than a fetching
one.** The content policy makes no reuse grant beyond "© Crown copyright" — no
Open Government Licence. So NHS text may be quoted with attribution into
`source_quote`, and must **never** enter `passages.parquet`. The validator
enforces this regardless of how the bytes were obtained.

**Fetching is governed by a robots parser, not by judgement.** `RobotsPolicy`
checks every URL against the origin's live `robots.txt` before any request, and
refuses a disallowed path with the reason recorded on the fetch record.
`nhs.uk/robots.txt` disallows `/Conditions/` with a capital C while the live
URLs are lowercase `/conditions/` and `/symptoms/`; matching is case-sensitive
per RFC 9309, so those are permitted and are fetched. Superseding an earlier
decision that treated the capitalised rule as barring them — that was a guess,
and the parser now decides.

**CDC and NICHD licences are unverified** — cdc.gov returned 403 to automated
requests and the NICHD copyright pages 404'd. Both are near-certainly public
domain as US federal works, but confirm before a large ingestion run rather than
inheriting an assumption.

### Excluded, and why — do not re-investigate

| Source | Reason |
|---|---|
| **NICE CKS** | *"Except for personal use, study or personal research, copyright content owned by NICE may not be used, reproduced, translated, distributed or transmitted in any form... without the prior written agreement of NICE."* The UK Open Content Licence is **UK-only**; CKS is separately third-party content under its own EULA; terms also forbid use "for any commercial gain". Users are in Egypt. Not a barrier to clear — a wall. |
| **RCOG / ACOG** | Copyright, reuse by permission, no open licence. |
| **UMLS** | Requires a UTS account and licence acceptance; not needed for the MVP. |
| **WHO ICD** | Only resolves `TODO_VERIFY` identifiers. Cosmetic; defer. |
| **NCBI E-utilities, openFDA** | Out of MVP scope. |

**Precedence on conflict** (lower wins): NHS 2, then NICHD / MedlinePlus /
womenshealth 3, then CDC 4. Numbering gaps are the removed sources, so the
ordering stays stable if a licence is ever cleared. Three sources share
precedence 3, so a conflict among them is **not resolvable by precedence** and
is recorded in the relevant row's, feature's or condition's own `note` with the
higher urgency taken. Never resolve a conflict silently.

`build/conflicts.jsonl` is **not** that record, and the sentence above is
deliberately not phrased in terms of it. The file does exist and holds real
hand-written entries, but `build/` is gitignored and no pipeline stage writes
it — so its contents reach no reviewer, survive no fresh clone, and appear in
no diff. Recording a conflict only there loses it. Write the note in the
tracked file and treat `conflicts.jsonl` as scratch.

Precedence resolves which source *wins*; it does not license writing the
losing side out. Where two sources contradict each other on whether a symptom
occurs at all — as NHS and womenshealth do on itching in bacterial vaginosis —
the safe move is to write no row in either direction and record why, because a
missing row is neutral. See `discharge_smell`'s note in `features.yaml`.

Raw fetches are immutable: `raw/{source}/{YYYY-MM-DD}/`, never overwritten.
Every record stores `url`, `fetched_at`, `content_hash`, `licence`.
Ask before any network call. Tests never hit the network.

---

## The stopping controller (outgoing)

**Superseded by [ADR 0011](docs/adr/0011-controller-free-triage.md), accepted
2026-08-31.** `engine.py`, `state.py` and the `should_stop`-based path through
`dialogue.py` are not yet deleted — they stay in the tree until the new
`TriageAgent` loop is wired to a real `services/model` and reviewed (ADR 0011's
migration checklist, steps 4–8) — but this section describes the code being
migrated away from, not the accepted architecture. In particular, **the
escalation screen described below is a property of this outgoing code, not a
guarantee the new design currently reproduces**: the replacement injects
`red_flags.yaml` in full every turn, but nothing forces the model to notice
that a more severe rule sits one answer away the way `should_stop` rule 1 did
by code. That gap is open, tracked in ADR 0011's risk register.

Plain Python in `services/backend/app/triage/`. No LLM involvement.

Per turn: the model extracts feature values → code adds the matching weights from
`evidence.csv` to a log-odds score per condition → red-flag rules run → code
decides ask-or-conclude → the model phrases the question or the final answer.

`should_stop` checks in order, first match wins:

1. Red flag fired → escalate, unless the escalation screen has a probe to ask
2. All conditions above `plausibility_floor` share one action → stop
3. No unasked feature could change the action → stop
4. Top plausibility above `stop_confidence` and `stop_margin` clear of second → stop
5. `max_questions` (6) reached → stop with the differential
6. Otherwise → ask one question

One question per turn, always. Stopping at `SELF_CARE` requires a strictly higher
bar than stopping at `ROUTINE_APPOINTMENT`.

**The escalation screen, which qualifies rule 1.** When several rules match the
same answers, the **most severe** one is taken — never the first in file order. A
fired rule then does not conclude while a strictly more severe rule is one answer
away: before returning the escalation, the controller asks about any rule that
has exactly one outstanding clause on a feature not yet put to the user, provided
at least one of its other clauses already matches. Each condition is load-bearing
— together they make the screen terminate, because every probe either fires its
rule or kills it.

Two consequences that look like violations of the rules above, and are not:

- The model *is* called during the screen, to phrase the probe. Rule 1 means no
  model involvement in the escalation **decision**, which remains code-only.
- **The screen has no probe budget and deliberately runs past `max_questions`.**
  That budget is a judgement about patience; emergency screening is not subject
  to it. A budget low enough to protect patience would silently drop the last few
  emergency rules, which is the failure the screen exists to remove.

See [`docs/adr/0007`](docs/adr/0007-what-the-first-real-consultations-showed.md)
for the derivation and the cost — once severe pelvic pain is known, six EMERGENCY
rules sit one answer away, so that case takes ten questions rather than four.

---

## The fine-tuned model from our evaluation paper

The paper's model was trained with **QLoRA** on
`services/data/eval/benchmark/gold_seeds_styled.csv`: 540 rows, 90 distinct
answers × 6 registers (`canonical`, `layperson`, `clinical`, `ambiguous`,
`emotionally_concerned`, `indirect_cultural`).

**No `Answer` in that file contains a question mark.** Not one — while 529 of the
540 `Question` values do. The dataset has an **`ambiguous` register**, and those
rows are paired with a complete answer too. So the model was shown 90 ambiguous
questions and taught, every time, to answer rather than ask.

That is the mechanical explanation for clarification-seeking collapsing to 0.000.
It was not an alignment mystery; it is what the data asked for.

What follows from that, and what does not:

- **It is a genuine asset for phrasing.** Six-register in-domain training is
  exactly what "render this action code as a sentence a worried user can read"
  needs, and it is the one thing the base model has no in-domain signal for.
- **As it stands, it must not choose an action code**, because the data it was
  trained on contains no example of choosing one under uncertainty. Under
  [ADR 0011](docs/adr/0011-controller-free-triage.md) the reasoning model *is*
  now permitted to decide, in general — but only after this adapter is
  retrained on multi-turn conversational data where the correct assistant turn
  is sometimes a clarifying question, which does not exist in
  `gold_seeds_styled.csv` today. Handing the untrained adapter the decision
  would very likely reproduce the 0.994 under-triage collapse this project
  already measured. Bootstrap data for the retrain exists at
  `services/data/eval/benchmark/bootstrap_multi_turn.jsonl`; the retraining run
  itself has not happened.
- **QLoRA quantises the base during *training*; the adapter itself is an ordinary
  LoRA adapter.** vLLM serves adapters with `--enable-lora --lora-modules
  {name}={path}` on any model implementing `SupportsLoRA`, so the paper's model
  and the base can be served from one process. The adapter was fitted against an
  NF4-quantised base, so serving it against an unquantised base is a small
  distribution shift — usually fine, but **measure it, do not assume it**.
- **Rank and target modules, confirmed 2026-08-31 against the real
  `adapter_config.json`** on `herhealthgpt/qwen3.5-9b-herhealth-enfrar-lora-v2`
  (private, not gated): `r=16`, `lora_alpha=16`, standard LoRA (`use_dora` and
  `use_rslora` both false), targeting attention and MLP/feed-forward
  projections (`q/k/v/o_proj`, `gate/up/down_proj`). Base model confirmed as
  `Qwen/Qwen3.5-9B`. Trained via Unsloth, `peft==0.19.1`. `max_lora_rank=16` is
  sufficient for serving.
- **The adapter's weights were verified clean on 2026-09-09**: every tensor
  `float32`, zero NaN, zero Inf, max |weight| ~0.41 (typical 0.03-0.08). When
  a serve produces garbage, the adapter is not the place to look — see the
  serving constraints below.

### The base is a multimodal hybrid, not a text model

Established 2026-09-09 from a live serve, and it corrects what the rest of this
document and `README.md` previously implied. `Qwen/Qwen3.5-9B` loads as
**`Qwen3_5ForConditionalGeneration`**: a vision tower plus a *mixed* attention
stack in which only every fourth layer is full attention and the remainder are
gated linear-attention (Mamba-family) blocks. The adapter's own module list is
independent confirmation — `mlp.{gate,up,down}_proj` on all 32 layers but
`self_attn.{q,k,v,o}_proj` on layers **3, 7, 11, 15, 19, 23, 27, 31** only,
under the key prefix `base_model.model.model.language_model.*`.

Three consequences bind anyone serving this model:

1. **Multimodality must be capped on both axes.** `--limit-mm-per-prompt
   '{"image":0,"video":0}'`. Capping `image` alone still profiles a video item
   and reserves a 12,288-token encoder cache. The log line
   `running in text-only mode` is the check.
2. **On multi-GPU hosts, `--disable-custom-all-reduce` is mandatory where GPU
   peer-to-peer access is unavailable.** vLLM's custom all-reduce silently
   corrupts activations across a broken link until the logits are NaN, at
   which point the sampler emits token 0 — the character `!` in Qwen's
   byte-level BPE vocabulary. The observed symptom is a reply of
   `!!!!!!!!!!!`, and the same broken collective deadlocks engine startup.
   Diagnosed and fixed on the campus VM 2026-09-09;
   [`docs/runbooks/uni-server-vllm.md`](docs/runbooks/uni-server-vllm.md) §0.1
   is the full write-up and the first thing to read when a serve misbehaves.
3. **`max_model_len` must exceed the injected prompt.** A triage turn's system
   prompt is ~3,200-3,600 tokens *before* retrieval — `DEFAULT_SYSTEM_PROMPT`
   plus the feature vocabulary plus all of `red_flags.yaml` rendered verbatim
   plus the JSON shape instruction. 4096 leaves nothing to generate into;
   8192 is the verified working value. `_chat_completions_body` in
   `services/backend/src/herhealth_backend/triage/clients.py` sends no
   `max_tokens`, so vLLM defaults to whatever remains in the window — which
   turns an oversized prompt into a validation failure and a retry loop
   rather than a clean error. That gap is open.

## Language scope

Probe text is authored in **English only** for now. The serving model is
multilingual and renders questions at response time. Do not add `fr`, `ar` or
`ar_eg` probe keys — but design the schema so they can be added without migration.

---

## Evaluation

Reuses an existing 540-case-per-language benchmark with matched register variants
and labels for concern category, risk level, recommended action, and clarification
need. Labels are **silver**, not clinician-adjudicated. Say so wherever reported.

Derive risk labels once from the English source text and propagate to other
languages by `canonical_case_id`. Never run English keyword rules on translated
text — that produced language-asymmetric labels skewed toward routine.

Blocks merge: red-flag recall (must be 100%), per-language under-triage,
clarification recall on ambiguous cases, grounding, cross-language action
agreement. Reported but not gated: over-triage, average questions asked.

**Red-flag recall stops being a provable gate once [ADR 0011](docs/adr/0011-controller-free-triage.md)
ships.** `== 1.0` was checkable because the outgoing controller evaluated every
red-flag clause by code — a proof, not a sample. Once escalation depends on the
reasoning model noticing injected `red_flags.yaml` text, 100% recall becomes a
measured rate like every other metric here. `make eval` needs to change from
asserting equality to reporting the number, and `DATASHEET.md` needs a sentence
saying so — neither has happened yet (ADR 0011 migration checklist, item 9).
Until it does, this line describes the accepted target policy, not what
today's `make eval` enforces.

---

## Working conventions

- Python 3.12, ruff, mypy strict on `packages/contracts/`
- Conventional commits, scoped: `feat(data):`, `fix(knowledge):`
- Short branches, under two days
- CODEOWNERS per folder — check before editing outside your area
- **Stop after each numbered deliverable and wait.**
- **Never generate more than 10 clinical rows without showing them for review.**
- Ask before any network call
- Prefer boring, readable code. This is read by markers, not scaled to millions.

---

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `HerHealthGPT/herhealthgpt`, via the `gh` CLI.
See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, using their default names: `needs-triage`,
`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Only `wontfix`
exists on the repo today. See `docs/agents/triage-labels.md`.

### Domain docs

**Multi-context.** `CONTEXT-MAP.md` at the root names two bounded contexts —
**Triage** (`CONTEXT.md`) and **Accounts** (`services/backend/CONTEXT.md`) — and
records the words that mean different things across the boundary. Read the map
before naming anything. See `docs/agents/domain.md`.
