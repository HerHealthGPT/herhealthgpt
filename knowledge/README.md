# knowledge/

Hand-authored clinical knowledge. Seven files, validated against the Pydantic
schemas in `packages/contracts/` — those schemas are the single definition, not
these files.

This system performs urgency triage and informational guidance. It does not
diagnose, and nothing in this directory may describe it as doing so.

## The three tables that drive reasoning

| File | Holds |
|---|---|
| `features.yaml` | Everything the system may ask about. One row per feature, with its allowed values and an English probe. |
| `conditions.yaml` | Everything the system may suspect. One card per condition, with its baseline action and its supporting sources. |
| `evidence.csv` | The join. One row per `(condition_id, feature_id, value)` saying whether that answer supports or argues against that condition. |

`evidence.csv` is sparse. `neutral` is expressed by omitting the row, never by
writing it.

## The four supporting files

| File | Holds |
|---|---|
| `red_flags.yaml` | Deterministic escalation rules, evaluated before any model call. |
| `sources.yaml` | Every source, with its precedence rank and licence. Lower rank wins on conflict. |
| `weights.yaml` | The numeric value of each of the five evidence strengths, plus the stopping thresholds. Set by us, tuned against the evaluation set. |
| `actions.yaml` | The four action codes and their ordering. |

## Fixed vocabularies

Evidence strength — and nothing else:

    strong_support, weak_support, neutral, argues_against, rules_out

Action codes — and nothing else:

    SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, EMERGENCY

Locale-specific instructions ("call 111", "see your GP") never appear in these
files. Action codes are resolved per locale at response time.

## Provenance is the correctness evidence

Clinician sign-off is out of scope for this project. What stands in for it is the
citation trail: every clinical row carries a `source_id` resolving to a real
fetched document from `sources.yaml`, and a row with no source supporting it is
omitted rather than guessed. Nothing here is clinician-adjudicated, and results
computed from it should say so.

## Language scope

Probe text is English only. The serving model is multilingual and renders
questions at response time. The schema leaves room for authored `fr` / `ar_eg`
probes later; when they land they will be written by a native speaker, never
machine translated.
