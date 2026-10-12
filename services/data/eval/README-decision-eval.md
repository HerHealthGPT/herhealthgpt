# Decision evaluation inputs

Read by `herhealth-eval-decisions` (ADR 0018).

- `decision_questions.jsonl`: 30 first-turn questions taken from
  `benchmark/gold_seeds_styled.csv`: ten seeds on topics the corpus covers, in
  the layperson, ambiguous and emotionally-concerned registers.
  `describes_own_symptoms` marks the 12 in which she reports something she is
  experiencing herself. That flag was assigned by reading each question on
  2026-10-12; it is a judgement, not a label from the benchmark.
- `decision_scripts.jsonl`: ten scripted consultations. Each has an opening
  message (one of the 12 above) and her reply to each feature she may be asked
  about. A feature with no scripted reply is answered "No.". The replies were
  written for this evaluation to exercise asking and concluding across turns.
  They are not clinical content and no urgency in them is treated as correct.

The benchmark's labels are silver, not clinician-adjudicated, and nothing here
measures whether the urgency advice is right.
