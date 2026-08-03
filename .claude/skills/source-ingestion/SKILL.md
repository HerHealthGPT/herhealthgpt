---
name: source-ingestion
description: >
  Rules for fetching, cleaning and chunking clinical content from external
  sources. Trigger when writing source clients, scrapers, API wrappers, cleaning
  code, chunkers, or anything touching services/data/src/ingest or raw/.
---

# Source ingestion rules

## Provenance is mandatory

Raw fetched content is immutable. Write to raw/{source}/{YYYY-MM-DD}/ and never
overwrite. Re-fetching creates a new dated version so changes are diffable.
Every record stores url, fetched_at, content_hash and licence.

## Never fetch without asking

Confirm before any network call. Cache aggressively. Tests never hit the network.

## Source precedence (lower number wins on conflict)

1 NICE Clinical Knowledge Summaries
2 NHS Website Content API v2
3 NICHD / MedlinePlus
4 CDC
5 RCOG / ACOG

When two sources disagree on urgency, the higher-precedence source wins AND the
conflict is appended to build/conflicts.jsonl. Never resolve silently.

## Extract escalation criteria first

The "when to get help", "ask for an urgent appointment" and "call 999" sections
are clinician-authored escalation criteria and are the most valuable text in any
source. Extract them before anything else; they become red_flags.yaml.

## Cleaning

Strip navigation, cookie banners, feedback widgets, related links, breadcrumbs.
Segment by heading and set section_type: symptoms, causes, when_to_get_help,
treatment, diagnosis, other. Replace locale-specific service references with
action codes.

## Licensing

Record licence per source. NHS content has attribution and reuse conditions.
For UMLS store concept identifiers only, never the strings. Repo stays private.
