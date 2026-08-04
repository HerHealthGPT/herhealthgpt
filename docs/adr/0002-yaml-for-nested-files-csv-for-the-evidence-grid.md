---
status: accepted
---

# Nested knowledge files are YAML; the evidence grid is CSV

Six of the seven knowledge files hold nested values — a feature's probe is a map
and its allowed values a list, a red flag holds a list of clauses — so they are
YAML, which represents nesting natively. The seventh, the evidence grid, is a
wide flat table of identical scalar rows and will reach several hundred of them,
so it is CSV, which diffs one row per line.

## Considered options

- **Everything CSV.** Rejected: representing a map and a list inside a CSV cell
  means inventing an encoding for nesting, which is what YAML already is. The
  encoding would then need parsing, documenting and testing.
- **Everything YAML, including evidence.** Rejected: several hundred
  five-line blocks is unreadable in bulk, and a row-per-line diff is exactly
  what you want when reviewing a change to a clinical grid.

## Consequences

A reader coming to `knowledge/` will reasonably ask why the formats are mixed —
this is the answer. The mix is a deliberate fit to the shape of each file, not
an accident of history.

Because the format split makes whole-file reading harder, `make tables` renders
every file as a flat CSV plus one Markdown document. Those exports are
generated, gitignored and never read back: two representations of the same data
in version control is two things to keep in sync, and one of them eventually
goes stale.
