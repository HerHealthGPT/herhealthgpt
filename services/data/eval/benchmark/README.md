# The benchmark, as it arrived

Put the original 540-case-per-language benchmark here, **exactly as it came out
of the earlier evaluation**. Do not edit it, reformat it, or fix anything in it.
Any format is fine — CSV, JSON, JSONL, XLSX, one file or several.

Tracked in git, and immutable once added. If a corrected version arrives later
it lands beside this one under a new name; the old file is never overwritten,
so a result computed last month can still be reproduced.

## Why this is separate from `../cases/`

Same pattern as `evidence_batches/` → `knowledge/evidence.csv`:

```
eval/benchmark/    the source, as authored elsewhere       (tracked, immutable)
       │
       ▼  make eval-cases
eval/cases/        our schema, one row per case            (tracked, generated)
       │
       ▼  make eval
build/eval/        metrics                                 (gitignored)
```

Keeping the original means the conversion is reviewable — if a label looks
wrong in `cases/`, the sentence it came from is still here to check against.
Converting in place would destroy that, exactly as hand-editing `evidence.csv`
would destroy the batch trail.

## What the converter will need to know

Answer these in a `SOURCE.md` next to the file, or tell me and I will write it:

1. **Where it came from** — which run, when, and what produced it. If it derives
   from a public dataset, name the dataset and its licence; that has the same
   provenance requirements as anything in `sources.yaml`.
2. **The label vocabulary** — the exact risk-level values, and whether there is
   also a recommended-action label and what its values are.
3. **How languages are tied together** — the column holding `canonical_case_id`,
   or whatever plays that role.

Point 3 matters most. Risk labels are derived **once** from the English source
text and propagated by `canonical_case_id`. Running English keyword rules over
translated text is what produced language-asymmetric labels skewed toward
routine last time, and the converter has to be able to prove it did not.

## Not clinician-adjudicated

These are silver annotations. Say so wherever results are reported.
