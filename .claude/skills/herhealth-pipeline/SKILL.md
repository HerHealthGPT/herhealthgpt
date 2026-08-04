---
name: herhealth-pipeline
description: >
  How the HerHealthGPT data pipeline is built and run — make targets, the module
  layout under services/data, the evidence batch review gate, and the rules that
  keep it reproducible. Trigger when running or changing any pipeline stage
  (fetch, clean, evidence, validate, tables), when adding a source or a knowledge
  row, when touching services/data/src/herhealth_data/, or when asked to make a
  step reproducible.
---

# The HerHealthGPT data pipeline

## Stages

```
ingest_targets.yaml   what to fetch + per-source guards        tracked
      │  make fetch          (dry run by default; --yes to request)
      ▼
raw/{source}/{date}/  immutable HTML + manifest.jsonl          gitignored
      │  make clean          (needs: uv sync --extra ingest)
      ▼
build/clean/*.json    sectioned, VERBATIM text                 gitignored
      │
      │  humans read this and author batches
      ▼
services/data/evidence_batches/batch_NN_*.yaml                 tracked
      │  make evidence       (approved batches only)
      ▼
knowledge/evidence.csv  GENERATED — never hand-edited          tracked
      │  make validate       (schema + cross-file checks)
      ▼
build/tables/*.csv + knowledge.md   flat views                 gitignored
```

`ingest.lock.jsonl` records url, sha256 and licence for every fetched document.
`raw/` is gitignored, so the lock is the only record of the corpus in git — a
changed hash means upstream guidance moved.

## Non-negotiables

1. **If a step is worth doing twice, it belongs in a module with a make target
   and a test.** No ad-hoc scripts. This is the whole point of the pipeline.
2. **Never hand-edit `knowledge/evidence.csv`.** Every `source_quote` contains
   commas and often nested quotes; one stray character silently changes a
   clinical claim. Edit the batch YAML and run `make evidence`.
3. **Never fetch without asking.** Dry run is the default and network requires
   `--yes`. Tests never hit the network — the transport is injected, so no test
   can reach it even by accident.
4. **Raw content is immutable.** `RawStore.save` refuses to overwrite. A
   re-fetch on a later date makes a new dated snapshot so changes stay diffable.
5. **Licence guards run before the request**, not after. `/ency/` on MedlinePlus
   is barred by path because its terms forbid ingestion into a health IT system.
6. **Builds are deterministic.** Rows sorted, keys ordered — re-running produces
   byte-identical output so a diff only ever shows a real change.

## Module layout

```
services/data/src/herhealth_data/
├── paths.py          every filesystem location, defined once
├── cli.py            argument parsing only
├── commands.py       one function per verb, returns an exit code
├── knowledge.py      load + validate all seven files
├── evidence.py       batch YAML -> evidence.csv
├── tables.py         flat CSV/Markdown exports
└── ingest/
    ├── config.py     what to fetch, licence guards, user agents
    ├── store.py      immutable raw/ layout, manifests, lockfile
    ├── fetch.py      the only socket, plus fetch policy
    └── clean.py      HTML -> sectioned verbatim text (needs bs4)
```

Dependencies point one way: `config` ← `store` ← `fetch`. Three modules, not
six — split by reason to change, not by type.

Exit codes everywhere: `0` did it, `1` ran but the data was wrong, `2` could not
run.

## Adding a source

1. `knowledge/sources.yaml` — id, precedence, licence, `status`. If the licence
   is not satisfiable, **do not add it**; record why in `CLAUDE.md` instead.
2. `services/data/ingest_targets.yaml` — documents, plus any
   `excluded_path_fragments` or `user_agents`, each with the reason written down.
3. `make fetch-plan`, then `make fetch`. Commit targets and lock together.

## Adding evidence rows

Draft a batch, present it as a table, wait for approval, then set
`approved: true` and `reviewed_on`. A batch without `approved: true` is parsed
and validated but contributes nothing — drafting ahead of review is safe by
construction.

Never more than 10 clinical rows without stopping for review.

## Gotchas that have already bitten

- **`certifi` is required.** uv installs a python-build-standalone interpreter
  with no CA bundle; `urllib` fails TLS on every host without it.
- **Unquoted `yes`/`no` in YAML parse as booleans** and fail the string schema.
  Quote them.
- **A colon inside an unquoted YAML scalar breaks the parse.** Use a `>-` block
  for any quote containing one.
- **Do not pipe Python source through shell heredocs.** `\n` gets mangled into
  real newlines and breaks the file. Use the editing tool.
- **CDC blocks honest user agents.** Its WAF allowlists client tokens; the
  configured override leads with `curl/8.0` and keeps our identifier. Never
  impersonate a browser — a test enforces this.
