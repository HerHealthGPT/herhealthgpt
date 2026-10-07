---
status: runbook
issue: 11
parent: 5
---

# Runbook: a Google OAuth client for Google sign-in

This is an **operations runbook, not code**. #11's backend (`GoogleOAuthTokenVerifier`,
`sign_in_with_google`) is fully built and fully tested against a double that
supplies identities directly — but nothing in the codebase can prove it
against a *real* Google ID token, because no Google Cloud project or OAuth
client exists yet. This is the same gap #6 closed for SES before #10 could
send a real email; this runbook is that gap's Google equivalent.

> **Who does what.** Every step below needs the Google Cloud console and a
> Google account with billing/ownership on the project — human actions with
> credentials. An agent cannot perform any of them. What an agent can do is
> everything *after* you have a Client ID: set `HERHEALTH_GOOGLE_CLIENT_ID`,
> restart the server, and drive a real sign-in through it.

## Provisioning record — fill in when this is run

| Item | Value |
|---|---|
| Google Cloud project | `__________` |
| OAuth consent screen: user type | `__________` (External, unless this project ever moves to a Google Workspace org) |
| OAuth consent screen: publish status | `__________` (Testing, until #11's frontend ships — Testing mode caps sign-in to accounts added as test users, which is fine for this) |
| OAuth client ID | `__________` |
| OAuth client secret | *(not needed — see §3)* |
| Test user(s) added | `__________` |

## 1. Create (or choose) a Google Cloud project

1. [console.cloud.google.com](https://console.cloud.google.com) → sign in with the
   Google account that should own this.
2. Top-left project picker → **New Project**.
3. Name it `HerHealthGPT` (or reuse an existing project if the team already
   has one for this work — record which in the table above).

- [ ] Project created or chosen, recorded above.

## 2. Configure the OAuth consent screen

**APIs & Services → OAuth consent screen.**

1. **User type: External.** Users are the public (women in Egypt using the
   service), not members of a Google Workspace organisation.
2. **App information:**
   - App name: `HerHealthGPT`
   - User support email: a real monitored address (`support@herhealthgpt.org`
     if that inbox exists yet, per the sending identity #6 set up — otherwise
     the account owner's own address for now)
   - Developer contact email: same
3. **Scopes:** add `openid`, `email`, `profile` — the three claims
   `GoogleOAuthTokenVerifier` reads (`sub`, `email`, `email_verified`) come
   from `openid` + `email`; `profile` is conventional to request alongside
   them but nothing in this codebase reads it.
4. **Test users:** add every Google account that will sign in during
   development — **including your own**, if you want to test with it.
   While the app is in **Testing** publish status (the default, and the
   right one until there is a frontend to actually ship), Google refuses
   sign-in for any account not on this list, regardless of Client ID
   correctness. This is the single most common cause of a real Google
   sign-in failing during manual testing — check this list first.
5. Save. **Do not** click "Publish app" — that starts Google's verification
   process, which this project does not need until #11 has a real frontend
   in front of real users.

- [ ] Consent screen configured, still in **Testing** status.
- [ ] Your own Google account added as a test user.

## 3. Create the OAuth client ID

**APIs & Services → Credentials → Create Credentials → OAuth client ID.**

1. **Application type: Web application.** (Not "Desktop" or "Android" — this
   backend verifies tokens issued to a web client.)
2. **Name:** `HerHealthGPT backend` (cosmetic, shown only in the console).
3. **Authorized JavaScript origins:** add whatever origin you will actually
   sign in from while testing — see §4. **For the production deployment, add
   `https://herhealthgpt.org`** (the apex, where the frontend is served; not
   `api.` and not `www.`), and add it to the **Authorized redirect URIs** too.
   The Client ID is also a *build-time* value for the frontend image
   (`NEXT_PUBLIC_GOOGLE_CLIENT_ID`, repository variable) as well as a runtime
   secret for the backend — see
   [aws-deploy.md](aws-deploy.md#google-sign-in-in-production). For the OAuth Playground method,
   nothing here is required. For a real "Sign In With Google" button on a
   page you serve yourself, add that page's origin (e.g. `http://localhost:3000`
   or `http://localhost:8000`).
4. **Authorized redirect URIs:** only needed for the OAuth Playground method
   in §4 — add `https://developers.google.com/oauthplayground` if using it.
5. Create. Google shows a **Client ID** and a **Client secret**.

**Only the Client ID goes in this project's configuration.** The secret is
for the authorization-code exchange flow (a server trading a code for
tokens); `GoogleOAuthTokenVerifier` only ever *verifies* an already-issued ID
token and checks its audience against the Client ID — the secret plays no
part in that and must not be added to `infra/envs/backend.env` or anywhere
else in this repo.

- [ ] Client ID created, recorded above.
- [ ] Client secret **not** copied anywhere into this repository.

## 4. Get a real ID token to test with

Two ways, in order of how little you need to build:

### Fastest: Google's OAuth 2.0 Playground

1. [developers.google.com/oauthplayground](https://developers.google.com/oauthplayground)
2. Gear icon (top right) → **Use your own OAuth credentials** → paste the
   Client ID and Client secret from §3.
3. Step 1: under scopes, find and check `openid`, `.../auth/userinfo.email`,
   `.../auth/userinfo.profile` (or paste
   `openid email profile` into the manual scope box) → **Authorize APIs** →
   sign in with a test-user Google account from §2.
4. Step 2: **Exchange authorization code for tokens.**
5. The response includes an `id_token` field — a long `xxx.yyy.zzz` JWT.
   Copy it whole.

### More representative: a real "Sign In With Google" button

If you want to see the actual production flow rather than a developer tool,
serve a minimal HTML page loading
[Google Identity Services](https://developers.google.com/identity/gsi/web/guides/overview)
(`https://accounts.google.com/gsi/client`), configured with the Client ID
from §3, and read `response.credential` in its callback — that string is
the ID token. This needs the page's origin added to §3's authorized
JavaScript origins. Ask for this to be built if you want it; it is not part
of #11's backend scope.

- [ ] A real `id_token` obtained, one way or the other.

## 5. Wire it into the backend and test for real

1. Set `HERHEALTH_GOOGLE_CLIENT_ID` in `infra/envs/backend.env` to the
   Client ID from §3.
2. Restart the server (`make serve`, or however it is currently running) so
   the new value is picked up — `HERHEALTH_GOOGLE_CLIENT_ID` is read once,
   at start-up.
3. `POST /accounts/sign-in/google` with `{"id_token": "<the token from §4>"}`.
   A fresh test-user address should create a new user with a Google
   credential and no password; check the response body and, if wanted, the
   `credentials` table directly.

ID tokens from the Playground are short-lived (about an hour) — if testing
stalls and resumes later, get a fresh one rather than debugging a stale-token
401 that has nothing to do with the backend.

## Done when

The table at the top is filled in, a real sign-in has been driven through
`POST /accounts/sign-in/google` and produced the expected row in `users`
and `credentials`, and `HERHEALTH_GOOGLE_CLIENT_ID` is recorded wherever
this project's real deployment secrets live (not committed to the repo —
`infra/envs/backend.env` is gitignored, same discipline as
`HERHEALTH_SESSION_SECRET`).
