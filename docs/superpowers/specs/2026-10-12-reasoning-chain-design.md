# The reasoning chain on LangChain — design

Date: 2026-10-12. Status: draft, awaiting review.

Step 3a of the move to a self-hosted stack. Steps 1 (model serving) and 2
(retrieval) are done. Step 3b, connecting the EC2 backend to the campus
endpoints, follows this and has its own spec.

## What was decided, and by whom

Decided by Mazen Bahgat on 2026-10-12, after the measurement below:

- **The base model decides.** `Qwen/Qwen3.5-9B`, served by the same vLLM
  process as the adapter, chooses ask, conclude, inform or decline.
- **The fine-tuned adapter writes informational answers.** When the decision
  is `inform`, the adapter (`herhealth`) writes the answer text.
- **Each turn has two reasoning steps:** first map her message onto the
  feature list, then decide.
- OpenRouter is removed, with the model selector and the fallback built on it.
- The pipeline is built on LangChain.

This changes ADR 0011 rule 1 in one direction only: it stays true that the
adapter does not choose an action code. ADR 0012 (OpenRouter reasoning) and
ADR 0016's model selector are superseded. A new ADR records this.

## The measurement behind it

Thirty user-style first-turn questions from the benchmark (ten seeds on
covered topics, in the layperson, ambiguous and emotionally-concerned
registers) were run through the real agent on 2026-10-12, once per model,
with the deployment's validation and its early-conclusion gate.

| | Adapter (`herhealth`) | Base (`Qwen/Qwen3.5-9B`) |
|---|---|---|
| Valid decisions | 0 of 30 | 23 of 30 |
| Valid on the first attempt | 0 | 18 |
| Median seconds per turn | 46 | 21 |
| Slowest turn, seconds | 240 | 93 |
| Turns over 50 seconds | 12 | 2 |

- **The adapter** replied in prose, not JSON, in 25 of 30 turns: a plain
  answer followed by a "Sources:" list, which is what its training data
  asked for. A separate two-question probe produced valid JSON once, so the
  behaviour is unreliable, not impossible. Requests set no temperature.
- **The base model's seven failures:** banned case-note wording (3), no
  citation (2), malformed JSON (2).
- **Neither model asked a clarifying question.** Of the base model's 23 valid
  decisions, 21 were `inform`, one `decline`, one `conclude`
  (`URGENT_SAME_DAY`, on unbearable pain with much heavier bleeding). It
  informed on messages that describe her own symptoms, which the prompt
  forbids. An inform carries no urgency level, so this is under-triage risk.
- **`observed` was filled in 3 of the 23 valid turns.** That field drives the
  list of questions worth asking and the warning-sign check; left empty, the
  model has nothing to ask about.
- A turn's prompt is about 6,000 tokens.

Limits: first turns only, 30 questions, English, one run each with sampling
on. "Valid" means the reply passed the system's own checks, not that the
advice was right. Labels in the benchmark are silver, not
clinician-adjudicated.

## Goals

1. Turns complete reliably on the local base model, with no OpenRouter.
2. The system asks when she describes her own symptoms.
3. The adapter is used where it performs: writing informational answers.
4. The reasoning path is built from LangChain components, like retrieval.

## A turn, end to end

```
her message + history
   │
   ├─ retrieval (step 2, unchanged)
   │
   ├─ 1. EXTRACT   base model, short prompt
   │      her latest message  →  {feature_id: value}
   │
   ├─ 2. DECIDE    base model, the existing prompt
   │      history + passages + what she has said so far  →  TriageDecision
   │      validate → repair → retry with the error, up to 2 attempts
   │      gates: early conclusion (existing), inform with symptoms (new)
   │
   └─ 3. ANSWER    adapter, only when the decision is inform
          question + cited passages  →  answer text
          checked; on failure the base model's own answer stands
```

Everything sits behind the existing `ReasoningClient` protocol, so
`TriageAgent`, the routes and session storage keep their shape. One addition
to the protocol's caller is described under "The extract step".

### The chat model

`langchain_openai.ChatOpenAI` pointed at `HERHEALTH_VLLM_URL`, one instance
per model name:

- `temperature=0`, so the same input gives the same reply.
- `max_tokens`: 300 for extract, 1,200 for decide, 900 for answer. Today no
  cap is sent, so an oversized prompt becomes a retry loop.
- `timeout` from `HERHEALTH_VLLM_TIMEOUT` (default 50 seconds, unchanged),
  `max_retries=0`: retries are this module's job, with feedback.
