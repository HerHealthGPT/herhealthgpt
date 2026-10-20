# HerHealthGPT

Urgency triage and informational guidance for reproductive health. The system
asks a short sequence of questions and returns how urgently to seek care, with
citations. It never diagnoses.

## Language

### Asking

**Feature**:
Something the system may ask about. A question, never a claim — listing a
feature asserts nothing about any condition.
_Avoid_: symptom, attribute, field, variable

**Value**:
One of the answers a feature admits. Every feature also implicitly admits
`unknown`, meaning the user did not say, which carries no weight.
_Avoid_: option, response, answer, level

**Probe**:
The wording in which a feature is put to a user, held per language.
_Avoid_: prompt, question text, phrasing

**Burden**:
How intrusive or effortful a feature is to ask, on a 1–5 scale. A judgement
about the person being asked, not about the information.
_Avoid_: cost, weight, priority

**Clarification**:
A turn in which the system asks rather than concludes.
_Avoid_: follow-up, probing question

### Suspecting

**Condition**:
Something the system may consider as an explanation. Considering is not
asserting: a condition being live never becomes a claim that the user has it.
Reserved for clinical explanations only — a red flag's predicate is a *clause*.
_Avoid_: diagnosis, disease, illness, outcome

**Differential**:
The set of conditions still live in a given consultation.
_Avoid_: candidate list, hypotheses, shortlist

**PMOS**:
Polyendocrine metabolic ovarian syndrome, formerly and still widely called
polycystic ovary syndrome. NHS and NICHD use the new name; MedlinePlus and the
Office on Women's Health still use the old one, so both appear in cited quotes.
The condition id remains `pcos` because ids are internal keys and renaming one
would rewrite every evidence row and break the benchmark's labels.
_Avoid_: renaming the id; treating PMOS and PCOS as two conditions

**Evidence Row**:
One cell of the sparse grid, saying that a particular feature value supports or
argues against a particular condition. Carries the sentence it restates.
_Avoid_: mapping, association, rule, link

**Evidence Strength**:
The five-level ordinal scale on which an evidence row is expressed:
`strong_support`, `weak_support`, `neutral`, `argues_against`, `rules_out`.
Deliberately not a probability. `neutral` is expressed by omitting the row.
_Avoid_: weight, score, confidence, likelihood, probability

**Plausibility**:
How strongly the accumulated answers point at a condition, on 0–1. Computed from
that condition's own accumulated evidence alone, so conditions do not compete and
all of them may be implausible at once. Not a probability of the user having
anything.
_Avoid_: probability, confidence, likelihood, certainty

### Deciding

**Action Code**:
One of the four urgency outcomes the system may return: `SELF_CARE`,
`ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`, `EMERGENCY`. Carries no locale — the
instruction a user finally reads is resolved per country at response time.
_Avoid_: recommendation, triage level, disposition, advice

**Red Flag**:
A deterministic escalation rule, evaluated before any model call and never
overridable by one. May only raise urgency, never lower it.
_Avoid_: alert, warning, safety rule, trigger

**Clause**:
One term of a red flag's predicate: a feature, a comparison, and a value. Red
flags are conjunctions only — an "or" is two red flags.
_Avoid_: condition, criterion, test, predicate

**Escalation**:
Returning `URGENT_SAME_DAY` or `EMERGENCY`.
_Avoid_: alerting, flagging, referral

**Under-triage**:
Returning a less urgent action than the case warranted. The dominant failure
mode, and the one every trade-off is resolved against.
_Avoid_: false negative, miss

**Over-triage**:
Returning a more urgent action than the case warranted. Tolerated in preference
to under-triage.
_Avoid_: false positive, false alarm

### Citing

**Source**:
A body of published clinical content that rows may cite.
_Avoid_: reference, citation, document, provider

**Source Precedence**:
Which source wins when two disagree on urgency, lower winning. Independent of
whether that source may be used at all.
_Avoid_: priority, rank, trust level

**Source Status**:
What a source's licence permits: `available` (may be quoted and redistributed),
`citable_only` (may be quoted with attribution but not redistributed), or
`restricted` (neither). Two permissions, because a licence may grant one and not
the other.
_Avoid_: licence, access level, permission

**Source Quote**:
The verbatim sentence a clinical row restates. Required on every evidence row
and red flag. A row that cannot be traced to a specific sentence is deleted, not
softened.
_Avoid_: citation, reference, excerpt, evidence

**Verification Protocol**:
The discipline that stands in for clinical review: every row must restate
something a cited source says, and no row may be an independent clinical
judgement. Turns verification into a reading-comprehension task, which this team
can perform, rather than a medical one, which it cannot.
_Avoid_: review process, QA, validation, sign-off

**Batch**:
A set of evidence rows presented together for review. Contributes nothing until
approved.
_Avoid_: chunk, group, set, import

**Silver Annotation**:
A label derived without clinician adjudication. Everything this system produces
or is evaluated against is silver, and is reported as such.
_Avoid_: ground truth, gold label, validated label

## Resolved

**How the two units relate.** Evidence accumulates as log-odds; thresholds are
authored on 0–1. The conversion is an independent logistic per condition, and it
lives in `packages/contracts/src/herhealth_contracts/scoring.py`. Settled
2026-08-04 — see `docs/adr/0005`.

## Open question

**The thresholds are probably too low** (this concerns the retired rule-based
controller, ADR 0011; the live system does not use these thresholds to stop).
Expressing them in log-odds showed that
one `strong_support` row reaches 0.818 and clears `stop_confidence` of 0.65 on
its own, so the controller could stop after a single answer. The number should
be set by the evaluation set rather than by argument, so it is left as authored
and flagged as the first tuning experiment.
