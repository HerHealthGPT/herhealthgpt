# The new flow, explained

For the meeting. Uses the real component names throughout — every technical
term is explained the first time it appears, in brackets, so this is readable
without an AI or software background but still says exactly what's being
built.

## The flow, step by step

1. The user types what's wrong, in her own words — for example, "my stomach
   really hurts and I feel sick." This goes to the **backend orchestrator**
   (the part of our system that manages one conversation from start to
   finish — a program, not a person).

2. The backend sends her words to the **embedding model** (a small, dedicated
   AI — specifically `Qwen3-Embedding-4B` — whose only job is turning text into a list of
   numbers, called a **vector**, that captures its *meaning*, so that pieces
   of text with similar meaning end up with similar numbers). This is the
   **semantic search model** the industry mentors asked for: a model
   dedicated to search, kept separate from the model that actually reasons
   about the case.

3. Those numbers are used to search a **retrieval index** (a searchable,
   pre-built copy of two things: real sentences from our trusted source pages,
   and every row of `evidence.csv` turned into a full sentence). This whole
   step is called **retrieval**, and the overall pattern — fetch real facts
   first, then hand them to an AI, instead of trusting the AI's memory — is
   called **RAG** (**R**etrieval-**A**ugmented **G**eneration). The index
   returns the handful of most relevant facts, each tagged with exactly where
   it came from (its **citation**). (`features.yaml` and `conditions.yaml`
   are not directly searchable yet — see the section below, "the seven
   knowledge files," for exactly how they're involved instead.)

4. Separately, the full contents of **`red_flags.yaml`** (our list of 14
   dangerous-symptom rules — e.g. "sudden severe pelvic pain") is added in
   full, every single time. Not searched for — just always included, because
   search can miss things and this list is too important to risk that.

5. Everything gathered so far — what she's said, the facts just retrieved,
   and the full danger list — goes to the **reasoning model** (the larger AI
   that actually decides what to do next: this is the fine-tuned model from
   the team's evaluation paper, trained using **QLoRA** — a lightweight way
   of fine-tuning a large model by training a small add-on instead of the
   whole thing — served alongside its untouched original "base" model).

6. The reasoning model must reply in exactly one of two shapes, enforced by a
   **structured output schema** (a strict form the AI's answer is checked
   against by code before it's accepted anywhere else — like a form with
   checkboxes instead of a blank page, so the AI literally cannot invent a
   fifth urgency level or ask about a symptom that isn't a real, defined
   question in our system). In our code this schema is a type called
   `TriageDecision`, and it's already built. The two shapes:
   - **`ask`** — one more clarifying question, which specific thing it wants
     to know (a **feature id** — the internal name for one symptom, e.g.
     `pain_onset`), why it's asking (its **rationale**), and which retrieved
     facts led it there (**citations**).
   - **`conclude`** — a final urgency level (an **action code** — one of
     exactly four: `SELF_CARE`, `ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`,
     `EMERGENCY`), optionally a short list (at most 5) of which conditions
     the answers matched, plus its rationale and citations. See "Naming
     which conditions match," below, for why that list is capped and why
     it's never shown alongside a danger-list escalation.
   
   Either way, it has to point to *something* it based the reply on — either
   a retrieved fact, or the specific danger-list rule it's responding to (a
   **red flag id**), or both. A reply pointing at nothing is treated the same
   as a made-up answer.

7. The whole exchange (every question and answer so far) is saved to a
   **session store** (a database — Postgres — that remembers a conversation
   between messages, the same way a chat app remembers your message
   history).

8. The chosen question — or the final answer, with its sources — is sent
   back to the user.

9. If it was a question, the flow goes back to step 2 with her new answer,
   and repeats until the reasoning model replies `conclude`.

## What is "agentic RAG", and why we thought it fit

The pattern above has a name: **agentic RAG**. Worth knowing what that name
actually means, because it's also where the biggest risk comes from.

