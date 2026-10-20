# HerHealthGPT frontend

The web app at [herhealthgpt.org](https://herhealthgpt.org): Next.js 16, React
19, TypeScript, Tailwind CSS 4, Radix UI. A normal responsive web app, **not a
PWA**. English, Arabic (right-to-left) and French.

## Run

```bash
npm ci
npm run dev                      # http://localhost:3000
npm run build && npx next start  # production build
npm run lint
```

The app calls the API at `/api/*`. Locally Next.js forwards that to
`BACKEND_URL` (default `http://localhost:8000`); in production the image is
built with `NEXT_PUBLIC_API_URL=https://api.herhealthgpt.org`. The whole stack:
[`../../docs/runbooks/running-the-app.md`](../../docs/runbooks/running-the-app.md).

## Where things are

| Path | What |
|---|---|
| `src/app/(auth)/` | sign-up, sign-in, email verification, password reset |
| `src/app/(app)/` | onboarding, dashboard, chat, settings, how it works |
| `src/app/cycle-import-guide/` | how to prepare a cycle-data file |
| `src/components/chat/` | messages, conclusion and decline cards, sources, the her-data source, the composer |
| `src/components/account/` | profile, health details, cycle-data import, kept files, account deletion |
| `src/i18n/messages/{en,ar,fr}/` | every string, in three languages |
| `src/lib/api/` | the API client (`client.ts`), endpoints, types |

Every user-facing string goes in all three message files. No copy may
describe the system as diagnosing.

`AGENTS.md` is written by `next dev`: this Next.js version has breaking changes,
so read `node_modules/next/dist/docs/` before relying on older Next.js habits.
