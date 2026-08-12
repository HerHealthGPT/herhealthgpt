# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — it names each bounded context, points at
  its glossary, and records the terms that mean different things on either side
  of a boundary. Read it first.
- **The `CONTEXT.md` for whichever context you are working in**, as listed in the
  map. Read every one relevant to the topic; a change that spans a boundary needs
  both.
- **`docs/adr/`** — the architecture decision records. Read the ones that touch
  the area you are about to work in.

If any of these don't exist, **proceed silently**. Don't flag their absence and
don't suggest creating them upfront; `/domain-modeling` creates them lazily when
terms or decisions actually get resolved.

## File structure

This repo is **multi-context**. The vocabulary genuinely divides: the clinical
reasoning language (feature, condition, evidence row, plausibility, action code)
shares nothing with the identity and persistence language (user, credential,
session, conversation, message), and two words collide outright across the
boundary.

```
/
├── CONTEXT-MAP.md              the contexts, the boundary, the collisions
├── CONTEXT.md                  Triage — clinical reasoning, knowledge, evaluation
├── docs/adr/                   decisions, system-wide
├── knowledge/                  the seven knowledge files      (Triage)
├── packages/contracts/         shared schemas                 (Triage)
├── services/data/              ingestion, validation, eval    (Triage)
└── services/backend/
    ├── CONTEXT.md              Accounts — identity, sessions, conversations
    └── src/herhealth_backend/  triage core (Triage) + API and accounts (Accounts)
```

`services/backend` deliberately holds code from both contexts. The boundary is a
language boundary, not a directory one, and pretending otherwise would mean
splitting a service for the sake of a diagram.

## Use the glossary's vocabulary

When your output names a domain concept — an issue title, a refactor proposal, a
hypothesis, a test name — use the term as defined in the `CONTEXT.md` for the
context you are in. Don't drift to synonyms the glossary explicitly avoids; the
`_Avoid_` lines are there because each of those synonyms once caused a real
misunderstanding.

**Watch the collisions.** `CONTEXT-MAP.md` lists the words that mean different
things in different contexts. Using one of them in the wrong context is the
easiest way to introduce a bug that reads as correct.

If the concept you need isn't in any glossary yet, that's a signal — either you
are inventing language the project doesn't use (reconsider), or there is a real
gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than
silently overriding:

> _Contradicts ADR-0005 (plausibility is an independent logistic) — but worth
> reopening because…_

This repo already treats superseded decisions this way: `CLAUDE.md` records that
the robots-policy rule replaced an earlier guess, and says so in the text rather
than quietly deleting the old reasoning. Do the same.