Plain **RAG** (step 3 above) is a *single* fetch-then-answer: look something
up once, hand it to the AI, get one answer. That's it — no back-and-forth.

**Agentic RAG** means the AI itself is put in a loop where it keeps deciding,
turn by turn, whether it has enough information yet or needs to look up more
and ask another question — instead of looking things up once, automatically,
before it ever runs. "Agentic" means the AI has been given a say over its own
next step, not just over the final wording of its answer. Steps 2 through 9
above, repeating, *are* that loop: every single turn, the system looks things
up again based on whatever was just said, and the AI itself decides —
`ask` or `conclude` — whether to keep going.

**Why this seemed like the right shape for this project:** a triage
conversation is never one question and one answer — it's several questions
building toward one conclusion, which is exactly the shape agentic RAG is
built for (plain, single-lookup RAG doesn't fit a back-and-forth
conversation at all). It's also the standard way to combine the two things
asked for at once — a model dedicated to search (the mentors' ask) and a
reasoning model with its own specialised training (the supervisor's ask) —
working together across many turns instead of a single exchange. And the
**structured output schema** (step 6) is exactly the tool the industry uses
to keep an agentic AI's "decisions" checkable rather than an unaccountable
black box — nothing new had to be invented to adopt this pattern.

**The catch, and it's not a new one — it's the same caution already in this
document, with its proper name attached.** The best-known failure of
agentic RAG is an AI that decides, on its own, that it "has enough" and
stops too early, or never asks a follow-up at all — which is precisely the
failure this project already measured (under-triage collapsing to 0.994).
Calling this "agentic RAG" doesn't add a new risk on top of everything
already explained in this document; it's the standard industry name for the
exact risk already being managed here.

## The seven knowledge files, and exactly when each one is used

The steps above mention "the knowledge base" as one thing. It's actually
seven separate files, each with one job, and they don't all get used the same
way or at the same time. Two moments matter, and they're very different:

- **Build time** — done once (and re-done whenever the knowledge base
  changes), *before* anyone ever talks to the app. This is where the files
  are turned into a searchable index.
- **Request time** — happens live, every single message a user sends.

### What each file is

| File | What it is, in plain terms |
|---|---|
| `features.yaml` | The complete list of every symptom or question the system is allowed to ask about (e.g. "how heavy is the bleeding"). Nothing outside this list can ever be asked. |
| `conditions.yaml` | The complete list of every condition the system is allowed to consider (e.g. PCOS, a urinary tract infection). Nothing outside this list can ever be suspected. |
| `evidence.csv` | The **join** between the two above: for one symptom-and-answer, one row says how strongly it points toward one condition, and quotes the exact sentence from a real source that says so. |
| `red_flags.yaml` | The danger list — 14 rules for symptom combinations serious enough to skip straight to "see someone today" or "go to the emergency room now." |
| `sources.yaml` | Where every fact came from (NHS, CDC, etc.), and — importantly — what we're legally allowed to do with each source's text (some can only be quoted with credit, not copied wholesale — see the licensing note below). |
| `weights.yaml` | Turns "strong support" / "weak support" into actual numbers a computer could add up. **In the new design, this file mostly stops being used** — see "what used to happen instead of step 6," below — except for one number, a hard limit on how many questions can be asked. |
| `actions.yaml` | The four allowed urgency levels and their strict ordering, from least to most urgent. |

### How the files depend on each other

- `sources.yaml` comes first, in a sense: it decides which sources' text is
  even *allowed* to be copied into the searchable index in the first place.
- `features.yaml` and `conditions.yaml` set the allowed vocabulary. Every row
  in `evidence.csv` has to refer to a real entry in both — this is checked
  automatically, so a typo can't silently create a symptom or condition that
  doesn't really exist in the system.
- `evidence.csv` connects the two, and is the only one of the seven that gets
  turned into full sentences and added to the searchable index (see below).
- `red_flags.yaml` stands apart from all of this — it never goes into the
  searchable index at all (explained in step 4, and again below).
- `actions.yaml` and `features.yaml` together define the "strict form" (the
  **structured output schema**, `TriageDecision`, from step 6) that the AI's
  answer has to fit — so those two files also act as a checklist the AI's
  reply is checked against, separately from anything it read.

### The exact order of operations, restated file by file

**Build time — done once, offline, before any conversation:**

1. `sources.yaml` is checked first. It flags which sources' full text may
   legally be copied into the searchable index versus only quoted with
   credit (see the licensing note below).
2. `features.yaml` and `conditions.yaml` are loaded, and every `evidence.csv`
   row is checked against them.
3. Every `evidence.csv` row is turned into one plain-English sentence (for
   example: *"Bleeding heaviness = heavy (strong support) for uterine
   fibroids. Source: '...'"*) and added to the searchable index, alongside
   real sentences pulled from the cleaned source pages.
4. `actions.yaml`'s four urgency levels and `features.yaml`'s list of
   allowed symptoms become the "strict form" the AI's reply must fit later.

**Request time — happens live, every single message:**

1. The user's latest message (not a file — her actual words) becomes the
   search question.
2. The **embedding model** (`Qwen3-Embedding-4B`) turns that question into numbers. No
   file is touched at this step.
3. Those numbers search the index built in step 3 above. This is where
   `evidence.csv`'s content (as sentences) and the source pages come back —
   the most relevant handful, each with a citation.
   **`features.yaml` and `conditions.yaml` are not searched directly** — the
   only way their content shows up here is baked into the wording of an
   `evidence.csv` sentence. Teaching the system to search `features.yaml`
   directly (so it can match a symptom described in someone's own words to
   the closest official symptom name) is a known next step, not built yet.
4. Separately, and always — no searching involved — the full text of
   `red_flags.yaml` (all 14 rules) is added in. Every time, regardless of
   what step 3 found, because a search can miss something and this list is
   too important to leave to a search's judgement.
5. The reasoning model receives all of it in one go: what she's said so far,
   the facts just retrieved, and the full danger list.
6. Its reply must fit the strict form built from `actions.yaml` and
   `features.yaml` back in build-time step 4 — checked by code, not just
   requested politely.
7. The exchange is saved, and the flow either asks again (back to step 1) or
   answers.

`weights.yaml` doesn't appear anywhere in the request-time list above. In the
new design it contributes exactly one thing: a hard cap on how many questions
can be asked before the system has to stop and answer with whatever it has —
a dumb turn counter, not a judgement call.

### A licensing detail worth knowing about before this goes live

Some of our sources — the NHS website is the main one — can be **quoted with
credit** but their sentences aren't allowed to be **copied wholesale** into a
searchable AI system, under their copyright terms. Every sentence in the
index is already tagged with whether it's allowed to be used this way. What
isn't finished yet is the actual code that double-checks that tag *every time
a live search happens* — right now that check only happens once, when the
index is first built. This is a specific, concrete thing that has to be
finished before launch, flagged here so it doesn't get missed.

## A real example, step by step

Everything below is real: real symptoms, real rules from `red_flags.yaml`,
real sentences and real numbers computed from `knowledge/evidence.csv`.
Nothing here is invented.

**She types:** *"I've had really bad pain in my lower belly since
yesterday, and I feel sick to my stomach. I don't think I have a fever."*

Nothing anywhere writes that down as "pain: severe, nausea: yes, fever: no"
in a clean, structured way — there's no code step that does that translation
in this new design. The reasoning model has to work that out for itself from
her raw sentence, every single time it reads the conversation so far. That's
a genuine loss of structure compared to the old design, worth saying plainly
rather than glossing over.

**Turn 1, step by step:**

1. Her sentence, exactly as typed, is the search question.
2. The embedding model turns it into numbers.
3. The search comes back with real matching facts, for example:
   - *"Severity of pelvic pain = severe (strong support) for Adenomyosis.
     Source: 'painful periods — the pain may be severe and stop you from
     doing your usual activities'"* (from NHS)
   - *"Nausea or vomiting = yes (weak support) for Ovarian cyst. Source:
     'If a cyst causes twisting of an ovary, you may have pain along with
     nausea and vomiting.'"* (from the Office on Women's Health)
4. The full danger list is added in, as always. Four of its 14 rules are
   relevant to what she's said so far:
   - "Severe pelvic pain" → see someone today
   - "Pelvic pain with nausea or vomiting" → see someone today
   - "Pelvic pain with fever" → see someone today (doesn't apply — she said
     no fever)
   - **"Sudden onset of severe pelvic pain" → go to the emergency room —
     and this one is exactly one question away from applying.** Two "see
     someone today" rules already match what she's said. Whether it's
     actually an emergency instead depends entirely on one thing nobody has
     asked yet: did the pain come on *suddenly*? The old system's code
     *always* asked that question before answering, guaranteed, whenever
     this exact situation came up. In the new design, nothing forces
     that — the AI has to notice it on its own, from reading the list it was
     just handed, and choose to ask rather than jump to an answer.
5. If it does notice — this is what its reply looks like, in the actual
   strict form (`TriageDecision`) it must use:

   ```json
   {
     "type": "ask",
     "next_feature_id": "pain_onset",
     "question_text": "Did the pain come on gradually, or suddenly?",
     "citations": ["5dcce4e37a8f2821"],
     "red_flag_id": "sudden_severe_pelvic_pain",
     "rationale": "What you've described already matches patterns associated with needing same-day care. I'm asking whether the pain started suddenly because national guidance treats that combination as more urgent still."
   }
   ```

   That `red_flag_id` field is new, added while writing this exact example:
   the strict form originally had no way to say "I'm asking/answering
   because of a danger-list rule," only "because of a retrieved fact" — and
   a reply driven by the danger list has no retrieved fact to point to,
   because the danger list is never searched (step 4 above). Writing out
   this real example is what caught that gap.

**Turn 2.** She replies: *"It came on pretty suddenly, within about an
hour."* The system looks things up again based on that new sentence, adds
the same full danger list again, and now both pieces are in place — severe
pain, and sudden onset. The correct reply:

```json
{
  "type": "conclude",
  "action_code": "EMERGENCY",
  "citations": ["5dcce4e37a8f2821"],
  "red_flag_id": "sudden_severe_pelvic_pain",
  "rationale": "Severe pain that came on suddenly matches a specific emergency warning sign in national guidance, so this needs care right away rather than waiting."
}
```

Turned into an actual reply to her, under the system prompt below: *"Based
on what you've told me, this needs emergency care right away. What you've
described — pain that came on suddenly and severely — matches a specific
warning sign in national health guidance. Urgency guidance only, from cited
sources. Not a diagnosis."* Notice that no condition is ever named to her,
even though the source page this rule comes from is about a named condition —
the same discipline this project already uses to avoid ever suggesting
cancer to a user, just applied consistently everywhere.

## The system prompt, in full

The **system prompt** (background instructions given to the reasoning model
before every single turn, that the user never sees directly) is where the
"matches your symptoms, but never diagnoses" rule actually lives. In full:

> You are an AI triage assistant for reproductive-health questions, not a
> clinician, and you must never diagnose — never tell her she "has" a
> condition. When you conclude for a reason OTHER than a red-flag rule, you
> may name up to a few (no more than five, and usually fewer) of the
> authored conditions her answers most closely match, always phrased as a
> possibility grounded in evidence, never as a conclusion about what is wrong
> with her — for example: "Based on your answers, this may match patterns
> our sources associate with PCOS or perimenopause." Name only a handful of
> the closest matches — a long list of everything not yet ruled out is not
> useful guidance. Never name a specific disease when a red-flag warning sign
> is the reason for concluding — red flags exist to escalate on a symptom
> pattern without asserting what it is. Every citation, whether for a matched
> condition or an urgency level, is tied to a cited source. Ask one
> clarifying question at a time, or give urgency guidance — exactly one of
> SELF_CARE, ROUTINE_APPOINTMENT, URGENT_SAME_DAY, or EMERGENCY. Remind her
> plainly, in your own words, that you are an AI tool, not a clinician, and
> that this is based on her answers and the cited evidence, not a diagnosis.
> End every reply, question or final answer alike, with: "Urgency guidance
> only, from cited sources. Not a diagnosis." Under-triage is the dominant
> failure mode: when in doubt, prefer sending her to care sooner rather than
> later.

Worth being honest about what this is and isn't: it's an instruction, not a
guarantee. Unlike the strict form (`TriageDecision`), nothing in code checks
whether the AI actually followed it. Whether it reliably does, under real
conversations, is something that has to be measured, not assumed.

## Naming which conditions match — and why the list has a hard limit of 5

You asked for more than just an urgency level: a list of which conditions
the answers actually match, clearly labelled as coming from an AI tool that
doesn't diagnose. That's built in now — `TriageDecision` (the strict form
from step 6) has a `matching_conditions` field, and the system prompt above
tells the AI when it's allowed to use it.

**One rule, enforced by code, not just requested:** a reply can name
matching conditions, *or* be driven by the danger list, never both. The
whole reason the danger list exists is to say "this needs urgent care"
without asserting what's wrong — the same reason this project never
suggests cancer to a user even when a source names it. Naming conditions
next to a danger-list escalation would undo that on purpose, so the strict
form refuses to let both happen in the same reply.

**The limit of 5 was found by actually running this, not guessed at.** The
first version had no limit — take whatever the differential says is still
plausible and name all of it. Run for real against the actual knowledge
base, that came back naming **18 or 19 conditions, on almost every
conclusion** — nearly the entire list the system knows about, every time.
The reason: most of the 18 authored conditions have no evidence row that
argues *against* them, so very little narrows the list down. An 18-item
"these might match" list isn't a useful answer, it's just the whole roster
restated — worse than saying nothing, because it looks like a real answer
without being one. The strict form now hard-caps the list at 5, and the
system prompt tells the AI the same thing in words, so this can't slip
through even if the code check were somehow bypassed.

**A real example, capped correctly:** *"Based on what you've told me,
arrange a non-urgent appointment with a healthcare professional. What
you've described matches patterns our sources associate with uterine
fibroids, a urinary tract infection, adenomyosis, an inherited bleeding
disorder, and bladder pain syndrome. For example: '...' I'm an AI tool, not
a clinician — this is based on your answers and cited sources, not a
diagnosis. Urgency guidance only, from cited sources. Not a diagnosis."*

## What used to happen instead of step 6

Before this change, step 6 was not an AI decision at all. It was a piece of
plain Python code called the **deterministic controller**
(`TriageEngine.should_stop` — "deterministic" means it always produces the
exact same output for the exact same input, the way a calculator does,
because it's ordinary code, not an AI). It added up numeric scores (called
**log-odds** — a way of expressing "how likely," chosen because it's easy to
add up) from every matching row in `evidence.csv`, and a fixed set of rules
decided whether to ask again or stop. No AI judgement was involved in the
decision itself.

**That controller is being removed.** The reasoning model now makes the call
directly. The `TriageDecision` schema is the one part of the old
guarantees that's still fully enforced by code — it stops the AI from
answering outside the four allowed urgency levels or inventing a question
that isn't a real feature — but it cannot stop the AI from picking the
*wrong one* of those allowed options.

## Why the team is being careful about this

The old controller checked the danger list (`red_flags.yaml`) in code, so it
caught every case matching one of those 14 rules — 100% of the time,
provably, the same way a calculator always gets 2+2 right. The new reasoning
model has to *notice* the danger list itself, from the text it's given.
It's shown the whole list every single turn specifically to give it the best
possible chance — but "very likely to notice" is a different kind of promise
than "mathematically guaranteed to catch." That gap is why:

- The reasoning model needs to be **retrained** before it's trusted with this
  job (see below). Its original training data (`gold_seeds_styled.csv`, 540
  examples) never included a single example of asking a follow-up question —
  every example was a complete answer. Without retraining, it would very
  likely just always answer immediately, which is the exact failure the team
  already measured happening once before (538 of 540 French test cases came
  back wrong).
- This change is written up as an **ADR** (Architecture Decision Record — a
  reviewed, written decision document; ours is
  `docs/adr/0011-controller-free-triage.md`) rather than a quiet code change,
  because it reverses a safety rule (`CLAUDE.md`'s "no fine-tuned model
  decides urgency") that was put in place for a documented, measured reason.
  It needs supervisor sign-off before it's treated as final.

## Retraining the reasoning model, in plain terms

"Retraining" means giving the reasoning model new practice examples in a
**conversational format** (a full back-and-forth transcript, not just one
question and one answer), including cases where the correct move is to ask a
question rather than answer. We generate this automatically, once, by running
the *old* controller — before it's removed — over one realistic example
persona per condition in the knowledge base, and recording every question it
asked as a training example. That script already exists and has already been
run: `services/backend/src/herhealth_backend/triage/bootstrap_dataset.py`
produced 18 example conversations (one per condition currently authored in
`knowledge/conditions.yaml`) at
`services/data/eval/benchmark/bootstrap_multi_turn.jsonl`.

## Quick glossary

| Term | Plain meaning |
|---|---|
| Embedding model / semantic search model | A small AI that turns text into numbers so similar meanings can be matched quickly. Here: `bge-m3`. |
| Retrieval / RAG | Fetching real, cited facts before asking an AI to answer, instead of trusting its memory. |
| Reasoning model | The AI that actually decides what to ask or conclude. Here: the fine-tuned paper model + its base model. |
| QLoRA | A lightweight way to fine-tune a large AI model by training a small add-on piece instead of retraining the whole thing. |
| Structured output schema (`TriageDecision`) | A strict form the AI's reply must fit, checked by code, so it can't invent an answer outside the allowed options. |
| Deterministic controller | The old plain-code decision logic being removed — always the same output for the same input, no AI involved. |
| Action code | One of the four allowed urgency levels: `SELF_CARE`, `ROUTINE_APPOINTMENT`, `URGENT_SAME_DAY`, `EMERGENCY`. |
| Citation | The exact source sentence a claim or decision is traced back to. |
| ADR | Architecture Decision Record — a written, reviewed record of a design decision and why it was made. |
| Build time vs. request time | Build time: done once, offline, before anyone uses the app (turning the knowledge files into a searchable index). Request time: happens live, on every message. |
| Closed vocabulary | A fixed, complete list of allowed values — like `features.yaml`'s list of symptoms or `actions.yaml`'s four urgency levels — that nothing outside the list can ever match. |
| Licensing filter | The check that stops a source's text from being copied into the searchable index when its terms only allow quoting with credit, not wholesale reuse (NHS is the main example). |
| Agentic RAG | RAG (see above) done in a loop the AI itself controls — it decides, turn by turn, whether to look up more and ask again, or stop and answer. Plain RAG looks something up once; agentic RAG can keep looking things up across a whole conversation. |
| System prompt | Background instructions given to the AI before every turn, which the user never sees directly — where rules like "never diagnose" actually live. |
| Red flag id | The specific danger-list rule (from `red_flags.yaml`) a reply is based on, when it's based on the danger list rather than — or in addition to — a retrieved fact. |
| Matching conditions | The (at most 5) conditions a final answer says the pattern matches, always phrased as a possibility, never shown alongside a danger-list escalation. |

## Where everything else lives

The full technical decision record — every schema, every file changed,
diagrams, risks, and the step-by-step build plan — is in
[`docs/adr/0011-controller-free-triage.md`](adr/0011-controller-free-triage.md).
