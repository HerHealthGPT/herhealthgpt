---
name: herhealth-repo
description: >
  Layout, conventions and constraints of the HerHealthGPT monorepo. Trigger when
  creating files, deciding where code belongs, writing imports across services,
  setting up CI workflows, adding dependencies, or writing commits.
---

# HerHealthGPT monorepo

## Layout

services/frontend/    Next.js responsive web app (NOT a PWA), en / ar / fr
services/backend/     FastAPI: triage agent and gates, retrieval, accounts,
                      cycle data, kept files, evaluation tools
services/data/        ingestion, evidence batches, evaluation cases and scripts
packages/contracts/   Pydantic schemas shared across services
knowledge/            features.yaml conditions.yaml evidence.csv red_flags.yaml
                      sources.yaml weights.yaml actions.yaml
scripts/              serve-models.sh, tunnel-models.sh (GPU server), hygiene
infra/                compose files, envs/*.env, Caddy, deploy/, model/, terraform/
.github/workflows/    path-filtered CI and the deploy

What runs, with versions: docs/ARCHITECTURE.md.

## Import rule

Nothing outside packages/contracts/ may be imported across service boundaries.
Kept by review: no import-linter runs (checked 2026-10-20). A service needing something from another service
means the thing belongs in contracts, or the boundary is wrong.

## CI

Every workflow uses path filters. A frontend change must not rebuild the backend
or the backend. Always add the paths: key when creating a workflow.

## Ownership

There is no CODEOWNERS file (checked 2026-10-20). Ask the owning teammate before
editing outside your area.

## Conventions

- Python 3.12, ruff, mypy strict on packages/contracts/
- Conventional commits, scoped: feat(data): ..., fix(knowledge): ...
- Short branches, under two days
- Prefer boring readable code; this is read by markers, not scaled to millions