- Thinking disabled through the same `chat_template_kwargs` the current
  client sends.

### 1. The extract step

A short prompt: the feature list with each feature's allowed values, her
latest message, and the feature she was asked about last turn, if any. The
reply is a JSON object of feature id to value.

- Unknown feature ids and values outside a feature's list are dropped, not
  retried: a dropped entry is merely not recorded, which is today's state.
- If the call fails or times out, the turn continues with nothing extracted.
  Extraction improves a turn; it must never fail one.
- The result is merged into the case record before the decide step: her
  profile age band first, then earlier turns, then this extraction. The
  decide step's own `observed` is merged last, as today.

The agent calls it through a new optional seam, `FeatureExtractor`, so tests
and the demo mode run without one.

### 2. The decide step

The existing system prompt, JSON shape instruction, retrieved-passage block
and per-turn context are reused word for word, assembled with a
`ChatPromptTemplate`. This step changes how the model is called and what it
is shown about her answers, not the rules it is given.

- **Repair, one kind only.** Take the first complete JSON object from the
  reply, so a code fence or trailing text does not fail the turn. No field is
  ever rewritten.
- **Validation** is unchanged: the `TriageDecision` schema, the closed
  vocabulary check, and the banned-wording check on user-facing text.
- **Retry with feedback**, up to `HERHEALTH_VLLM_MAX_ATTEMPTS` (default 2):
  the error is appended and the model is asked again.
- **Timeouts are retried**, as today.

### The inform gate (new)

An `inform` reply is refused once, and the model re-asked, when either holds:

- the case record holds any feature value for this consultation other than
  the profile age band, whether from this turn's extraction or earlier turns;
- a warning sign has fired or is one answer away.

The re-prompt says an explanation is not allowed while she has described
symptoms of her own, and to ask or conclude. If the model informs again, the
second reply stands, on the same reasoning as the existing early-conclusion
gate: the gate gives way, it does not loop.

This is a refusal to accept, not a decision made in code. It picks no
question and no action code.

### 3. The answer step

Runs only when the accepted decision is `inform`.

- **Prompt.** The instruction the adapter was trained on, her question, and
  the text of the passages the decision cited. Nothing else: no feature
  vocabulary, no rules list.
- **Output handling.** A trailing "Sources:" section is cut off, since the
  interface renders citations itself. Markdown emphasis markers are stripped.
- **Checks.** Non-empty; within 2,500 characters; passes the existing
  banned-wording check.
- **Warning-sign lines are carried by code, not by the adapter.** The decide
  prompt already makes the base model end an inform with lines of the form
  "Get emergency care now if…" and "See someone today if…". Those lines are
  taken from the base model's answer and appended to the adapter's text under
  the heading "When to get medical help:" whenever the adapter's text does not
  already contain them.
- **Fallback.** If the adapter's reply fails a check, or the call fails or
  times out, the base model's own `answer_text` is used unchanged. The turn
  never fails because of this step.
- `HERHEALTH_ANSWER_MODEL` (default `herhealth`) names the model; set empty,
  the step is skipped.

The persisted record of a turn says which model wrote the answer, through the
existing `served_by` attempts list.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `HERHEALTH_TRIAGE_MODE` | `off` | `vllm`, `demo` or `off`. `openrouter` is removed |
| `HERHEALTH_VLLM_URL` | `http://127.0.0.1:8002` | chat endpoint |
| `HERHEALTH_DECISION_MODEL` | `Qwen/Qwen3.5-9B` | extract and decide steps |
| `HERHEALTH_ANSWER_MODEL` | `herhealth` | answer step; empty disables it |
| `HERHEALTH_VLLM_API_KEY` | unset | bearer token, sent when set |
| `HERHEALTH_VLLM_TIMEOUT` | `50` | seconds per model call |
| `HERHEALTH_VLLM_MAX_ATTEMPTS` | `2` | decide attempts |

`HERHEALTH_VLLM_MODEL`, `OPENROUTER_API_KEY` and `HERHEALTH_MODEL_SELECTOR`
are removed. With no explicit mode, triage is off; it no longer switches on
because a key happens to be set.

The mode is set to `vllm` explicitly in `infra/envs/backend.env.example`, in
`infra/compose.prod.yml`, and in the campus box's own untracked
`infra/envs/backend.env` (that one line only, once the new code is in place).
The code default stays `off`, so a host nobody configured never tries to
reach a model. In production the mode has no effect until step 3b: without an
index the backend reports triage as "not configured".

