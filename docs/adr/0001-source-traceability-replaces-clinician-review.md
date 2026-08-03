---
status: accepted
---

# Source traceability replaces clinician review

We have no access to a clinician reviewer, so instead of shipping unreviewed
clinical content we constrained what the knowledge base may contain: every row
must restate something a cited source says, carrying the verbatim sentence it
came from, and no row may be an independent clinical judgement. This converts
verification from a medical task we cannot perform into a reading-comprehension
task we can — a second person reads the quote and confirms it supports the row.

## Considered options

- **Seek a clinician reviewer.** Rejected: not available within the project's
  resources, and a review process that never actually runs is worse than one
  designed around the constraint.
- **Author rows from clinical knowledge and flag them as unreviewed.** Rejected:
  a plausible-sounding row with no source is indistinguishable from a correct
  one, so the flag would carry all the weight and none of the information.

## Consequences

There is deliberately **no `reviewed_by_clinician` field**, nor anything
resembling one — such a field could only ever hold a value we are not in a
position to assert. A test asserts no field matching `clinic|review|approv`
exists on the row models, and `extra="forbid"` prevents one being smuggled in
through the data files.

Rows are limited to what sources state explicitly. This bites hardest on
`argues_against` rows: sources list what a condition causes and rarely state
what argues against it, so most such rows cannot be written at all. Where one
can be, it is because the source frames the feature as distinguishing or
characteristic — never because a symptom was absent from a list.

Everything produced is a **silver annotation** and must be reported as such.
Nothing here may be described as clinically validated, expert-reviewed or
verified.
