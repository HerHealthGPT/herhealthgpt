# syntax=docker/dockerfile:1
#
# The FastAPI backend. Build from the REPOSITORY ROOT, not this directory:
#
#   docker build -f services/backend/Dockerfile -t herhealth-backend .
#
# The root is the build context because this is a uv workspace: herhealth-backend
# depends on herhealth-contracts by path (`[tool.uv.sources] workspace = true`),
# and uv resolves every workspace member from the lockfile, so all three member
# manifests must exist even though only two are installed here.
#
# No model weights load in this process — embedding and reranking are HTTP
# calls to vLLM. That is an architectural rule, and it is why this image is
# small and needs no GPU.

FROM python:3.12-slim AS builder

# Pinned, and copied from the official image rather than curl|sh so the build
# is reproducible and fetches no script at build time.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Manifests and the lockfile first. Source changes below this line then reuse
# the resolved dependency layer instead of re-resolving on every commit.
COPY pyproject.toml uv.lock ./
COPY packages/contracts/pyproject.toml packages/contracts/
COPY services/data/pyproject.toml services/data/
COPY services/backend/pyproject.toml services/backend/

# Workspace members must exist as directories for the lock to resolve, but the
# two this image never imports contribute nothing beyond their manifest.
RUN mkdir -p packages/contracts/src services/data/src services/backend/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra api --no-install-workspace

COPY packages/contracts packages/contracts
COPY services/backend services/backend

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra api

# Import the app here so a dependency missing from the api extra fails the
# image build, not the migration step on the server (which is how the missing
# `requests` for google-auth was first found). Importing it has no side effects.
RUN /app/.venv/bin/python -c "import herhealth_backend.app"


FROM python:3.12-slim AS runtime

# Not root. The knowledge base is read-only; the one thing written is files
# she chooses to keep (ADR 0020), into /data/uploads. The directory is made
# here and owned by the app user, so the named volume compose.prod.yml mounts
# over it starts out writable by that user.
RUN useradd --create-home --uid 10001 herhealth \
    && mkdir -p /data/uploads \
    && chown herhealth:herhealth /data/uploads

WORKDIR /app

COPY --from=builder --chown=herhealth:herhealth /app/.venv /app/.venv
COPY --from=builder --chown=herhealth:herhealth /app/packages/contracts packages/contracts
COPY --from=builder --chown=herhealth:herhealth /app/services/backend services/backend

# The seven knowledge files. Read at start-up and injected into every turn, so
# they are part of the image rather than a mount: an image and the rules it
# enforces should not be able to drift apart.
COPY --chown=herhealth:herhealth knowledge knowledge
# The retrieval index, built on the campus box with `make index` (it needs the
# embedding server) and never committed. The deploy workflow downloads it from
# a GitHub release into build/index before this build; for a local build, run
# `make index` first. The backend refuses an index that holds quote-only text
# or was built with a different embedding model.
COPY --chown=herhealth:herhealth build/index index

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HERHEALTH_KNOWLEDGE_DIR=/app/knowledge \
    HERHEALTH_INDEX_DIR=/app/index \
    # 127.0.0.1 is the entry point's default and is correct on a dev box; in a
    # container it would make the port unreachable from anywhere else.
    HERHEALTH_HOST=0.0.0.0 \
    HERHEALTH_PORT=8000

USER herhealth
EXPOSE 8000

# Every other value — database URL, session secret, OpenRouter key, CORS
# origins, HERHEALTH_REASONING_TIMEOUT — is supplied at run time. Nothing
# secret is baked in.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "herhealth_backend.app"]
