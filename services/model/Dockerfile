# syntax=docker/dockerfile:1
#
# The retrieval service: bge-m3 embeddings over the reviewed passage index.
# Build from the REPOSITORY ROOT:
#
#   make index                                     # build/index must exist first
#   docker build -f services/model/Dockerfile -t herhealth-retrieval .
#
# CPU only. This is the memory-hungry service — bge-m3 sits resident at roughly
# 2 GB — so size the host for this container, not for the other two.
#
# PREREQUISITE: build/index/ is generated, gitignored, and NOT in a fresh clone.
# Run `make index` before building, or the COPY below fails with a clear error
# rather than producing an image that starts and then answers nothing.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/contracts/pyproject.toml packages/contracts/
COPY services/data/pyproject.toml services/data/
COPY services/model/pyproject.toml services/model/
COPY services/backend/pyproject.toml services/backend/
RUN mkdir -p packages/contracts/src services/data/src services/model/src services/backend/src

# Both extras: retrieval for the index and embedder, ingest for the guarded web
# fallback, which reuses clean_html/RobotsPolicy rather than reimplementing
# HTML cleaning and robots compliance (ADR 0012 §3).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra retrieval --extra ingest --no-install-workspace

COPY packages/contracts packages/contracts
COPY services/data services/data
COPY services/model services/model

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra retrieval --extra ingest

# Regression guard. This host has no GPU, so a CUDA build of torch (and the
# ~1.5 GB of nvidia-*/triton wheels it drags in) is dead weight in the image and
# in every pull. Fail the build here, loudly, if one ever returns to uv.lock.
RUN /app/.venv/bin/python -c "import sys, torch; sys.exit(1 if torch.version.cuda else 0)" \
 && ! ls /app/.venv/lib/python3.12/site-packages | grep -E '^(nvidia|triton|cuda)' \
 || { echo "ERROR: a CUDA torch or nvidia/triton packages are installed; see [[tool.uv.index]] pytorch-cpu in pyproject.toml" >&2; exit 1; }


FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 herhealth
WORKDIR /app

COPY --from=builder --chown=herhealth:herhealth /app/.venv /app/.venv
COPY --from=builder --chown=herhealth:herhealth /app/packages/contracts packages/contracts
COPY --from=builder --chown=herhealth:herhealth /app/services/data services/data
COPY --from=builder --chown=herhealth:herhealth /app/services/model services/model

# The passage index: vectors.npy, passages.jsonl, manifest.json. ~20 MB.
COPY --chown=herhealth:herhealth build/index build/index

# Maps (source_id, slug) -> url, which is what turns a citation into a link a
# user can open. Tracked in git precisely because raw/ is not.
COPY --chown=herhealth:herhealth services/data/ingest.lock.jsonl services/data/ingest.lock.jsonl

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/herhealth/.cache/huggingface \
    HERHEALTH_INDEX_DIR=/app/build/index \
    HERHEALTH_INGEST_LOCK=/app/services/data/ingest.lock.jsonl \
    HERHEALTH_HOST=0.0.0.0 \
    HERHEALTH_PORT=8001

USER herhealth

# Bake the weights (~2.3 GB) so the container does not download a model the
# first time someone asks a question. Set BAKE_MODEL=0 to build a small image
# and mount a warm HF cache at /home/herhealth/.cache/huggingface instead —
# the only sane option on a metered or air-gapped builder.
ARG BAKE_MODEL=1
RUN if [ "$BAKE_MODEL" = "1" ]; then \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"; \
    fi

EXPOSE 8001

# start-period is long on purpose: loading bge-m3 from disk takes tens of
# seconds, and a shorter grace window marks a healthy container unhealthy
# while it is still doing exactly what it should.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "herhealth_model"]
