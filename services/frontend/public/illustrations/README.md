# Illustrations — download these by hand

The app expects five SVGs in this folder. **They are not committed**, and
they need to be fetched manually rather than by a script.

## Why by hand

[unDraw's licence](https://undraw.co/license) is generous about *use* —
free, commercial or not, no attribution, no permission needed. It is not
generous about *collection*:

> You may not … compile assets, vectors or images from unDraw to replicate a
> similar or competing service … distribute the assets in packs or otherwise
> … whether automated or manual … without our consent.

Two consequences, and they point the same way:

1. **No script may fetch these.** The clause names automated downloading
   explicitly, so `curl`, a build step, or an agent doing it on your behalf
   is out.
2. **The files stay out of git.** `HerHealthGPT/herhealthgpt` is a real
   repository; committing the SVGs is arguably distributing them. This
   project already excludes NICE CKS, RCOG, ACOG and UMLS over licence
   wording (see `CLAUDE.md`), and it would be inconsistent to take on a new
   grey area for decoration.

A person downloading art from a website to use in their own product is
exactly what unDraw is for. That person has to be you.

## How

1. Open <https://undraw.co/illustrations>.
2. Set the colour to **`#9F1239`** — the brand primary, `--primary` in
   `globals.css`. Everything on the site is themed to it, and an
   off-palette illustration will look pasted on.
3. Search the term below, pick one you like, download the SVG.
4. Save it here under the **exact filename** in the table. The filename is
   the contract — `Illustration` resolves `name` to
   `/illustrations/<name>.svg`.

| Save as | Search unDraw for | Used by |
|---|---|---|
| `onboarding.svg` | "medicine", "doctors", "healthy habit" | Sign-in / sign-up side panel |
| `urgency.svg` | "decide", "choice", "medical care" | Landing page, urgency-scale section |
| `welcome.svg` | "welcome", "good morning", "well done" | Dashboard, before the first chat |
| `conversation.svg` | "chat", "messaging", "conversation" | Empty chat list · onboarding step 2 |
| `safety.svg` | "safe", "security", "protection" | Onboarding step 3 ("Good to know") |
| `sources.svg` | "reading", "book lover", "research" | Onboarding step 4 · landing page |
| `resolved.svg` | "completed", "done", "confirmation" | A concluded consultation |
| `error.svg` | "bug fixing", "fixing bugs", "warning" | Route error boundary |
| `not-found.svg` | "page not found", "lost", "void" | 404 page |

Nine files. `welcome.svg` covers both onboarding step 1 and the dashboard,
and `sources.svg` covers both onboarding step 4 and the landing page — so
nine downloads fill eleven placements. Nothing else is reused: seeing the
same drawing twice inside one flow reads as a placeholder.

Pick calm, uncluttered ones. The audience is often worried and sometimes in
a hurry; busy art reads as noise.

## Nothing breaks if you skip this

`Illustration` renders **nothing** when a file is missing — no broken-image
icon, no reserved gap. Every layout using it is built to read correctly with
the art absent. Add them when you have them, in any order.

## Checking it worked

With the dev server running:

```bash
curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/illustrations/conversation.svg
```

`200` means the app can see it. `404` means the filename does not match the
table above.
