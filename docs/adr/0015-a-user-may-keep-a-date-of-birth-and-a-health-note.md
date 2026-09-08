---
status: proposed
---

# A user may keep a date of birth and one health note

> **Proposed, not accepted.** An in-session product decision, 2026-09-06,
> taken with the person building the app rather than at supervisor or mentor
> review — the same gate [ADR 0011](0011-controller-free-triage.md),
> [ADR 0012](0012-openrouter-reasoning-and-guarded-web-fallback.md),
> [ADR 0013](0013-emergency-conclusions-may-name-conditions.md) and
> [ADR 0014](0014-an-off-scope-message-is-declined-not-triaged.md) each named
> for themselves. It amends a glossary, so it is on the record rather than
> sitting as an unexplained column.

## Context

The product asked for two things at sign-up: a mandatory date of birth, and
an optional free-text field for anything she wants the system to know.

That collides head-on with the Accounts glossary
([`services/backend/CONTEXT.md`](../../services/backend/CONTEXT.md)), which
defines a **User** as holding *"an email address and nothing clinical —
everything she reports lives in a conversation, not on her"*, and lists
*history* under _Avoid_ for cycle data. Taken literally, neither field could
exist.

Three facts decided the shape:

1. **Age is not incidental to this system, it is load-bearing.**
   `knowledge/features.yaml` records that `age_band` *"carries weight far
   beyond PCOS. Separates perimenopause from PCOS in women over 45, and makes
   bleeding after menopause interpretable at all."* Without a stored age,
   every consultation spends one of its few turns re-asking it.
2. **Triage never needs a date, only one of six bands.** `age_band`'s
   `allowed_values` are `under_20`, `20_to_29`, `30_to_39`, `40_to_44`,
   `45_to_54`, `55_plus`. A date is strictly more identifying than the system
   can use — and this team has already refused identity-linked data on that
   reasoning once ("Email, not phone", settled 2026-08-05).
3. **Against that, a stored band goes stale on a birthday, at exactly the
   boundary that matters.** A user who registers at 44 is silently treated as
   `40_to_44` forever, and 45 is the number `features.yaml` names.

## Decision

**Date of birth is stored on the user; the health note is not.**

| Field | Where | Required |
|---|---|---|
| `users.date_of_birth` | on the user, beside `email` and `display_name` | at sign-up |
| `health_notes.content` | its own table, one row per user | never |

**The split is the whole point.** A date of birth is *demographic* — the same
kind of thing as an email address, and it reports no symptom. The free-text
note is what she says about her health, which is precisely what the glossary
means by clinical. So the glossary's sentence survives intact for the note:
it does not live on her, it lives beside her, and it can be deleted on its
own without closing her account — the property that glossary already asks of
optional cycle data.

**The band is derived at read time, never stored.** `triage.age_bands`
converts a date to a band on each request, so a consultation run on her
birthday uses the band she is in that morning. This is why the mandatory
field is a date rather than the dropdown the vocabulary would suggest.

**"Mandatory" means asked of every new sign-up, not enforced by the column.**
`date_of_birth` is nullable. Accounts created before migration 0009 have no
date to backfill, and a placeholder would be a fact we invented; absent means
unknown and is handled as unknown everywhere. Existing users are shown the
step next time they pass through onboarding and can set it in Settings, but
are **not** locked out of the app — a hard gate would deny urgency guidance to
a woman who came back because something is wrong, which is the wrong trade in
a system whose stated dominant failure mode is under-triage.

**The word "history" is not used**, in code, schema or UI copy. It is on the
glossary's _Avoid_ list, and it invites reading the field as a medical record.
It is a **health note**: unverified text she typed, once.

### How it reaches the model, and what stops it acting like a symptom

`agent.render_known_background` renders both into the **system prompt**, not
into the transcript. Injecting a synthetic user turn was considered and
rejected: she did not say it in this consultation, and a fabricated message
in a record meant to be replayable and auditable is a lie about what
happened.

The block states three things about the note, each pinned by a test in
`tests/test_known_background.py`:

- it is **unverified** and may be months old,
- it is **not a symptom she is reporting now**,
- it **may not fire a warning sign on its own**.

That last one matters most. A woman who typed "I have PCOS" in Settings has
told us nothing about today, and a red flag inferred from stored free text
would escalate on something no one checked this turn. Red flags stay derived
from what she says in the consultation.

