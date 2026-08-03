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
.PHONY: help install lock sync-check validate build eval lint fmt test clean

help:
	@echo "install    create .venv and install everything from uv.lock"
	@echo "lock       re-resolve uv.lock after changing a dependency"
	@echo "sync-check fail if uv.lock has drifted from the pyproject files"
	@echo "validate   check knowledge/ against the contracts schemas"
	@echo "build      fetch -> clean -> chunk -> build/passages.parquet (phase 4)"
	@echo "eval       run the triage controller over the benchmark cases (phase 3)"
	@echo "lint       ruff check + mypy strict on packages/contracts"
	@echo "test       pytest"

install:
	$(UV) sync

lock:
	$(UV) lock

sync-check:
	$(UV) sync --locked

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
	$(UV) run pytest services/data/tests -q

clean:
	rm -rf build/
