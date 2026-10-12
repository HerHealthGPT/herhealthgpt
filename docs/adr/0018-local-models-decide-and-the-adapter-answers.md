---
status: accepted
date: 2026-10-12
supersedes: 0012
---

# The local base model decides, and the fine-tuned adapter words informational answers

## Context

[ADR 0012](0012-openrouter-reasoning-and-guarded-web-fallback.md) put reasoning
on OpenRouter, with the fine-tuned adapter offered through a dev-only selector
and OpenRouter as its fallback. On 2026-10-11 the repo owner decided the whole
stack runs on the campus GPU box, with no OpenRouter, built on LangChain, and
that the fine-tuned model should be used.

Whether the adapter could make the decisions was measured before designing
anything. Thirty user-style first-turn questions from the benchmark (ten seeds
on covered topics, in the layperson, ambiguous and emotionally-concerned
registers) were run through the real agent, once per model:

| | Adapter (`herhealth`) | Base (`Qwen/Qwen3.5-9B`) |
|---|---|---|
| Valid decisions | 0 of 30 | 23 of 30 |
| Median seconds per turn | 46 | 21 |
| Clarifying questions asked | 0 | 0 |

The adapter replied in prose in 25 of 30 turns, which is what its training
data asked for. The base model was valid most of the time but explained
(`inform`) on 21 of its 23 valid turns, including messages describing her own
symptoms, and recorded what she said in only 3 of them.

## Decision

- **The base model decides.** It is served by the same vLLM process as the
  adapter. The adapter does not choose an action code; that part of ADR 0011
  rule 1 stands.
- **A turn has up to three steps**, each a LangChain call
  (`triage/chain.py`): *extract* (the base model maps her latest message onto
  the feature list), *decide* (the base model, with the existing prompt and
  checks), and, only for an accepted `inform`, *answer* (the adapter words the
  answer from the cited passages).
- **An `inform` is refused once** when she has described symptoms of her own
  or a warning sign is close. If the model informs again, that stands.
- **The adapter cannot make a reply invalid.** Its text replaces the answer
  only if it is non-empty, within length and free of banned wording.
  Warning-sign lines are copied onto it from the base model's answer by code,
  in the two layouts the prompt allows; if the base answer holds urgent advice
  in any other wording, the adapter's text is discarded and the base answer
  stands whole. Any error in the step leaves the base answer in place. It can
  still cost time: a slow answer step counts against the turn's time budget.
- **One repair is applied to a reply**: the first complete JSON object is
  taken, so a code fence or trailing text does not fail a turn. No field is
  rewritten.
- Requests set `temperature=0` and a `max_tokens` cap.
- **OpenRouter, the model selector and the fallback are removed.**
  `HERHEALTH_TRIAGE_MODE` is `vllm`, `demo` or `off`.

## What was measured after the change

`herhealth-eval-decisions`, run on the campus box on 2026-10-12.

**First turns, 30 questions**

| Measure | Before | After | Target |
|---|---|---|---|
| Valid decisions | 23 | 26 | at least 27 |
| Clarifying questions asked | 0 | 4 | more than 0 |
| Median seconds per turn | 21 | 31 | at most 45 |
| Slowest turn, seconds | 93 | 59 | |

On the 12 questions flagged as describing her own symptoms: 8 valid, of which
3 asked, 1 concluded (`EMERGENCY`) and 4 informed. Before: 7 valid, 0 asked,
1 concluded, 6 informed. The target was at most 2 informs.

An earlier pass of the same 30 questions, with longer timeouts, gave 25 valid,
4 asks and 3 informs on the flagged questions; the numbers move by one or two
between runs even at temperature 0, because latency decides which attempts
time out. In that pass the extract step found something in 11 of 30 messages
in about a second, and the adapter's text was used for 20 of 20 informs at
about 11 seconds each.

**Scripted consultations, ten scripts**

**3 of 10 reached a conclusion.** One escalated on the first turn
(`EMERGENCY`), one concluded in 2 turns and one in 8. The other seven ended in
a rejected reply:

| Reason the turn was rejected, on both attempts | Scripts |
|---|---|
| A question with no citation ("a decision must be grounded in at least one citation or a red_flag_id") | 4 |
| Case-note wording in user-facing text ("You mentioned…") | 2 |
| An invented feature id | 1 |

