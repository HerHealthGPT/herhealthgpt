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
.PHONY: help install install-ingest lock sync-check fetch fetch-plan clean evidence tables icd verify-quotes validate build eval lint fmt test clean-build

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
	@echo "build      fetch -> clean -> chunk -> build/passages.parquet (phase 4)"
	@echo "eval       run the triage controller over the benchmark cases (phase 3)"
	@echo "lint       ruff check + mypy strict on packages/contracts"
	@echo "test       pytest"

install:
	$(UV) sync

install-ingest:
	$(UV) sync --extra ingest

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

build:
	$(UV) run python -m herhealth_data.cli build --knowledge $(KNOWLEDGE_DIR)

eval:
	$(UV) run python -m herhealth_data.cli eval --knowledge $(KNOWLEDGE_DIR) --cases $(CASES_DIR)

lint:
	$(UV) run ruff check packages/contracts services/data
	$(UV) run mypy --config-file packages/contracts/pyproject.toml packages/contracts/src

fmt:
	$(UV) run ruff format packages/contracts services/data
	$(UV) run ruff check --fix packages/contracts services/data

test:
	$(UV) run pytest packages/contracts/tests services/data/tests -q

clean-build:
	rm -rf build/
