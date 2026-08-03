---
status: accepted
---

# Severe pelvic pain is urgent, not emergency

Three NHS pages disagree on severe pelvic pain and all carry the same source
precedence, so precedence cannot break the tie. We resolved it deliberately:
severity alone returns `URGENT_SAME_DAY`, and severity **with sudden onset**
escalates to `EMERGENCY`. This departs from the project's default rule of taking
the higher urgency whenever sources conflict, so it is recorded here.

## Context

- Pelvic pain page: *"Call 999 or go to A&E if… it's severe, getting worse, or
  hurts when you move or touch the area"*
- Period pain page: *"Ask for an urgent GP appointment… if your pelvic pain or
  period pain is severe or worse than usual, and painkillers have not helped"*
- Ovarian cyst page: *"you have sudden, severe pelvic pain"* → urgent

Two of three route severe pain to 111. More importantly, the 999 bullet is not
severity alone — it reads *severe, **getting worse**, or **hurts when you move
or touch***, which describes an acute abdomen. No feature exists for progression
or tenderness, so encoding that bullet as severity alone would over-read the
source.

Routing all severe pain to an ambulance would fire constantly on exactly the
endometriosis and fibroid population this system serves, which is a large
over-triage cost for a rule the sources do not clearly support.

## Consequences

The conflict is recorded in `build/conflicts.jsonl` with all three quotes and
their URLs — never resolved silently.

**Revisit if `pain_getting_worse` or `pain_on_movement` features are added.**
The 999 bullet becomes encodable as written at that point, and `EMERGENCY` may
be the right answer. Do not change this silently in either direction: it is the
single largest over-triage lever in the rule set.
