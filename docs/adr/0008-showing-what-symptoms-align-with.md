---
status: accepted
---

# Showing what symptoms align with, without diagnosing

The system reports urgency. Mentors asked that it also tell a user what her
symptoms most align with, so the guidance feels informative rather than opaque.
That is a reasonable ask — "see someone this week" with no reason attached is
hard to act on and easy to ignore — but it moves the differential from an
internal scoring artefact onto the screen, which needs rules.

## The line

**Diagnosing is telling a person what they have. This tells a person what a
named source associates with what they described.**

| Not this | This |
|---|---|
| "You have uterine fibroids." | "NHS lists heavy periods and pelvic pressure among the symptoms of uterine fibroids." |
| "PCOS: 85% match." | "What you described also overlaps with what NICHD writes about PCOS." |
| "Most likely: endometriosis." | "Two conditions your answers overlap with are…" |

The grammatical subject matters. The sentence is *about the source and the
symptom*, never about the user and a condition. That is not a euphemism — it is
literally all the knowledge base can support. Every row is a restatement of a
sentence saying "condition X causes symptom Y". Reading it backwards to
"symptom Y means you have condition X" is an inference the sources do not make
and the project is not in a position to make.

## Seven rules, all enforced in code rather than in the prompt

1. **Action first.** The action code is the answer. Alignment is context printed
   after it, never instead of it.
2. **Never one item alone.** Show two or three, or none. A single name at the top
   of a screen reads as a verdict however it is worded.
3. **Only conditions that actually moved.** A condition sits at 0.50 before
   anything is asked. Showing one that received no supporting evidence would
   present a default as a finding. Requires at least one supporting row from an
   answer the user actually gave.
4. **No numbers.** No percentages, no scores, no "strong match". The knowledge
   base has ordinal weights chosen by us, and dressing them as confidence would
   imply a calibration that does not exist. This extends the standing ban on
   probabilities to the interface.
5. **Nothing when a red flag fired.** An escalation must not be diluted by a
   paragraph about what it might be. If the answer is "be seen today", that is
   the whole message.
6. **Always cited, always linked.** Each item carries the source name and a link
   to the page. This is also the safest form for NHS content, which is
   `citable_only`: a short quote plus a link needs no reuse grant.
7. **The caveat travels with it**, in the same block, not in a footer.

## Wording

> **What to do: see a GP within the next few weeks.**
>
> What you described overlaps with what these sources write about:
>
> - **Uterine fibroids** — NHS lists heavy periods and pelvic pressure among its
>   symptoms. [nhs.uk](https://www.nhs.uk/)
> - **Adenomyosis** — NHS describes heavy, painful periods and a feeling of
>   fullness in the tummy. [nhs.uk](https://www.nhs.uk/)
>
> This is not a diagnosis, and this list is not complete. Only a clinician can
> tell you which, if any, applies to you.

"This list is not complete" is doing real work. Twelve conditions are modelled;
adenomyosis is authored on one source; cancers are deliberately absent. A user
must not read the absence of something as its exclusion.

## What this is not

Not a probability, not a ranking the user should act on, and not a reason to
skip care. The action code remains the only output the system stands behind.

## Consequences

- `Decision.differential` becomes user-visible, so it needs a presentation
  filter: above the floor, at least one supporting row, top three.
- Rule 3 partly mitigates a known problem — because nothing currently leaves the
  differential, all twelve conditions are technically live at the end of every
  consultation, and printing that list would be absurd. Requiring evidence to
  have *moved* a condition is what makes the list short and true.
- The alignment block is generated from structured data, not written by the
  model. The model translates and phrases; it never picks which conditions
  appear or invents a reason.
- **HIPAA is not the governing concern.** It regulates how covered entities
  handle identifiable health data, does not apply to a student project serving
  users in Egypt, and says nothing about whether software may diagnose. The real
  exposure is medical-device and clinical-decision-support regulation, and the
  protection against it is output design — urgency plus attributed information,
  never a determination about a person. Data handling matters separately and on
  its own terms.
