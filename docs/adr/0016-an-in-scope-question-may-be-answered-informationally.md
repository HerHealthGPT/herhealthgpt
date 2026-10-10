---
status: proposed
---

# An in-scope question may be answered informationally, not triaged

> **Proposed, not accepted.** Taken as an in-session product decision on
> 2026-10-10 at the product owner's request, not from supervisor or mentor
> review — the same gate [ADR 0011](0011-controller-free-triage.md),
> [ADR 0012](0012-openrouter-reasoning-and-guarded-web-fallback.md),
> [ADR 0013](0013-emergency-conclusions-may-name-conditions.md) and
> [ADR 0014](0014-an-off-scope-message-is-declined-not-triaged.md) each
> named for themselves.

## Context

After [ADR 0014](0014-an-off-scope-message-is-declined-not-triaged.md),
`TriageDecision` had three legal shapes, and every one of them is about
**her**:

| shape | what it assumes she sent |
|---|---|
| `ASK` | a case, not yet clear enough to rule on |
| `CONCLUDE` | a case, clear enough to rule on |
| `DECLINE` | something this system does not cover |

None of them fits *"what actually is PCOS?"* — a question about the subject
matter, from someone who has reported no symptom. It is squarely inside the
knowledge base's own subject matter, so declining it is wrong on ADR 0014's
own terms: scope there is defined as *"what the knowledge base can actually
ground"*, and `conditions.yaml` grounds PCOS in 19 authored rows. The other
two shapes fit no better. `ASK` puts a clarifying question to a woman with
nothing to clarify. `CONCLUDE` assigns one of four urgency levels to a
question that described no case — and would then close the consultation,
because a `CONCLUDE` concludes.

This is the same structural fault ADR 0014 diagnosed, one shape further
along: **a legitimate move was unrepresentable, so the model had to pick the
least-bad wrong shape.** ADR 0014's own risk register anticipated the
direction — *"that it does not decline a real reproductive-health concern
phrased unusually… a woman refused is a woman not triaged"* — and an
informational question is the clearest instance of it.

The retrieval side was already built for this and unused by it. Every turn
retrieves sentence-level passages from the reviewed corpus (ADR 0010), and
`services/model`'s `/search` reserves slots for evidence statements. Those
passages were only ever read *to* the model as background for a triage
decision; nothing could hand what they say to the person who asked.

## Decision

A fourth shape, `DecisionType.INFORM`: answer the question from the
retrieved passages, cite them, assign no urgency.

The answer she reads lives in a field of its own, **`answer_text`**, for the
reason `question_text` is its own field — `rationale` is one or two
sentences on *why* this turn went the way it did, held to that by the prompt
and by `clients._reject_leaked_internals`, and an informational body is a
different kind of text at a different length.

**It is deliberately the narrowest shape in the enum**, because it is the one
shape that could be used to walk around triage, and under-triage is this
project's dominant failure mode (`CLAUDE.md` rule 3). Four properties hold
by schema, not by prompt:

1. **No `action_code`.** An INFORM cannot say `SELF_CARE`, so it can never
   function as reassurance.
2. **`citations` required non-empty, with no `red_flag_id` route to
   grounding.** Note the direction: this is **stricter** than `ASK` and
   `CONCLUDE`, which may ground themselves on a red flag instead. ADR 0014
   found a shape that was *forced to manufacture* a citation; this closes the
   same hole from the other side — an answer cannot be given without one.
3. **No `red_flag_id`.** A warning sign is grounds to escalate, never grounds
   to explain. A decision that has noticed one cannot be an INFORM at all.
4. **No `matching_conditions`.** That field means "conditions whose pattern
   *her answers* matched", and an INFORM matched nothing against her. An
   informational answer may discuss a condition in prose, grounded in its
   citations; it may never attach one to her. **"Never diagnoses" therefore
   holds on this path by construction, not by wording.**

