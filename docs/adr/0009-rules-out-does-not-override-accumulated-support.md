---
status: accepted
---

# `rules_out` does not override accumulated support

`weights.yaml` states that `rules_out` is

> "Large enough that a single `rules_out` row drops a condition below
> `plausibility_floor` **regardless of accumulated support** — which is what
> makes it mean 'rules out' rather than 'counts heavily against'."

**That sentence is false.** Found by working the arithmetic while documenting
the thresholds, not by a test.

## The arithmetic

Weights add. `rules_out` is −4.0 and the floor is −2.94 log-odds, so a
`rules_out` row eliminates a condition only when prior support is below
**+1.06** log-odds.

| Support already gathered | After `rules_out` | Plausibility | Outcome |
|---|---|---|---|
| nothing | −4.0 | 0.018 | eliminated |
| 1 × `weak_support` (+0.6) | −3.4 | 0.032 | eliminated |
| 2 × `weak_support` (+1.2) | −2.8 | 0.057 | **survives** |
| **1 × `strong_support` (+1.5)** | **−2.5** | **0.076** | **survives** |
| 2 × `strong_support` (+3.0) | −1.0 | 0.269 | **survives** |

A single `strong_support` row is enough to make a condition immune.

## Why the validator did not catch it

`Weights._rules_out_must_actually_rule_out` checks that `rules_out` alone
reaches the floor:

```python
if rules_out > self.plausibility_floor_log_odds:   # −4.0 > −2.94 is False
    raise ValueError(...)
```

−4.0 clears −2.94, so it passes. But that tests elimination *from a standing
start*, which is strictly weaker than the "regardless of accumulated support"
the file claims. The check and the sentence were never the same statement.

## Impact today: none

`evidence.csv` contains **zero** `rules_out` rows. Every eliminating row in the
knowledge base is `argues_against`. So nothing currently depends on the broken
guarantee — this is a latent defect in a mechanism not yet used.

That is also why it is worth settling now rather than after rows exist that
assume the documented behaviour.

## Three ways to fix it, and why none is obvious

**A. Make `rules_out` absolute.** Special-case it so a matching row *sets* the
score below the floor rather than adding to it. Matches the name and the
documented intent. But it makes elimination unconditional, and an unconditional
eliminator is the most dangerous kind of row in the file: one mis-authored
`rules_out` could silently remove an urgent condition from every differential
that touches it. Under-triage is the dominant failure mode, so a mechanism that
can only ever remove conditions deserves suspicion.

**B. Make the magnitude large enough in practice.** Set `rules_out` to, say,
−12.0, so it dominates any realistic accumulation. Simple, keeps the arithmetic
uniform, no special case. But "large enough" is a guess about how much support a
condition can accumulate, and it becomes wrong the moment the evidence grid gets
denser.

**C. Fix the sentence, not the number.** Document `rules_out` honestly as
"counts very heavily against, and eliminates on its own from a standing start",
and tighten the validator's docstring so the check and the claim match.
Preserves the current conservative behaviour — a condition with real supporting
evidence is not dropped on one contrary row — but abandons the word "rules out".

## Decision

**C now, and revisit with the evaluation set.**

The current behaviour is the *safe* direction: a condition backed by a
characteristic sign is not eliminated by one contrary row. Given that eight of
twelve conditions have no eliminating rows at all, weakening elimination further
is not the pressing problem — the pressing problem is that nothing leaves the
differential (ADR 0007, finding 1).

But the present state is worse than either extreme, because elimination is
*conditional in a way nobody would predict*: it works from a standing start and
silently stops working after one strong row. So the documentation is corrected
immediately, and the choice between A and B waits for evidence about what
elimination actually needs to do.

## Consequences

- `weights.yaml` no longer claims elimination is unconditional.
- The validator keeps its check but its docstring now states exactly what it
  proves, which is not what the old comment implied.
- **Before any `rules_out` row is authored**, this decision must be revisited.
  The first such row is the point at which the choice between A and B stops
  being theoretical.
- Recorded in `KNOWLEDGE_BASE.md` §6a so the arithmetic stays visible to anyone
  reasoning about the thresholds.
