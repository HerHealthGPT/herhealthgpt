# syntax=docker/dockerfile:1
#
# The Next.js frontend. Build from THIS directory:
#
#   docker build -t herhealth-frontend \
#     --build-arg NEXT_PUBLIC_API_URL=https://api.herhealthgpt.org \
#     --build-arg NEXT_PUBLIC_GOOGLE_CLIENT_ID=<client id> \
#     services/frontend
#
# (The build context is services/frontend, not the repo root: the frontend has
# its own package-lock.json and imports nothing from the Python side. The
# repo-wide .dockerignore does not apply to this context.)
#
# NEXT_PUBLIC_* values are INLINED into the JavaScript bundle at BUILD time. A
# runtime environment variable with the same name does nothing, so they are
# build args, and a different API host means a different image.
#
# next.config.ts sets output: "standalone", so the runtime image carries only
# what the server needs -- no dev dependencies, no full node_modules.

FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci


FROM node:22-bookworm-slim AS build
WORKDIR /app

# Inlined into the bundle; see the note at the top.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
# next.config.ts bakes the /api rewrite destination at build time too. The
# browser calls the API host directly, so this rewrite is never used in
# production, but it must not point at localhost: the compose service name is
# the right value.
ARG BACKEND_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID \
    BACKEND_URL=$BACKEND_URL \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


FROM node:22-bookworm-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Not root. The node image ships a `node` user (uid 1000).
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public

USER node
EXPOSE 3000

# Any HTTP answer below 500 means the server is up (the root page may redirect
# to sign-in). start-period covers Node's cold start.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.status<500?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
