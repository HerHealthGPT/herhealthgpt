# Code guide

Every module in the repository, what it is responsible for, and why it is shaped
that way. Read [`CLAUDE.md`](CLAUDE.md) first for *what* the system does; this
document covers *how the code is arranged*.

**Status:** Phase 1. `packages/contracts` and `services/data` exist.
`services/backend`, `services/frontend` and `services/model` do not yet.

---

## Contents

- [The pipeline](#the-pipeline)
- [Module map](#module-map)
- [`packages/contracts`](#packagescontracts)
- [`services/data`](#servicesdata)
  - [`paths.py`](#pathspy)
  - [`ingest/config.py`](#ingestconfigpy)
  - [`ingest/store.py`](#ingeststorepy)
  - [`ingest/fetch.py`](#ingestfetchpy)
  - [`commands.py`](#commandspy)
  - [`cli.py`](#clipy)
- [`knowledge/`](#knowledge)
- [Invariants, and where each is enforced](#invariants-and-where-each-is-enforced)
- [Testing strategy](#testing-strategy)
- [How to extend](#how-to-extend)
- [Design rules used throughout](#design-rules-used-throughout)

---

## The pipeline

```
ingest_targets.yaml          what to fetch, and the rules
        │
        ▼
   make fetch  ─────────────▶  raw/{source}/{date}/*.html      (immutable, gitignored)
        │                      raw/{source}/{date}/manifest.jsonl
        │                      services/data/ingest.lock.jsonl (tracked)
        ▼
   make clean  ─────────────▶  build/clean/*.json              (phase 4, not built)
        │                      sectioned text, boilerplate stripped
        ▼
   make build  ─────────────▶  build/passages.parquet          (phase 4, not built)
        │                      build/conflicts.jsonl
        ▼
   make validate ───────────▶  knowledge/ checked against the schemas
        │
        ▼
   make eval   ─────────────▶  benchmark metrics               (phase 3, not built)
```

Only `fetch` and `validate` exist today. `build` and `eval` are honest stubs that
exit `2` naming the phase that implements them — they never succeed vacuously.

**Why the odd order.** Knowledge is hand-authored and evaluated on three
conditions *before* the corpus is built. If elimination does not work at three
conditions, ten thousand passages will not fix it.

---

## Module map

Eight Python files in `services/data`. Dependencies point downward only.

```
   cli.py            argument parsing only — a table of contents
      │
      ▼
   commands.py       one function per verb, returning an exit code
      │
      ▼
   ingest/           public API via __init__
      │
      ├── fetch.py   the network, and the policy deciding what to request
      │      │
      │      ▼
      ├── store.py   where documents go: raw/ layout, manifests, lockfile
      │      │
      │      ▼
      └── config.py  what to fetch, and the per-source rules

   paths.py          imported by anything, imports nothing
```

`config.py` and `paths.py` are leaves — they import nothing from the package,
which keeps the graph acyclic.

**Three ingest modules, not six.** An earlier version split records, transport
and the lockfile into their own files; that was more files than the problem
needs. The split that survives is by *reason to change*: what to fetch
(`config`), where it lands (`store`), how it is fetched (`fetch`).

---

## `packages/contracts`

The shared schema package. **Nothing outside it may be imported across a service
boundary.** Both `services/data` and (later) `services/backend` depend on it, and
neither depends on the other.

`mypy --strict` runs here and nowhere else, because these types are the single
definition every other service validates against.

### [`knowledge.py`](packages/contracts/src/herhealth_contracts/knowledge.py)

Pydantic models for all seven knowledge files. **The schemas are the definition;
the YAML and CSV conform to them, not the other way round.**

Every model inherits `_KnowledgeModel`, which sets:

| Config | Why |
|---|---|
| `extra="forbid"` | A typo'd column in a hand-edited CSV becomes a load failure, not a silently dropped field |
| `frozen=True` | The knowledge base is read-only once loaded |
| `str_strip_whitespace=True` | Whitespace cannot masquerade as content |

#### Fixed vocabularies

| Type | Values |
|---|---|
| `EvidenceStrength` | `strong_support`, `weak_support`, `neutral`, `argues_against`, `rules_out` |
| `ActionCode` | `SELF_CARE`, `ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`, `EMERGENCY` |
| `FeatureKind` | `boolean`, `categorical`, `ordinal`, `numeric` |
| `SourceStatus` | `available`, `citable_only`, `restricted` |
| `ComparisonOp` | `equals`, `not_equals`, `in`, `gte`, `lte` |

These are `StrEnum`, so an invalid value is a **load-time failure**, not a
validation rule someone can forget to run.

#### Models

| Model | File | Notes |
|---|---|---|
| `Feature` | `features.yaml` | `probe` is `dict[str, str]` keyed by language; only `en` required. That mapping shape is what lets `fr`/`ar_eg` land later **without a migration** |
| `Condition` | `conditions.yaml` | `icd11` defaults to `TODO_VERIFY`; `source_ids` has `min_length=2` |
| `EvidenceRow` | `evidence.csv` | Rejects `neutral`; requires non-empty `source_quote` |
| `RedFlagRule` | `red_flags.yaml` | `action` restricted to escalating codes; requires `source_quote` |
| `Clause` | (inside a rule) | Conjunction only — an "or" is two rules, so each stays traceable to its own quote |
| `Source` | `sources.yaml` | `status` has **no default**; exposes `may_be_cited` / `may_be_ingested` |
| `Weights` | `weights.yaml` | Enforces monotonic scale and the `SELF_CARE` bar |
| `Actions` | `actions.yaml` | All four codes, strictly increasing severity |
| `KnowledgeBase` | all of them | Container; rejects duplicate `(condition, feature, value)` cells |

#### Two permissions, not one

`Source` distinguishes quoting from redistributing, because a licence may grant
one and not the other:

```python
source.may_be_cited     # status is not restricted  → may appear in source_quote
source.may_be_ingested  # status is available       → may enter passages.parquet
```

That split is what lets NHS content back a red-flag rule (its "when to get help"
sections are the best escalation language available) while staying out of the
corpus.

---

## `services/data`

Offline. Runs in CI and by hand; never deployed.

### [`paths.py`](services/data/src/herhealth_data/paths.py)

Canonical filesystem locations, defined once. Every other module imports from
here rather than recomputing paths relative to `__file__`. When the layout
changes, this is the only file that needs to know.

| Constant | Tracked? |
|---|---|
| `KNOWLEDGE_DIR` | yes |
| `INGEST_TARGETS_FILE` | yes |
| `INGEST_LOCK_FILE` | yes |
| `CASES_DIR` | yes |
| `RAW_DIR`, `BUILD_DIR` | **no** — gitignored, reproducible |

---

### `ingest`

Import from the package, not its modules — the internal split may change, the
public names will not:

```python
from herhealth_data.ingest import RawStore, fetch_all, load_plan
```

#### [`ingest/config.py`](services/data/src/herhealth_data/ingest/config.py)

What to fetch and the per-source rules, loaded from the tracked
[`ingest_targets.yaml`](services/data/ingest_targets.yaml).

Two rule kinds, both existing because *a rule that lives only in someone's memory
eventually gets broken*:

**Licence guards** — path fragments never requested from a source:

```yaml
excluded_path_fragments:
  medlineplus:
    - /ency/      # A.D.A.M. encyclopedia; its terms bar ingestion into a
                  # "health IT system", which names systems like this one
```

**User agents** — overrides for sources whose edge rejects the default:

```yaml
user_agents:
  cdc: curl/8.0 HerHealthGPT-research/0.1 (academic capstone)
```

CDC's WAF returns 403 to an honest project agent, an empty one, no header at
all, *and* a full browser string; it allowlists client tokens. We lead with the
accepted token and keep our identifier after it, so requests stay attributable.
**A test asserts no configured agent contains `Mozilla`, `Chrome`, `Safari`,
`Firefox`, `AppleWebKit` or `Edg/`** — we work around a WAF, we do not
impersonate.

`load_plan` raises `DuplicateTargetError` if two targets would write to the same
file, since one would silently be lost.

#### [`ingest/store.py`](services/data/src/herhealth_data/ingest/store.py)

Where documents go and what we record about them: the raw layout, provenance
records, manifests, and the tracked lockfile.

**Provenance.** `FetchOutcome` — what happened to one target:

| Outcome | Meaning |
|---|---|
| `fetched` | Retrieved and written for the first time |
| `already_present` | File existed; raw content is immutable, so it was left alone |
| `excluded` | Refused by a licence guard, **before any request** |
| `failed` | Not a usable 200. Nothing written |
| `planned` | Dry run — nothing requested |

`FetchRecord` carries the four fields the protocol requires on every record:
`url`, `fetched_at`, `content_hash`, `licence`. Frozen; `.with_()` returns a
modified copy; `.to_json()` drops `None` so optional fields are *absent* rather
than null.

**The store.** `raw/{source_id}/{YYYY-MM-DD}/{slug}.html`.

**The only module that writes to `raw/`, and the only one that knows the
layout.** The clean stage reads through `RawStore.documents()` rather than
globbing, so if the layout changes, one class changes with it.

A store is **bound to a single date at construction**. That makes "write today's
snapshot" and "read yesterday's" two different objects rather than two different
arguments, and removes any way to write into a past snapshot by accident.

```python
store = RawStore(paths.RAW_DIR, "2026-08-03")
store.has(target)          # already fetched?
store.read(target)         # bytes
store.save(target, body)   # raises FileExistsError rather than overwrite
store.documents()          # every StoredDocument in this snapshot, sorted
store.write_manifests(records)
```

`save()` refusing to overwrite is the backstop for when a caller forgets to check
`has()` — immutability enforced, not assumed.

**The lockfile.** `services/data/ingest.lock.jsonl` — **to source content what
`uv.lock` is to dependencies.**

`raw/` is gitignored, so this is the only evidence in version control of which
documents the knowledge base was built from. The point is **drift detection**: a
changed `content_hash` on a later fetch means upstream guidance moved, and that
should appear in a diff rather than silently altering the evidence under a set of
clinical rows.

Rows are sorted by `(source_id, slug)` and keys are ordered, so diffs stay
readable. Only usable records appear — an excluded or failed document has no
bytes, so listing it would imply content that does not exist.

#### [`ingest/fetch.py`](services/data/src/herhealth_data/ingest/fetch.py)

The network, and the policy deciding what to request.

`http_get` is **the only function in the package that opens a socket**:

```python
Transport = Callable[[str, str], tuple[int, bytes]]   # (url, user_agent) -> (status, body)
```

Every consumer takes a `Transport` argument rather than calling `http_get`
directly. That indirection is why *"tests never hit the network"* is a
**structural property** rather than a rule people must remember — no test
supplies the real one.

Two things worth knowing:

- **`certifi` is required, not optional.** uv installs a
  python-build-standalone interpreter with no CA bundle, so `urllib` fails
  certificate verification against every host without it. Verification is never
  disabled.
- **HTTP error statuses are returned, not raised.** A 404 is data the caller
  records. Only transport-level failure — DNS, TLS, refused — raises.

The order of checks in `fetch_all` *is* the policy:

1. **Licence guard** — before anything else, before any network call. A barred
   URL is never requested, so a licence rule cannot be violated by a retry, a
   redirect, or a bug further down. It even precedes the immutability check.
2. **Already present** — immutable, so leave it and report it.
3. **Dry run** — the default. Nothing is requested unless the caller opts in.
4. **Fetch** — and only a real 200 with a body is written, so a 404 error page
   can never sit in `raw/` masquerading as content.

Returns one record per target **including refused and failed ones**, because a
report that omits them is a report that hides them.

---

### [`commands.py`](services/data/src/herhealth_data/commands.py)

One function per CLI verb. Kept out of `cli.py` so parsing and behaviour are
separately testable; kept in *one* module because four small functions do not
need four files.

| Function | State |
|---|---|
| `run_fetch` | implemented |
| `run_validate` | stub that says plainly it verified nothing |
| `run_build` | phase 4 |
| `run_eval` | phase 3 |

**Exit codes, consistent across every command:**

```
0   did what was asked
1   ran, but something in the data was wrong
2   could not run — bad arguments, missing input, not implemented
```

`validate` currently prints a loud `WARNING: these files were NOT validated`
rather than exiting 0 quietly. A validation step that silently approves
everything is worse than no validation step at all.

### [`cli.py`](services/data/src/herhealth_data/cli.py)

Argument parsing only — a table of contents. Every default comes from `paths`.

---

## `knowledge/`

Seven hand-authored files. See [`knowledge/README.md`](knowledge/README.md) for
the data model and [`CLAUDE.md`](CLAUDE.md) for the authoring rules.

| File | Status |
|---|---|
| `weights.yaml` | authored — every number chosen by us, marked as such |
| `actions.yaml` | authored |
| `sources.yaml` | authored — 4 usable sources; unusable ones removed, not listed |
| `features.yaml` | authored — 26 features |
| `conditions.yaml` | **not yet** — needs source text |
| `evidence.csv` | **not yet** — needs source text |
| `red_flags.yaml` | **not yet** — needs source text |

The last three are gated on the verification protocol: every row needs a
verbatim `source_quote`, so they cannot be written from memory.

---

## Invariants, and where each is enforced

The point of this table: **none of these rules relies on anyone remembering
them.**

| Invariant | Enforced by | Test |
|---|---|---|
| Tests never hit the network | `Transport` injection — no test supplies the real one | structural |
| Raw content is immutable | `RawStore.save` raises `FileExistsError` | `test_store.py` |
| A licence guard cannot be bypassed | Checked before the request, and before the immutability check | `test_fetch.py` |
| No browser impersonation | Assertion over the real config | `test_config.py` |
| A 404 never becomes a document | Only a 200 with a body is written | `test_fetch.py` |
| `neutral` never appears in `evidence.csv` | Rejected on `EvidenceRow` | `test_knowledge.py` |
| Red flags cannot de-escalate | `action` restricted to escalating codes | `test_knowledge.py` |
| `SELF_CARE` bar strictly higher | `Weights` model validator | `test_knowledge.py` |
| Evidence scale stays monotonic | `Weights` model validator | `test_knowledge.py` |
| No condition rests on one document | `source_ids` `min_length=2` | `test_knowledge.py` |
| ICD codes never written from memory | Defaults to `TODO_VERIFY` | `test_knowledge.py` |
| No clinician-review field exists | Assertion over model fields + `extra="forbid"` | `test_knowledge.py` |
| Two targets cannot overwrite each other | `DuplicateTargetError` | `test_config.py` |
| Upstream drift is visible | `content_hash` in the tracked lockfile | `test_store.py` |

---

## Testing strategy

**110 tests. None touch the network. None need fixtures on disk.**

One test file per module.

| File | Covers |
|---|---|
| `packages/contracts/tests/test_knowledge.py` | Schemas, weighted toward safety invariants |
| `services/data/tests/conftest.py` | Shared factories and fake transports |
| `services/data/tests/test_config.py` | Guards, agents, loading, the real config |
| `services/data/tests/test_store.py` | Layout, immutability, manifests, lockfile |
| `services/data/tests/test_fetch.py` | The four policy checks, in order |
| `services/data/tests/test_cli.py` | Parsing and wiring |

Three conventions:

- **Test names state the claim**, not the mechanism —
  `test_barred_url_is_never_requested`, not `test_excluded_returns_excluded`.
- **Negative tests use an exploding transport.** `forbidden()` raises if called,
  so a guard test cannot pass for the wrong reason.
- **Some tests assert against the real tracked config**, not fixtures — so
  `ingest_targets.yaml` cannot drift into an unsafe state unnoticed.

---

## How to extend

### Add a source

1. Add it to [`knowledge/sources.yaml`](knowledge/sources.yaml) with `precedence`
   and `status`. If the licence is not satisfiable, **do not add it** — record
   the reason in `CLAUDE.md` instead.
2. Add its documents to
   [`ingest_targets.yaml`](services/data/ingest_targets.yaml), plus any
   `excluded_path_fragments` or `user_agents` it needs, with the reason written
   down.
3. `make fetch-plan` to check the plan, then `make fetch`.
4. Commit `ingest_targets.yaml` **and** `ingest.lock.jsonl` together.

### Add a feature

Add to [`knowledge/features.yaml`](knowledge/features.yaml). A feature is a
*question*, not a claim, so it needs no `source_quote`. Values must be lowercase
tokens; never list `unknown` (it is implicit and carries no weight); quote
`"yes"` and `"no"` or YAML will parse them as booleans.

A feature with no evidence rows and no red-flag clause is dead weight — delete
it rather than keep asking a question nobody can use.

### Add a CLI command

New module in `commands/` exposing `run(args) -> int`, then a subparser in
`cli.py`. Use the standard exit codes.

### Change a dependency

Edit the right `pyproject.toml`, run `make lock`, and commit both files in the
same commit. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Design rules used throughout

**Make the rule structural, not remembered.** Wherever a protocol rule could be
enforced by a type, a signature, or a raise, it is. The network is behind an
injected callable; the store refuses to overwrite; the schema refuses a
`SELF_CARE` bar below the routine bar.

**Fail loudly rather than pass quietly.** `extra="forbid"`, non-zero exits for
unimplemented commands, a `WARNING` from a validator that has not been wired up.
A step that silently approves everything is worse than no step.

**One module, one reason to change — but no more modules than that needs.**
`store.py` is the only place that knows the `raw/` layout; `paths.py` the only
place that knows where anything lives; `fetch.py` the only place that opens a
socket. Three modules, not six: splitting further produced files too small to
justify the navigation cost.

**Inject the awkward dependency.** Anything slow, networked, or non-deterministic
is passed in. That is what makes the test suite offline and fast.

**Write down the reason, not just the rule.** Every guard in
`ingest_targets.yaml` carries the licence clause or the observed behaviour that
motivated it. In six months the rule will look arbitrary without it.

**Boring and readable over clever.** This is read by markers, not scaled to
millions of requests.
