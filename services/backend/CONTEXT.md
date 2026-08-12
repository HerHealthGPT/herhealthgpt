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
A person with an account. One row, one human. Holds an email address and nothing
clinical — everything she reports lives in a conversation, not on her.
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
_Avoid_: health data, records, history

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
