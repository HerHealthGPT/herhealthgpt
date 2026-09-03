---
status: proposed
---

# An off-scope message is declined, not triaged

> **Proposed, not accepted.** Taken as an in-session product decision on
> 2026-09-03 in response to a live failure (below), not from supervisor or
> mentor review — the same gate [ADR 0011](0011-controller-free-triage.md),
> [ADR 0012](0012-openrouter-reasoning-and-guarded-web-fallback.md) and
> [ADR 0013](0013-emergency-conclusions-may-name-conditions.md) each named
> for themselves.

## Context

`TriageDecision` had exactly two legal shapes, `ASK` and `CONCLUDE`, and one
grounding rule applying to both: a decision must point at a `citation` or a
`red_flag_id`, because *"a decision citing nothing is not distinguishable
from one the model made up."*

Together those made a refusal **unrepresentable**. There was no value of
`type` meaning "this is not something this system does", and no way to emit
a decision that asserted nothing. The system prompt never mentioned scope
either, so nothing told the model to try.

The consequence, observed live in the running app on 2026-09-03. Asked
**"who won world cup 2026"**, the system returned:

- `type: conclude`, `action_code: SELF_CARE` — *"Self-care should be
  enough… this looks like something you can manage yourself for now"*
- a factual answer to the football question in the `rationale`
- and, as the evidence for it, a genuine Office on Women's Health sentence:
  *"Your doctor will do a complete blood count (CBC)."*
- then, because a `CONCLUDE` closes a consultation, *"This chat is
  complete."*

Nothing malfunctioned. Each of those four is what the schema and prompt
*required* given the model had chosen to answer at all: `ASK` needs a real
`features.yaml` id, which no football question has; that leaves `CONCLUDE`,
which requires one of the four action codes and — per the grounding rule —
at least one citation. Retrieval always returns *something*, because cosine
similarity has no notion of "irrelevant". So the model took the top passage
and attached it.

The third item is the serious one. It is a real quote, correctly attributed,
wired to a question it has nothing to do with. That is indistinguishable at
a glance from the fabricated-citation failure the entire verification
protocol exists to prevent, and it was produced by the safety rule meant to
prevent it.

The same mechanism applies to any health question outside this system's
scope — a men's health concern, a sore throat, an injury — which is a larger
class of input than off-topic trivia and a more likely one in real use.

## Decision

**Add a third decision type, `DECLINE`, and make it the required response to
any message outside scope.**

A `DECLINE` carries **only** its `rationale`, which is the text she reads.
`action_code`, `next_feature_id`, `question_text`, `matching_conditions`,
`red_flag_id` and `citations` are all **forbidden** — not optional. Two
consequences are the point of the change:

- It is **exempt from the grounding rule**, alone among the three types. A
  decision that asserts nothing about her health has nothing for a citation
  to support, and requiring one is exactly what manufactured the CBC quote
  above.
- "Declined *and* assigned an urgency", or "declined *and* cited a source",
  are **unconstructible**. Forbidding rather than merely omitting is what
  makes this a schema guarantee rather than a prompt hope — the same
  reasoning `TriageDecision`'s docstring already gives for being the one
  deterministic safety net left after ADR 0011.

**Scope is defined as what the knowledge base can ground:** the conditions
in `conditions.yaml`, the features in `features.yaml`, the rules in
`red_flags.yaml`. A question those cannot speak to is declined. Defining it
this way rather than as "women's health, broadly" keeps a refusal provable
against the files rather than a matter of taste, and it is the same closed
vocabulary every other part of this design is bounded by.

**A `DECLINE` does not conclude the consultation.** `routes.py` changes
session status on `CONCLUDE` only, so the session stays active and the
composer stays open. An off-scope message costs her nothing and she can ask
something in scope next — as against the observed behaviour, where a
football question ended the consultation.

**What the refusal says**, per the product decision of 2026-09-03: that this
tool covers women's reproductive health only and does not provide diagnoses,
and — when hers was a health question — that a doctor or pharmacist is where
to take it. Where the off-scope message describes something plainly
dangerous, the decline also says to seek urgent medical help now. That
sentence is **not** a triage verdict and carries no action code; it says
this tool is the wrong one, which is the honest thing to say and keeps a
flat refusal from becoming the under-triage `CLAUDE.md` names as the
dominant failure mode.

