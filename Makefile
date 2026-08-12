# HerHealthGPT — repo-level task runner.
#
# Lives at the root rather than in services/data/ because knowledge/ is a
# root-level directory and these targets need to reach it without ../../ paths.
#
# Every target runs through `uv run`, which syncs the environment from uv.lock
# before executing. You never need to activate a virtualenv, and you cannot
# accidentally run against a stale one. `make` is not installed by default on
# Windows — each recipe below is a single command you can also run by hand.

UV ?= uv
KNOWLEDGE_DIR ?= knowledge
CASES_DIR ?= services/data/eval/cases

.DEFAULT_GOAL := help
.PHONY: help install install-ingest install-api lock sync-check fetch fetch-plan clean evidence tables icd verify-quotes validate thresholds build eval triage triage-all lint fmt test test-api db-up db-down migrate serve clean-build

# A demonstration case for `make triage`. Override to run another:
#   make triage CASE=services/backend/cases/says_nothing.yaml
CASE ?= services/backend/cases/heavy_periods_over_40.yaml

help:
	@echo "install    create .venv and install everything from uv.lock"
	@echo "lock       re-resolve uv.lock after changing a dependency"
	@echo "sync-check fail if uv.lock has drifted from the pyproject files"
	@echo "fetch-plan show what would be fetched, without making any request"
	@echo "fetch      fetch source documents into raw/ (makes network requests)"
	@echo "clean      turn fetched HTML into sectioned, quotable text"
	@echo "evidence   regenerate knowledge/evidence.csv from reviewed batches"
	@echo "tables     render the knowledge base as CSV + Markdown tables"
	@echo "icd        propose ICD-11 codes (needs WHO_ICD_* in infra/envs/data.env)"
	@echo "verify-quotes  check every source_quote against its cited source"
	@echo "validate   check knowledge/ against the contracts schemas"
	@echo "thresholds show where each tunable number sits, and whether it is fragile"
	@echo "build      fetch -> clean -> chunk -> build/passages.parquet (phase 4)"
	@echo "eval       run the benchmark cases through the triage controller"
	@echo "triage     run one scripted consultation and print the trace (CASE=...)"
	@echo "triage-all run every demonstration case in services/backend/cases/"
	@echo "lint       ruff check + mypy strict on packages/contracts"
	@echo "test       pytest (fast, offline: contracts, data, triage core)"
	@echo "test-api   backend app tests — starts PostgreSQL in Docker (needs the api extra)"
	@echo "db-up      start the local dev PostgreSQL (infra/compose.yml)"
	@echo "migrate    apply migrations to the database in infra/envs/backend.env"
	@echo "serve      run the backend API against that database (uvicorn --reload)"

install:
	$(UV) sync

install-ingest:
	$(UV) sync --extra ingest

install-api:
	$(UV) sync --extra api

lock:
	$(UV) lock

sync-check:
	$(UV) sync --locked

# Dry run. Prints the plan and touches nothing.
fetch-plan:
	$(UV) run python -m herhealth_data.cli fetch

# Makes real network requests. Existing files are never overwritten, so this is
# safe to re-run; a re-fetch on a later date lands in a new dated directory.
fetch:
	$(UV) run python -m herhealth_data.cli fetch --yes

# Needs the ingest extra: make install-ingest
clean:
	$(UV) run --extra ingest python -m herhealth_data.cli clean

# evidence.csv is generated, never hand-edited. Edit the batch YAML instead.
evidence:
	$(UV) run python -m herhealth_data.cli evidence

# Flat views of every knowledge file. Generated; nothing reads them back.
tables:
	$(UV) run python -m herhealth_data.cli tables

# Reads credentials from infra/envs/data.env. Proposes only; --apply to write.
icd:
	set -a; . ./infra/envs/data.env; set +a; $(UV) run python -m herhealth_data.cli icd

# Needs build/clean, so run after `make clean`. This is the check that makes
# the verification protocol real: it confirms each quote exists in its source.
verify-quotes:
	$(UV) run python -m herhealth_data.cli verify-quotes

validate:
	$(UV) run python -m herhealth_data.cli validate --knowledge $(KNOWLEDGE_DIR)

# Where each tunable threshold sits among the scores the evidence can actually
# reach. Exits 1 if one is fragile — enforcing its requirement by accident
# rather than by decision. Not in CI: that is a design debt, not a build break.
thresholds:
	$(UV) run python -m herhealth_data.cli thresholds --knowledge $(KNOWLEDGE_DIR)

build:
	$(UV) run python -m herhealth_data.cli build --knowledge $(KNOWLEDGE_DIR)

# Runs the benchmark cases through the controller. No model, no network.
# Exits 1 if a gated metric fails, so CI can depend on it.
eval:
	$(UV) run herhealth-eval --knowledge $(KNOWLEDGE_DIR) --cases $(CASES_DIR)

# Run one scripted consultation and print the whole trace. No model, no network,
# no server — the same case gives the same trace on any machine.
triage:
	HERHEALTH_KNOWLEDGE_DIR=$(KNOWLEDGE_DIR) $(UV) run herhealth-triage --case $(CASE)

triage-all:
	@for case in services/backend/cases/*.yaml; do \
		HERHEALTH_KNOWLEDGE_DIR=$(KNOWLEDGE_DIR) $(UV) run herhealth-triage --case $$case || true; \
	done

lint:
	$(UV) run ruff check packages/contracts services/data services/backend
	$(UV) run mypy --config-file packages/contracts/pyproject.toml packages/contracts/src

fmt:
	$(UV) run ruff format packages/contracts services/data services/backend
	$(UV) run ruff check --fix packages/contracts services/data services/backend

# --extra ingest because the clean-step tests import BeautifulSoup. `make
# validate` deliberately works WITHOUT the extra; the test suite does not, and
# CI must install it or test_clean.py fails at collection.
#
# tests/app is excluded here: it needs the api extra and a real PostgreSQL in
# Docker. That suite is `make test-api`. Everything left runs offline with no
# server and no database, which is the property the triage core must keep.
test:
	$(UV) run --extra ingest pytest packages/contracts/tests services/data/tests services/backend/tests --ignore=services/backend/tests/app -q

# The backend's HTTP and database tests. Starts PostgreSQL in a container via
# testcontainers, so Docker must be running. No AWS account, no credentials.
test-api:
	$(UV) run --extra api pytest services/backend/tests/app -q

# Local dev loop: a real PostgreSQL to run the service against by hand. The test
# suite ignores all of this and starts its own container.
db-up:
	docker compose -f infra/compose.yml up -d postgres

db-down:
	docker compose -f infra/compose.yml down

# Applies migrations to HERHEALTH_DATABASE_URL (read from infra/envs/backend.env).
# Run from services/backend so Alembic finds alembic.ini and migrations/.
migrate:
	set -a; . ./infra/envs/backend.env; set +a; cd services/backend && $(UV) run --extra api alembic upgrade head

# Serves the API on 127.0.0.1:8000. Point Postman at http://localhost:8000/health.
# Uses the package entry point (not the uvicorn CLI) so Windows gets a
# psycopg-compatible event loop.
serve:
	set -a; . ./infra/envs/backend.env; set +a; $(UV) run --extra api python -m herhealth_backend.app

clean-build:
	rm -rf build/
