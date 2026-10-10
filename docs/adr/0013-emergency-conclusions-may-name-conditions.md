---
status: proposed
---

# An EMERGENCY conclusion may name matching conditions

> **Proposed, not accepted.** Taken as an in-session product decision on
> 2026-09-02, not from supervisor or mentor review — the same gate
> [ADR 0011](0011-controller-free-triage.md) and
> [ADR 0012](0012-openrouter-reasoning-and-guarded-web-fallback.md) each
> named for themselves. It is implemented in code already (see § Status);
> this ADR exists so the reversal is on the record with its reasoning and
> its risk, rather than sitting as an unexplained relaxation in a
> validator.

## Context

[ADR 0011](0011-controller-free-triage.md) generalised one of `CLAUDE.md`'s
oldest rules. `CLAUDE.md` says cancer is deliberately unmodelled and
*"served by red flags instead — postmenopausal bleeding routes to a GP
without ever naming why."* ADR 0011 extended exactly that discipline to
**every** red flag, and `TriageDecision` enforced it structurally:
`matching_conditions` and `red_flag_id` were mutually exclusive, so a
red-flag-driven conclusion could not name a condition even if the model
tried.

The reasoning behind that rule has not changed and is not disputed here:
red flags exist to escalate on a *symptom pattern*, and naming a specific
condition while escalating risks (a) being wrong about a specific scary
thing, and (b) reading as a diagnosis in the moment a user is least able
to weigh it critically. `CLAUDE.md`'s binding *"It never diagnoses"* is the
rule that discipline serves.

Against that, the team's product judgement after using the built system:
at the top of the urgency scale, being told only *"seek emergency care
now"* with no indication of what the warning sign relates to is itself a
poor outcome — it gives someone about to walk into an emergency department
nothing to say about why she is there, and nothing to check the guidance
against.

## Decision

**`matching_conditions` may be populated alongside `red_flag_id` when, and
only when, `action_code` is `EMERGENCY`.**

Every other case keeps ADR 0011's rule exactly:

| Decision | May name conditions? |
|---|---|
| `CONCLUDE`, no red flag | Yes (unchanged — ADR 0008) |
| `CONCLUDE`, red flag, `EMERGENCY` | **Yes — this ADR** |
| `CONCLUDE`, red flag, `URGENT_SAME_DAY` | No (unchanged) |
| `ASK` | No (unchanged) |

Scoping this to `EMERGENCY` alone is deliberate, and narrower than "let
red-flag conclusions name conditions". `URGENT_SAME_DAY` red flags —
which is most of `red_flags.yaml`, including
[`severe_pelvic_pain`](0004-severe-pelvic-pain-is-urgent-not-emergency.md) —
keep the original restriction, because the argument above (she is going to
an emergency department right now and needs something to say) applies at
`EMERGENCY` and not at a same-day appointment.

## What this does not change

- **`CLAUDE.md`'s "never diagnoses" rule is untouched.** A named condition
  is still rendered as *"may match patterns our sources associate with…"*,
  never as *"you have…"*. The system prompt
  (`herhealth_backend.triage.agent.DEFAULT_SYSTEM_PROMPT`) states this in
  the same sentence that grants the exception.
- **Cancer is still unmodelled.** It is absent from `conditions.yaml`, so
  no `matching_conditions` value can name it — this ADR cannot resurrect
  it, because the closed vocabulary never contained it. The specific
  hazard `CLAUDE.md`'s cancer rule guards against is therefore still
  structurally impossible, not merely discouraged.
- **The five-condition cap** (ADR 0008 / `Field(max_length=5)`) applies
  identically here.

## Status

Implemented 2026-09-02:

- `packages/contracts/src/herhealth_contracts/decision.py` —
  `_shape_matches_type` gained the `EMERGENCY` exception.
- `packages/contracts/tests/test_decision.py` — **new**; the first test
  coverage `TriageDecision` has had. Pins both the rule and the exception:
  a red-flag `URGENT_SAME_DAY` conclusion naming a condition is still
  refused, an `EMERGENCY` one is not.
- `herhealth_backend.triage.agent.DEFAULT_SYSTEM_PROMPT` and
  `herhealth_backend.triage.clients._JSON_SHAPE_INSTRUCTION` — updated so
  the model is told the rule and its exception, not just structurally
  prevented from breaking one of them.

## Risk register

- **This is a relaxation of a safety rule, made on product judgement, not
  on evidence that the rule was wrong.** No measurement showed the old
  behaviour causing harm, and none shows the new behaviour avoiding it.
  It is recorded here as a judgement call so a future reviewer can weigh
  it as one.
- **The named condition at `EMERGENCY` comes from the same model whose
  action-code and vocabulary choices this project's own risk registers
  already flag as unverified** (ADR 0011: *"the model choosing the wrong
  action code or the wrong question within the allowed vocabulary… is the
  gap the deterministic controller closed and this design does not"*).
  A wrong condition named at the highest urgency is the worst-placed
  version of that existing gap, and this ADR moves the system into it
  deliberately.
- **Nothing measures this.** `make eval` has no metric for whether a named
  condition at `EMERGENCY` was appropriate, and adding one would need
  labels the benchmark does not carry. Until it does, this rests on
  review of transcripts, not on a number.