## What this does not change

- **The grounding rule for `ASK` and `CONCLUDE` is untouched.** Every
  decision that actually assesses something still cites a passage or names
  a red flag.
- **Nothing about the four action codes.** `DECLINE` is not a fifth urgency
  level; it sits beside the urgency question rather than on its scale, and
  no `actions.yaml` entry is added.
- **The closed vocabularies.** A decline names no feature and no condition,
  so it cannot widen what the system may suspect.

## Status

Implemented 2026-09-03:

- `packages/contracts/src/herhealth_contracts/decision.py` —
  `DecisionType.DECLINE`; `_shape_matches_type` validates its shape and
  exempts it from grounding. The `CONCLUDE` branch became explicit
  (`elif ... is CONCLUDE`) rather than `else`, so a future fourth type
  cannot fall through into it — the same class of missing-case bug this ADR
  is about.
- `packages/contracts/tests/test_decision.py` — a decline needs no
  grounding; a decline carrying any of the six forbidden fields is refused
  (parametrised over all six).
- `herhealth_backend.triage.agent.DEFAULT_SYSTEM_PROMPT` — a scope rule,
  placed **first** in the prompt, naming the three shapes of off-scope
  message and forbidding both answering them and citing anything for them.
  Only prose can decide that "who won world cup 2026" is off-scope; the
  schema can only guarantee what a decline may then contain.
- `herhealth_backend.triage.clients._JSON_SHAPE_INSTRUCTION` — the decline
  shape, stated as the explicit opposite of the mandatory-citation rule
  immediately above it, plus the retry feedback for a malformed one.
- `herhealth_backend.triage.demo_clients` — a keyword-matched decline so the
  path is exercisable offline, with `HERHEALTH_TRIAGE_MODE=demo` and no
  OpenRouter key.
- `services/backend/tests/app/test_triage_routes.py` — a declined turn
  returns no action code and no citations, and leaves the session open for
  the next message; the demo path declines too.
- `services/frontend` — `DeclineCard`, deliberately not a `ConclusionCard`
  variant: a conclusion's card is built around an urgency headline, matched
  patterns and cited sources, and reusing it would leave a row of empty
  affordances implying something was assessed. Neutral tone, no urgency
  palette, no "start a new chat" button.

No change was needed in `triage/vocabulary.py`, `triage/provenance.py` or
`routes.py`'s turn loop: each already keys off `DecisionType` and a decline
passes or short-circuits correctly. That is a property of those seams, and
worth noting as evidence they are drawn in the right place.

## Risk register

- **Scope is judged by the model, and nothing checks it.** The schema
  guarantees a decline is empty; it cannot guarantee the model declines
  when it should, or — more worryingly — that it does not decline a real
  reproductive-health concern phrased unusually. That is a **new**
  false-refusal failure mode this design did not previously have, and it
  points the wrong way against `CLAUDE.md`'s rule 3: a woman refused is a
  woman not triaged. It is unmeasured.
- **`make eval` has no case for it.** The 540-case benchmark is entirely
  in-domain, so it cannot detect either over- or under-declining. Adding
  off-scope cases with expected-decline labels is the obvious next step and
  has not been done; until it is, this rests on manual transcript review.
- **The "seek urgent help" sentence in a decline is not source-traceable.**
  Every clinical row in this project restates a cited source; that sentence
  restates none, because the knowledge base has no evidence for conditions
  it does not model. It is admitted deliberately as UI-level safety copy
  rather than a clinical claim, and it carries no action code precisely so
  it cannot be read as a triage outcome. A reviewer who disagrees should
  read it as the one place this ADR trades the verification protocol's
  strictness for not leaving someone in danger with a flat refusal.
- **Prompt-only enforcement of the scope boundary is weaker than the
  vocabulary guarantees elsewhere in this design**, and weaker still on
  OpenRouter, which per ADR 0012 runs in plain-JSON mode rather than with
  guided decoding. A self-hosted vLLM server would constrain the *shape* of
  a decline, but no decoding constraint can constrain the *judgement* of
  when to emit one.