## What is deleted

- `OpenRouterReasoningClient`, `VllmReasoningClient`,
  `FallbackReasoningClient` and the request-building helpers only they use,
  in `triage/clients.py`. The prompt text, the passage rendering and the
  validation functions move to the new module and are kept.
- `app/triage/reasoning_models.py`, the `GET /triage/models` route, and the
  per-turn model choice in `POST /triage/turn`.
- Frontend: `model-selector.tsx`, `unreviewed-model-notice.tsx`,
  `lib/model-preference.ts`, and their use in the chat page and header.
- `infra/compose.prod.yml` and `infra/deploy/refresh-secrets.sh`: the
  OpenRouter key and the selector setting.

Kept: database columns and migrations that mention the model (they are
history), the demo mode, and the Terraform definition of the OpenRouter
secret, which is removed in a later manual `terraform apply`.

## Measurement

The 30-question run becomes a committed command,
`herhealth-eval-decisions`, so it can be repeated: it reads a question file,
runs first turns through the real agent, and reports valid replies, decision
types, failure reasons and timings.

It is run before and after this change. Targets, reported and not gated:

| Measure | Baseline (base model) | Target |
|---|---|---|
| Valid decisions | 23 of 30 | at least 27 |
| Informs on the questions describing her own symptoms | 8 of the 9 that were valid | at most 2 |
| Clarifying questions asked | 0 | more than 0 on those questions |
| Median seconds per turn | 21 | at most 45 |

The set of "questions describing her own symptoms" is fixed in the question
file as a flag per question, assigned by reading each one; it is a judgement
and the file says so.

Ten scripted multi-turn consultations are added to the same command, so that
asking, answering and concluding across turns is exercised: the script
supplies her replies, and the run reports how many reach a conclusion and in
how many turns. No correctness of urgency is claimed from them.

## Testing

No test hits the network or needs a GPU.

- **Chain.** With a scripted fake chat model: a valid reply; a fenced reply
  repaired; a banned-wording reply retried with feedback; two bad replies
  raising; a timeout retried.
- **Extract.** Unknown ids and out-of-list values dropped; failure returns
  nothing and does not raise.
- **Inform gate.** Refused when symptoms are recorded; refused when a warning
  sign is near; accepted for a question with nothing recorded; a second
  inform stands.
- **Answer step.** "Sources:" trimmed; warning-sign lines appended when
  missing and not duplicated when present; banned wording falls back to the
  base answer; a timeout falls back.
- **Wiring.** Each mode builds what it should; `openrouter` is rejected with
  a message naming the valid modes.
- The frontend's type check and build pass without the selector.

## Risks

- **The adapter's answer is not checked for faithfulness.** Code can check
  wording, length and that warning-sign lines survive; it cannot check that
  the adapter restated the passages correctly. An inform carries no urgency
  level, which limits the harm, and the cited passages are shown beside the
  answer. This is a stated limitation.
- **The inform gate can be argued past.** It refuses once. A model that
  informs twice is accepted.
- **Extraction can be wrong.** A wrongly recorded value changes which
  questions are offered and can bring a warning sign into play. The bias is
  toward false alarms, which is the direction this project chooses.
- **Each turn is two or three model calls.** Expect a slower median than
  today's 21 seconds. The 60-second proxy cut matters in step 3b, not here.
- **No second model stands behind the base model.** If it fails twice the
  turn returns 502.
- **Schema-constrained output still does not work** on this serve, so
  validity rests on the prompt, the checks and the retry.
- **The targets may be missed.** If they are, the result is reported as it
  is, and the design is revisited before step 3b.

## Out of scope

- Reaching the endpoints from EC2, and getting the index there (step 3b).
- Rewriting the system prompt's rules.
- Retraining the adapter.
- Arabic and French evaluation.
- Any change to `knowledge/`, retrieval or the database schema.

## Done when

- `HERHEALTH_TRIAGE_MODE=vllm` completes a turn on this box with no
  OpenRouter code in the tree.
- `herhealth-eval-decisions` has a recorded before and after, with the
  multi-turn results, in the new ADR.
- The chat UI has no model selector, and the frontend builds.
- `git grep -i openrouter` matches only ADRs, research notes, migrations,
  Terraform and the superpowers documents.
- `make test`, `make lint` and the hygiene check pass.
