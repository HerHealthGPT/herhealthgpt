# syntax=docker/dockerfile:1
#
# The retrieval service: bge-m3 embeddings over the reviewed passage index.
# Build from the REPOSITORY ROOT:
#
#   docker build -f services/model/Dockerfile -t herhealth-retrieval \
#     --build-arg BGE_M3_REVISION=<hf commit sha> \
#     --build-arg INDEX_VERSION=<published index version> .
#
# CPU only. This is the memory-hungry service — bge-m3 sits resident at roughly
# 2 GB — so size the host for this container, not for the other two.
#
# PREREQUISITE: build/index/ is generated, gitignored, and NOT in a fresh clone.
# (There is no `make index` target in the Makefile; the build is
# `python -m herhealth_data.cli index` — see docs/runbooks/aws-deploy.md,
# "The retrieval index".) The COPY below fails with a clear error if it is
# missing, rather than producing an image that starts and then answers nothing.
#
# For any image that leaves a developer machine, build/index must come from a
# published, filtered index (scripts/publish-index.sh): quote-only (NHS) text
# must never be in it. CI pulls exactly that from S3 into build/index.

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
#
# BGE_M3_REVISION pins the weights to one Hugging Face commit. The index's
# vectors are only meaningful against the weights that produced them, so the
# revision here MUST equal the one the index was built with (recorded in the
# index's build-info.json by scripts/publish-index.sh; CI refuses to build on a
# mismatch). It is required when baking: an unpinned "latest" is exactly how the
# two drift apart.
#
# snapshot_download(revision=<sha>) fills the cache but, for a commit hash, does
# not write refs/main, so SentenceTransformer('BAAI/bge-m3') would not find it
# offline. Writing refs/main by hand makes loading by NAME resolve to the pinned
# snapshot, which is what keeps the app's model name (and the index's
# model_name check) unchanged.
#
# ignore_patterns skips the repository's ONNX export and images. A bare
# snapshot_download fetches the WHOLE repo (SentenceTransformer(...) would not),
# which would roughly double the weights layer for files nothing here loads. The
# offline load in the next command is the check: if a file the model needs were
# ever excluded, the build fails here instead of the container failing later.
ARG BAKE_MODEL=1
ARG BGE_M3_REVISION
RUN if [ "$BAKE_MODEL" = "1" ]; then \
      test -n "$BGE_M3_REVISION" || { echo "BGE_M3_REVISION build-arg is required when BAKE_MODEL=1" >&2; exit 1; }; \
      python -c "import os, pathlib; from huggingface_hub import snapshot_download; rev = os.environ['BGE_M3_REVISION']; snap = pathlib.Path(snapshot_download('BAAI/bge-m3', revision=rev, ignore_patterns=['onnx/*', 'imgs/*', '*.jpg', '*.png'])); refs = snap.parents[1] / 'refs'; refs.mkdir(exist_ok=True); (refs / 'main').write_text(rev)" \
      && HF_HUB_OFFLINE=1 python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"; \
    fi

# Provenance, readable with `docker inspect`. INDEX_VERSION is the published
# index (s3://<bucket>/index/<version>/) this image was built from.
ARG INDEX_VERSION=unknown
LABEL org.herhealthgpt.bge-m3-revision="${BGE_M3_REVISION}" \
      org.herhealthgpt.index-version="${INDEX_VERSION}"

EXPOSE 8001

# start-period is long on purpose: loading bge-m3 from disk takes tens of
# seconds, and a shorter grace window marks a healthy container unhealthy
# while it is still doing exactly what it should.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status==200 else 1)"

CMD ["python", "-m", "herhealth_model"]
