# Benchmark cases

Version-controlled, deliberately. These cases test the knowledge in `knowledge/`,
so they belong next to it in history — a change to an evidence row that shifts a
case outcome should show up in the same diff.

Empty until phase 3. Two rules carried over from how the earlier benchmark was
built, both of which fixed real bugs:

- The risk label is derived **once**, from the English source text, and
  propagated to other languages by `canonical_case_id`. Never run English
  keyword rules over translated text.
- These are **silver annotations**, not clinician-adjudicated. Say so wherever
  results are reported.
