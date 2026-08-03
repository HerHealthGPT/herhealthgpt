---
name: clinical-data-authoring
description: >
  Rules for authoring or editing any file under knowledge/ in this repo —
  features.yaml, conditions.yaml, evidence.csv, red_flags.yaml, sources.yaml,
  weights.yaml, actions.yaml. Trigger whenever writing, extending, reviewing or
  validating clinical knowledge rows, evidence weights, red-flag rules, condition
  cards, ICD codes, or action codes. Also trigger when drafting rows from source
  text such as NHS or NICE content.
---

# Clinical data authoring rules

## Absolute constraints

1. This system performs urgency triage and informational guidance. It NEVER
   diagnoses. No file, comment, docstring, string literal or commit message may
   describe it as diagnosing.
2. NEVER invent a probability, likelihood ratio, prevalence figure or confidence
   score. Evidence strength is the five-level ordinal scale only.
3. NEVER invent a citation. Every clinical row carries a source_id resolving to a
   real fetched document. If no source supports a row, omit the row and say so.
4. NEVER write an ICD-11 code from memory. Write `TODO_VERIFY` and let the WHO
   ICD API lookup fill it. Codes recalled from training data are unreliable.
5. When a choice trades false alarms against missed escalations, choose false
   alarms and note the choice in the row's `note` column.

## The five weights, and nothing else

strong_support, weak_support, neutral, argues_against, rules_out

`neutral` means omit the row entirely. evidence.csv is sparse.

## The four action codes, and nothing else

SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, EMERGENCY

Never store locale-specific instructions ("call 111", "see your GP") in any
knowledge file or passage. Those are stripped during cleaning and replaced with
action codes, resolved per locale at response time.

## Authoring an evidence row

For each symptom a source lists under a condition, ask two questions:

1. Is it listed? Yes → at least weak_support. Emphasised or described as a main
   sign → strong_support.
2. Would its ABSENCE make you doubt this condition? If yes, add a second row for
   the opposite value with argues_against.

Question 2 is what makes elimination work and is the one most often forgotten.
Without "regular periods argues_against PCOS", PCOS never drops out.

## Batch limit

Never generate more than 10 clinical rows without stopping for human review.
Present them as a table, wait for approval, then write the file.

## Language scope (current phase)

Probe text is authored in English only. Do not add fr, ar or ar_eg probe keys.
The serving model is multilingual and renders questions at response time. The
authored Egyptian Arabic layer is deferred to a later phase; when it lands it
will be authored by a native speaker, never machine translated.
