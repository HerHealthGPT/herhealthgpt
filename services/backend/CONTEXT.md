# Accounts

Who the user is, how she proves it, and what is kept for her. The context that
lets a consultation outlive the request that produced it.

Depends on [Triage](../../CONTEXT.md); Triage does not depend on it. See
[`CONTEXT-MAP.md`](../../CONTEXT-MAP.md) for the boundary and the terms that
collide across it.

> **Status: authored ahead of the code.** These terms were settled in design
> before the schema existed, so that the schema could be written in the language
> rather than the language reverse-engineered from a schema.

## Language

### Being someone

**User**:
A person with an account. One row, one human. Holds an email address, a display
name and a date of birth, and nothing clinical — everything she *reports* lives
in a conversation, not on her.

Date of birth was admitted in [ADR 0015](../../docs/adr/0015-a-user-may-keep-a-date-of-birth-and-a-health-note.md)
on the grounds that it is demographic rather than clinical: it is the same kind
of fact as an email address and reports no symptom. It is stored as a date, not
as an `age_band`, so the band can be derived fresh on every request — a band
stored at 44 would silently stay `40_to_44` past the birthday, and 45 is the
number `features.yaml` says separates perimenopause from PCOS. What she says
about her health is a **Health note**, below, and that is not held on her.
_Avoid_: account, profile, customer, patient

**Patient** is not a word this project uses, anywhere. She is not under anyone's
care here, and the word imports a clinical relationship the system does not have.

**Credential**:
One way a user can prove she is herself — a password, a Google identity, later a
passkey. A user has zero or more, each of a `kind`. Kept separate from the user
so a second kind can be added without a migration, and so "same email address"
can never by itself mean "same person".
_Avoid_: login, auth method, provider, identity

**Verification**:
Proof that a user controls the email address on her account, established by a
one-time code. Gates account recovery and identity linking, not access to advice.
_Avoid_: activation, confirmation, validation

**Linking**:
Attaching a second credential to an existing user. Permitted only when both sides
are verified — the local account's email confirmed, and the provider asserting
the address is verified too. An unverified local account is taken over rather
than linked, because it proved nothing.
_Avoid_: merging, connecting, associating

### Staying someone

**Session**:
An authenticated period. Backed by a refresh token that can be revoked, so
logging out and deleting an account take effect at once rather than whenever a
token happens to expire.
_Avoid_: login, connection, visit — and never use this word in Triage

**Access token**:
A short-lived bearer token proving the request comes from a signed-in user.
Minutes, not days, precisely because it cannot be revoked.
_Avoid_: JWT, bearer, auth token

**Refresh token**:
A long-lived opaque secret, stored server-side, exchanged for a new access token.
The revocable half of the pair, and the reason deletion can be honest.
_Avoid_: session token, cookie, key

### Keeping things

**Conversation**:
What the user sees in her history: one consultation, stored, named, revisitable
and deletable. The product-facing view of a clinical object.
_Avoid_: consultation, chat, session, thread

**Message**:
One row in a conversation — what she wrote, or what the system replied. Content
is encrypted at the application layer, not merely at rest.
_Avoid_: turn, utterance, entry, log

**Deletion**:
Removal, immediately and by cascade, with no recoverable copy in the live
database. Not a flag. Chosen over a grace period because a woman deleting an
account on this service may be doing so precisely because someone else can reach
her device, and a reversible window is the window in which they find it.
_Avoid_: soft delete, archive, deactivate, disable

**Cycle data**:
Menstrual tracking a user may import to give the system context. Hers, optional,
and deletable independently of her account.

Uploaded as an export file from any tracking app; only values that map onto
`features.yaml` are kept, and the file itself is never stored. She confirms what
was found before it is saved. When fresh, it may answer a cycle-pattern feature
so she is not asked it again — never a feature any red flag reads, and never a
value inferred from something she did not log. See
[ADR 0019](../../docs/adr/0019-cycle-data-is-imported-from-any-tracker-and-may-pre-fill-answers.md).
_Avoid_: health data, records, history

**Health note**:
Anything a user chooses to tell the system about herself once — a condition she
has been told she has, a medicine she takes — so she does not have to repeat it
at the start of every consultation. One per user, edited in place. Optional,
hers, and deletable on its own without closing her account, exactly as cycle
data is.

Unverified free text she typed, and never treated as a symptom she is reporting
now: it cannot fire a red flag, and it cannot carry a conclusion by itself. It
reaches the reasoning model as background in the system prompt, never as a turn
in the transcript, because she did not say it in the consultation being
recorded. See [ADR 0015](../../docs/adr/0015-a-user-may-keep-a-date-of-birth-and-a-health-note.md).
_Avoid_: history, medical record, records, health data, profile, intake

## Resolved

**Sessions are opaque and revocable, access tokens are not.** A plain JWT cannot
be revoked, and "your account will finish deleting within 24 hours" is the wrong
promise on this service. Pairing a short-lived access token with a server-side
refresh token keeps the ergonomics and makes deletion honest. Settled 2026-08-05.

**Email, not phone.** SIM registration in Egypt is mandatory and identity-linked,
so a phone number resolves to a named person in a way an email address does not.
Storing one beside a consultation that mentions a possible pregnancy or an
infection creates an identity-linked clinical record by construction. Settled
2026-08-05.

**Message content is encrypted at the application layer**, not only by the
database at rest. Encryption at rest defends against a stolen disk; the realistic
breach path for this project is a leaked snapshot, an over-broad grant, or a
credential in git history, and application-level encryption defeats all three.
It does not defend against the application itself being compromised, and that
limit is stated rather than glossed. Settled 2026-08-05.

## Open question

**Whether the team should be able to read conversations at all.** The chosen
design says yes-through-the-application: encrypted in the database, decryptable
by the service. A per-user key derived from her password would remove that, and
breaks on contact with Google sign-in (no password to derive from) and with
password reset (which would destroy all her history). Left as a documented
limitation rather than solved.