The scripts were corrected once before this run: the first version had no
reply to the age question, so the model re-asked it, and a mid-consultation
decline surfaced as a bare error. Both were faults in the evaluation.

## Follow-up the same day: a question no longer has to cite a passage

The repo owner decided the first open decision below on 2026-10-12: a
clarifying question does not need a citation. `TriageDecision` now exempts
`ask` from the grounding rule; its feature must still be a real one, and
conclusions and explanations keep the requirement. The evaluation was re-run.

| Measure | Before the chain | Chain | Chain, no citation on a question |
|---|---|---|---|
| First turns valid, of 30 | 23 | 26 | 28 |
| Clarifying questions asked | 0 | 4 | 7 |
| Median seconds per turn | 21 | 31 | 30 |
| Own-symptom questions (12): valid | 7 | 8 | 11 |
| ...of which asked / concluded / informed | 0 / 1 / 6 | 3 / 1 / 4 | 6 / 1 / 4 |
| Scripted consultations concluded, of 10 | not run | 3 | 3 |

First turns now meet the validity target (27). The informs on own-symptom
questions are still 4 against a target of 2.

**Scripted consultations are still 3 of 10, but they fail differently and
later.** No turn was lost to a missing citation. Consultations now run five to
eight turns before ending:

| How the other seven ended | Scripts |
|---|---|
| Still asking after 8 turns, repeating questions already answered (one asked about the same feature four times) | 3 |
| Case-note wording ("You mentioned…") on both attempts | 2 |
| The model recorded an invented feature id in `observed` | 2 |

So the citation rule was a real cause and removing it helped single turns,
but it was hiding two further problems: the model re-asks what it has been
told, and a made-up id in `observed` fails a whole turn. The second and third
open decisions below still stand, and a fourth joins them: whether an
unrecognised entry in the model's own `observed` should be dropped, as the
extract step already does, instead of failing the turn.

## What this shows

The points below describe the first run, before the citation change.


- **The design does what it was meant to on first turns.** The system now
  asks, validity rose, and turns stay under a minute.
- **Two of the three targets were missed**, narrowly: 26 valid against 27,
  and 4 informs on the flagged questions against 2.
- **Multi-turn consultations mostly do not complete.** This is the finding
  that matters. In `vllm` mode, a woman who answers a first question is more
  likely than not to get an error on a later turn. With OpenRouter gone there
  is no second model to catch it.
- **The dominant cause is one rule.** A clarifying question must cite a
  retrieved passage, and the base model often asks a sensible question from
  the system's own question list without citing anything, twice in a row.
  Whether a question drawn from that list needs a passage citation is a
  decision about the safety contract (`TriageDecision`), so it was not changed
  here.
- **The extract step is fallible.** "I can't seem to lose weight" was recorded
  as weight unchanged; "I've tried everything to lose weight and nothing
  works" was recorded as weight loss and as difficulty conceiving, which she
  did not say.

## Limits

The evaluation calls the agent directly. It applies neither the HTTP route's
turn timeout nor its second whole-turn attempt, so "valid" here is close to,
but not exactly, what a user of the API would see.


Thirty questions and ten scripts, English only, from a benchmark whose labels
are silver and not clinician-adjudicated. "Valid" means a reply passed this
system's own checks; nothing here measures whether the urgency advice was
right. The flags for "describes her own symptoms" and the scripted replies
were written for this evaluation. The knowledge base is source-traceable, not
clinician-adjudicated.

## Consequences

- **Step 3b (connecting production to these endpoints) should wait** until
  scripted consultations complete reliably. Shipping this to users as it is
  would put errors in front of most of them.
- **Open decisions for the repo owner, none taken here:**
  1. ~~whether an `ask` must still cite a passage~~ decided 2026-10-12: it
     need not (see the follow-up above);
  2. whether to allow a third attempt, or more specific feedback, when the
     wording check fails;
  3. how much to trust the extract step, and whether its output should be
     shown to the decide step as a suggestion instead of as fact.
- The adapter's informational answers are not checked for faithfulness to the
  passages; only wording, length and warning-sign lines are checked in code.
- Production triage reports "not configured" until step 3b, as after ADR 0017.
- The Terraform definition of the OpenRouter secret remains and can be removed
  in a later `terraform apply`. An OpenRouter key that was pasted into a chat
  session earlier in the project should still be treated as compromised and
  rotated or revoked, whether or not the app uses it.