The age band is presented differently and deliberately: as an answer she has
already given to the `age_band` feature, with an explicit instruction not to
ask again. That is the entire benefit being bought.

## What this does not change

- **Nothing clinical is asserted by either field.** A note is never rendered
  to her as a finding, and `TriageDecision` is untouched — no new decision
  type, no new action code, and `matching_conditions` still comes only from
  `conditions.yaml`.
- **The closed vocabularies.** `age_bands` can only emit values that exist in
  `features.yaml`, asserted in both directions by `tests/test_age_bands.py`,
  so a renamed band breaks a test rather than producing an id
  `ClosedVocabularyViolation` would later reject.
- **Deletion stays honest.** `health_notes.user_id` cascades, so deleting an
  account removes the note in the same statement — the glossary's **Deletion**
  term requires no recoverable copy, and a surviving row of clinical free text
  would violate it.

## Status

Implemented 2026-09-06:

- `services/backend/migrations/versions/0009_dob_and_health_note.py` — the
  column and the table. The revision id is kept under 32 characters, because
  `alembic_version.version_num` is `varchar(32)` and a longer id fails *after*
  the DDL has already run.
- `app/accounts/models.py` — `User.date_of_birth`, and `HealthNote`.
- `app/accounts/profile.py` — validation (`MIN_AGE_YEARS = 13`,
  `MAX_AGE_YEARS = 120`, `MAX_HEALTH_NOTE_LENGTH = 2000`) and the writes. A
  date is refused rather than clamped: age derives a band that changes what
  the system suspects, so a guess here is a guess about that.
- `app/accounts/routes.py` — `date_of_birth`, `age_band` and
  `has_health_note` on `UserSummary`; `GET`/`PUT`/`DELETE
  /accounts/health-note`. The note's *text* is deliberately not on `/me`,
  which the app polls, so unverified clinical free text is fetched only when
  something will show it.
- `triage/age_bands.py` — date to band, pure, `today` injected so a
  birthday-boundary test can name the day it means.
- `triage/agent.py` — `render_known_background`, and `run_turn(background=…)`.
- `app/triage/routes.py` — `_known_background`, the one place the two
  contexts meet over her profile, which `CONTEXT-MAP.md` permits only at the
  API layer.
- `services/frontend` — `ProfileDetailsStep` (first stage of first-time
  onboarding, shown only when `date_of_birth` is null) and
  `HealthDetailsForm` in Settings.
- `services/backend/CONTEXT.md` — the **User** term amended and a **Health
  note** term added, so the glossary describes the code rather than
  contradicting it.

## Risk register

- **This weakens a privacy stance the project took deliberately.** Before
  this, a stolen snapshot of `users` yielded email addresses. It now yields
  email plus date of birth, which together are a far better identifier — and
  `health_notes` yields unverified clinical statements next to them. The
  "Email, not phone" decision refused exactly this kind of accumulation; this
  ADR accepts a smaller version of it for a stated clinical benefit, and that
  is a judgement, not a finding that the earlier reasoning was wrong.
- **`health_notes.content` is stored in plaintext.** `CONTEXT.md` records
  application-layer encryption of clinical content as *settled* since
  2026-08-05, but it is **not implemented** — `messages.content` is plain
  `Text` today and this column matches it. So this inherits an existing gap
  rather than opening a new one, but it widens what a leaked snapshot
  contains. Encrypting both columns is the fix and has not been done.
- **A note can push the model toward a condition, and nothing measures
  whether that is good.** The framing forbids concluding from it alone, but a
  model told "she has previously written: PCOS since 2019" is not neutral
  about PCOS afterwards. `make eval`'s 540 cases carry no profile data, so
  the benchmark cannot detect either an improvement or an anchoring bias.
  This is unmeasured, and it is the risk a reviewer should push on hardest.
- **The age band now enters the prompt as settled fact.** If she mistypes her
  year of birth, every subsequent consultation is quietly reasoned in the
  wrong band, and the validation above only catches implausible dates, not
  wrong ones. She can correct it in Settings; nothing prompts her to check.
- **Prompt-only enforcement, again.** As in
  [ADR 0014](0014-an-off-scope-message-is-declined-not-triaged.md), the
  schema cannot constrain a judgement. Nothing structurally prevents the
  model from treating the note as a symptom report; only the wording asks it
  not to.
