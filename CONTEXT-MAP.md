# Context map

This repository holds two bounded contexts. They share a codebase and a
deployment; they do not share a language.

| Context | Glossary | What it talks about |
|---|---|---|
| **Triage** | [`CONTEXT.md`](CONTEXT.md) | Clinical reasoning, the knowledge base, provenance, and evaluation |
| **Accounts** | [`services/backend/CONTEXT.md`](services/backend/CONTEXT.md) | Who the user is, how she proves it, and what is kept for her |

## Why two, and not one

The Triage glossary defines twenty-two terms. Every one of them is about asking,
suspecting, deciding or citing — *feature*, *condition*, *evidence row*,
*plausibility*, *action code*, *red flag*, *source quote*. Not one concerns a
person with a login.

The Accounts vocabulary — *user*, *credential*, *session*, *conversation*,
*message* — has no overlap with it and no dependency on it. A change to how
refresh tokens are revoked cannot affect what `argues_against` means, and vice
versa.

Keeping them in one glossary would have meant a single list where half the terms
are irrelevant to whoever is reading, and the collisions below would have had
nowhere to be recorded.

## The boundary

Accounts **depends on** Triage, never the reverse.

```
Accounts  ──uses──▶  Triage
(who she is,          (what to ask,
 what is kept)         what to advise)
```

The triage core must stay runnable with no server, no database and no user — that
is what makes the evaluation harness possible, and it is why `TriageEngine` takes
a `KnowledgeBase` and injects nothing. **No module in the Triage context may
import anything from Accounts.** If it needs to, the design is wrong.

The two meet at exactly one place: the API layer starts a consultation on behalf
of an authenticated user, and stores the result against her account.

## Collisions — read this before naming anything

These words mean different things on either side of the boundary. Using one in
the wrong context produces code that reads as correct and is not.

### Consultation *(Triage)* vs Conversation *(Accounts)*

**The same events, described from two sides.** A *consultation* is the clinical
object: a sequence of turns in which features are answered, a differential moves,
and an action code is reached. A *conversation* is the product object: what she
sees in her history, what she can name, delete, or come back to.

One consultation is stored as one conversation. They are not synonyms and neither
term should be used in the other's context. `run_consultation` and `Transcript`
stay as they are; the persistence layer says `Conversation` and `Message`.

*Avoid in Triage:* conversation, chat, thread
*Avoid in Accounts:* consultation, transcript, turn

### Session

**Currently only an Accounts term, and it must stay that way.** In Accounts a
*session* is an authenticated period, backed by a refresh token, revocable on
logout or account deletion.

The Triage context has no session and needs none — a consultation is a list of
answers, and its state is a value that can be replayed. If a `Session` type ever
appears in the triage core, something from Accounts has leaked across the
boundary.

*Avoid in Triage:* session — say `TriageState` or "consultation"

### Clarification *(Triage)* vs message *(Accounts)*

A *clarification* is a turn in which the system asks rather than concludes; it is
a measured quantity — clarification recall is a gated metric. A *message* is a
row in a conversation. Every clarification is stored as a message; most messages
are not clarifications.

*Avoid in Accounts:* clarification, probe

## Adding a third context

Two are enough today. If a third is proposed, the test is the one used here:
**does it have vocabulary of its own that the existing glossaries do not, and
would putting its terms in an existing glossary make that glossary worse?** A new
directory is not a new context. A new language is.

Candidates that have been considered and rejected as separate contexts:

- **Knowledge and provenance** (*source*, *source quote*, *batch*, *verification
  protocol*) — inseparable from Triage. Every evidence row carries a source quote;
  splitting them would put both halves of one sentence in two glossaries.
- **Evaluation** (*case*, *register style*, *silver annotation*) — shares
  *under-triage*, *over-triage* and *action code* with Triage, and exists to
  measure it. A sub-section of the Triage glossary, not a peer of it.