`observed` *is* allowed, unlike on a DECLINE, and the asymmetry is the point:
an off-scope message tells us nothing about her health, whereas an in-scope
question may carry real information in passing (*"I get awful cramps — what
is endometriosis?"*). Recording it is what lets the next turn pick up where
this one left off.

**An INFORM does not conclude the consultation.** The session stays `active`,
the composer stays open, and nothing is added to `asked`. She is answered and
the conversation carries on — the same treatment a DECLINE gets, for a
related reason: neither a question she asked along the way nor an off-scope
aside should cost her a consultation.

**It renders as an ordinary assistant chat bubble**, not a card. A conclusion
gets a card because it is a terminal verdict with an urgency headline and an
action; an informational answer is a reply in a conversation that is still
going, and giving it a card would signal an ending that has not happened.
Its sources appear the way a clarifying question's do, as a compact *"Based
on …"* line.

### The rule the schema cannot carry

**A message describing her own current symptoms is triaged, never explained.**
Nothing in the schema can distinguish *"what is endometriosis?"* from *"I
think I have endometriosis, what is it?"* — both are in scope, both are
phrased as questions, and only the second is a consultation. That rule lives
in `DEFAULT_SYSTEM_PROMPT`, stated as a rule about when **not** to inform and
placed immediately after the SCOPE block so it is read before the invitation
to use the shape has settled. The prompt resolves the tie explicitly: if it
is unclear which she wants, **ask**.

This is the same kind of gap ADR 0011 opened and named, and it is named here
rather than implied. See the risk register.

## What this does not change

- **The grounding rule for `ASK` and `CONCLUDE` is untouched**, and `INFORM`
  is held to a stricter one.
- **Nothing about the four action codes.** `INFORM` is not a fifth urgency
  level; like `DECLINE` it sits beside the urgency question rather than on
  its scale, and no `actions.yaml` entry is added.
- **The closed vocabularies.** An INFORM names no feature as a question and
  no condition as hers, so it cannot widen what the system may suspect.
  Cancer remains unmodelled and therefore unnameable.
- **No knowledge file changes.** This shape reads the corpus that already
  exists; not one row, feature or rule was added, edited or reinterpreted for
  it.
- **The verification protocol.** An informational answer restates cited
  passages, which is exactly what every clinical row in this project already
  is. It introduces no new class of unsourced claim — and the citation
  requirement is what keeps that true.

## Status

Implemented 2026-10-10:

- `packages/contracts/src/herhealth_contracts/decision.py` —
  `DecisionType.INFORM`, the `answer_text` field, and an `_shape_matches_type`
  branch enforcing all four properties above. `answer_text` is rejected on
  every other type. A `mode="before"` coercion promotes `rationale` into an
  empty `answer_text`, the same recover-rather-than-retry trade as
  `matching_conditions` and `_drop_conditions_named_beside_a_red_flag`.
- `packages/contracts/tests/test_decision.py` — the happy path, the
  promotion, the citation requirement, and the forbidden fields
  (parametrised).
- `herhealth_backend.triage.agent.DEFAULT_SYSTEM_PROMPT` — when to inform
  and, at greater length, when not to.
- `herhealth_backend.triage.agent.run_consultation` — an INFORM continues the
  scripted loop rather than tripping the ASK-only assertion.
- `herhealth_backend.triage.clients` — the `inform` shape and `answer_text`
  in `_JSON_SHAPE_INSTRUCTION`; `_reject_leaked_internals` now also checks
  `answer_text`, which is the longest user-facing text this system produces
  and so has the most room for internals to surface in.
- `herhealth_backend.app.triage.routes` — `answer_text` is the stored
  assistant message; an INFORM leaves the session `active`; the
  dropped-answer warning does not fire on one, because a question asked back
  genuinely leaves the pending feature open.
- `herhealth_backend.triage.demo_clients` — a keyword-matched informational
  answer, so the path is exercisable offline with
  `HERHEALTH_TRIAGE_MODE=demo` and no OpenRouter key. The detector refuses to
  inform when the message contains first-person symptom talk, which is the
  prompt's tie-break expressed in the one place it can be tested
  deterministically.
- `services/frontend` — `"inform"` and `answer_text` on the `TriageDecision`
  type; an informational answer maps to an ordinary assistant message entry;
  `ChatMessage` now preserves blank-line paragraph breaks, which a long
  answer needs and a short one is unaffected by.

No change was needed in `triage/vocabulary.py` or `triage/provenance.py`:
both key off `DecisionType` and an INFORM passes or short-circuits correctly.
Citations are still checked against what was actually retrieved this turn,
which is what makes property 2 meaningful rather than cosmetic. As in ADR
0014, that is a property of those seams and worth recording as evidence they
are drawn in the right place.

## Risk register

- **The inform-versus-triage boundary is judged by the model, and nothing
  checks it.** This is the central risk and it points the wrong way against
  `CLAUDE.md` rule 3. The schema guarantees an informational answer carries no
  urgency; it cannot guarantee the model declines to inform when she is
  describing her own symptoms. A woman who asks *"is it normal to bleed this
  heavily?"* and is handed an explanation of heavy menstrual bleeding instead
  of being asked three questions has been **under-triaged** — the failure
  this project was built around. The prompt states the rule and resolves the
  tie toward asking; that is mitigation, not a guarantee, and it is the same
  class of gap ADR 0011's risk register already carries for red flags.
- **It is unmeasured.** `make eval`'s 540 cases are symptom presentations with
  risk and action labels; not one is an informational question, so the
  benchmark cannot detect either over- or under-informing. Adding cases with
  expected-`inform` labels — and, more importantly, symptom cases phrased as
  questions, where `inform` is the **wrong** answer — is the obvious next step
  and has not been done. Until it is, this rests on manual transcript review.
  This is the same hole ADR 0014 recorded for declines, now wider, and the two
  should be closed together.
- **It increases the surface for ungrounded prose.** An informational answer
  is the longest text this system shows and the model is explicitly asked to
  be generous with it. The citation requirement proves passages were
  retrieved and cited; it does not prove the prose stayed inside them. A
  per-sentence grounding check is the analogue of `make verify-quotes` for
  generated text and does not exist. `_reject_leaked_internals` catches
  leaked machinery, not drift.
- **`enforce_provenance_cap` does not apply.** That function floors a
  `SELF_CARE` conclusion at `ROUTINE_APPOINTMENT` when every citation behind
  it is a live, unreviewed web fallback (ADR 0012 §3, rule 4). An INFORM has
  no action code to floor, so an informational answer may be built entirely
  on live-fallback passages with nothing marking it as thinner than one built
  on the reviewed corpus. The UI labels such a source *"looked up live"*,
  which is the only signal today. Whether an INFORM should be refused outright
  on fallback-only grounding is an open question this ADR does not settle.
- **Red-flag recall is unaffected in principle and untested in practice.**
  Property 3 means an INFORM cannot carry a `red_flag_id`, so an escalation
  cannot be smuggled into an informational answer. It does not stop the model
  informing on a message a red-flag rule *would* have matched had it
  evaluated one — which is ADR 0011's open gap, reached by a new route.
- **One more shape is one more thing the model gets wrong.** The live
  failure modes already logged for this contract are a missing `action_code`,
  an invented condition id, and `"conclude": false` as an extra key
  (`docs/runbooks/running-the-app.md` §5). A fourth type with a fifth
  user-facing field will have its own. The `rationale`-to-`answer_text`
  promotion absorbs the most likely one; the rest will surface as retries,
  which cost a full generation each.
