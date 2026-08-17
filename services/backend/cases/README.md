# Controller demonstration cases

Hand-written consultations for `herhealth-triage`. Each file says what is true
of one person; the controller decides what to ask.

```
make triage CASE=services/backend/cases/sudden_severe_pain.yaml
```

**These are not the evaluation set.** The benchmark lives in
`services/data/eval/cases/` and is scored. These four exist to exercise the
stopping rules by hand and to keep their behaviour visible in a diff — each one
is pinned by a test in `tests/test_cli.py`, so a change to the weights or the
question ranking shows up as a failing assertion naming the case rather than as
a silent shift in behaviour.

| Case | Exercises |
|---|---|
| `sudden_severe_pain.yaml` | Rule 1 — a red flag outranks the differential |
| `heavy_periods_over_40.yaml` | Rule 5 — the question budget, at the most urgent action |
| `itching_and_discharge.yaml` | The higher bar on concluding `SELF_CARE` |
| `says_nothing.yaml` | Every answer `unknown` — the floor case |

Values must appear in the feature's `allowed_values`; the CLI refuses anything
else rather than treating it as unknown, because a typo that reads as "she did
not say" would quietly turn an escalation into a routine appointment.

Quote `yes` and `no`. YAML parses them as booleans, and while the loader
converts them back, quoting says what is meant.
