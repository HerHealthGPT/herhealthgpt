---
name: herhealth-repo
description: >
  Layout, conventions and constraints of the HerHealthGPT monorepo. Trigger when
  creating files, deciding where code belongs, writing imports across services,
  setting up CI workflows, adding dependencies, or writing commits.
---

# HerHealthGPT monorepo

## Layout

services/frontend/    Next.js PWA
services/backend/     FastAPI: triage, tracker, retrieval, safety, orchestration
services/data/        ingestion, evaluation harness, benchmark cases
packages/contracts/   Pydantic schemas, error codes, safety policy
packages/types-ts/    TypeScript types generated from OpenAPI
knowledge/            features.yaml conditions.yaml evidence.csv red_flags.yaml
                      sources.yaml weights.yaml actions.yaml
infra/                compose.yml, envs/*.env, Caddy, Prometheus
.github/workflows/    path-filtered CI

## Import rule

Nothing outside packages/contracts/ may be imported across service boundaries.
Enforced by import-linter in CI. A service needing something from another service
means the thing belongs in contracts, or the boundary is wrong.

## CI

Every workflow uses path filters. A frontend change must not rebuild the model
image. Always add the paths: key when creating a workflow.

## Ownership

CODEOWNERS per folder, not per repo. Check it before editing outside your area.

## Conventions

- Python 3.12, ruff, mypy strict on packages/contracts/
- Conventional commits, scoped: feat(data): ..., fix(knowledge): ...
- Short branches, under two days
- Prefer boring readable code; this is read by markers, not scaled to millions
