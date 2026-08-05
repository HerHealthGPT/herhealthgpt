# Benchmark cases

Generated from `../benchmark/` by annotation, reviewed in batches, and
version-controlled — a change to an evidence row that shifts a case outcome
should show up in the same diff as the row.

Run them with `make eval`.

## The format

One file per reviewed batch, `batch_NN.yaml`. Several files rather than one so
each batch stays reviewable on its own, the same reason evidence rows are
authored in batches.

```yaml
cases:
  - id: heavy_prolonged_bleeding_over_40
    topic: Menstrual Flow
    features:                       # what she said, as feature values
      bleeding_heaviness: heavy
      period_duration: over_7_days
      age_band: 40_to_44
    label:
      expected_action: ROUTINE_APPOINTMENT
      needs_clarification: false
      expected_red_flag_id: ""      # set only when a specific rule must fire
      label_quote: >-
        The sentence in the benchmark's reference answer this was read from.

variants:                           # phrasings; NO labels, deliberately
  - canonical_case_id: heavy_prolonged_bleeding_over_40
    style: canonical
    language: en
    text: My periods have been really heavy and long since I turned 41.
```

Quote `yes` and `no`. YAML parses them as booleans; the loader converts them
back, but quoting says what is meant. Any other non-string is refused rather
than stringified — `30` becoming `"30"` would be a silent wrong answer that
scores as a triage failure rather than the typo it is.

## Two rules that are not negotiable

**A variant cannot carry a label.** There is no field for one. Labels live on
the canonical case and reach every register and language through
`canonical_case_id`. This is why: deriving risk labels by running English
keyword rules over translated text produced language-asymmetric labels skewed
toward routine — French under-triage reached 0.994. Here that failure is
unrepresentable rather than merely forbidden.

**`label_quote` is required and must be a real sentence from the reference
answer.** Same role as `source_quote` on a clinical row: it makes the label a
restatement of something the benchmark says rather than our own judgement, and
it is what a second reader checks. A label that cannot be traced to a sentence
is deleted, not softened.

## Scope

`in_scope: false` marks a case that probes something deliberately not modelled —
pregnancy-related bleeding, for instance, which has no usable sources. It needs
an `out_of_scope_reason`, is excluded from scoring, and is **counted in the
report**. A gap we chose is not a gap we missed, and printing one as the other
would misstate both.

## What these are not

**Silver annotations**, read off the benchmark's own reference answers, not
clinician-adjudicated. Say so wherever results are reported.

**Not a test of the whole system.** Cases are expressed as feature values, so
`make eval` measures the controller alone. Turning prose into feature values is
the model's job and does not exist yet. Two consequences the report must carry:
cross-language and register agreement are unmeasurable here (every case runs
once from language-independent input), and clarification recall is near-vacuous
(the controller cannot conclude before asking, so it always asks).
