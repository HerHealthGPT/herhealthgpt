# Reasoning Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run every triage turn on the local models through LangChain: the base model extracts what she said and decides, the fine-tuned adapter writes informational answers, and OpenRouter is gone.

**Architecture:** A new `triage/chain.py` holds a LangChain chat model factory and three small components behind seams the agent already has or gains: `LangChainReasoningClient` (decide), `LangChainFeatureExtractor` (extract) and `LangChainAnswerWriter` (answer). The prompt text, passage rendering and validation in `triage/clients.py` are reused unchanged; only the transport and the retry loop are replaced. The agent gains the extract step, an inform gate and the answer step.

**Tech Stack:** Python 3.12, `langchain-core`, `langchain-openai` (`ChatOpenAI` against vLLM), pydantic, pytest; Next.js for the selector removal.

**Spec:** `docs/superpowers/specs/2026-10-12-reasoning-chain-design.md`

**Why this plan is shorter than the previous two.** It names every file, interface, test and command, but does not reproduce each code block. It was written for native execution in the session that designed it, late in a long context; the spec carries the behaviour, and each task's tests are listed by name so the red-green order is fixed.

## Global Constraints

- Decision model `Qwen/Qwen3.5-9B`, answer model `herhealth`, chat endpoint `http://127.0.0.1:8002`, all from settings.
- `temperature=0`; `max_tokens` 300 (extract), 1200 (decide), 900 (answer); `max_retries=0` on the chat model.
- The adapter never chooses an action code and never fails a turn.
- The extract step never fails a turn.
- No user-facing text is rewritten in code, except trimming a trailing "Sources:" section and markdown emphasis from the adapter's answer, and appending warning-sign lines taken verbatim from the base model's answer.
- The system prompt, the JSON shape instruction and every existing check are reused word for word.
- Tests never hit the network: use `langchain_core`'s fake chat models and scripted callables.
- No file, comment, string or commit message may describe the system as diagnosing.
- `export UV_PROJECT_ENVIRONMENT=/tmp/herhealth-venv UV_CACHE_DIR=/tmp/uv-cache` before any `uv` command.
- Commit per task on `Mazen-Branch`. Nothing is pushed.

## Review Focus

1. **The adapter drops or rewords a warning-sign line**: the final answer must still contain every "Get emergency care now if…" and "See someone today if…" line from the base model's answer. Task 4.
2. **The base model informs twice in a row while she has described symptoms**: the second reply stands and the turn does not loop or fail. Task 3.
3. **The extract call times out or returns junk**: the turn continues with nothing extracted. Task 2.
4. **A reply wraps valid JSON in a code fence or adds text after it**: accepted after repair, without a retry. Task 1.
5. **A host with `HERHEALTH_TRIAGE_MODE=openrouter` left in its env**: start-up fails with a message naming the valid modes, not a silent fallback to off. Task 5.

## Tasks

### Task 1: The decide step on LangChain

**Files:** create `services/backend/src/herhealth_backend/triage/chain.py`, `services/backend/tests/test_chain.py`; modify `triage/clients.py` (add `parse_decision_text`).

**Produces:**
- `clients.parse_decision_text(content: str) -> TriageDecision` (the body of `_parse_chat_completion_payload`, with JSON-object extraction first); `_parse_chat_completion_payload` calls it.
- `chain.extract_json_object(text: str) -> str`
- `chain.build_chat_model(*, url, model, api_key, timeout, max_tokens) -> ChatOpenAI`
- `chain.ReasoningUnavailable(httpx.HTTPError)`
- `chain.LangChainReasoningClient(chat, *, name, validator=None, max_attempts=2)` with `.name` and `.decide(*, system_prompt, history, context) -> ReasoningResult`

**Tests (write first, watch fail):** `test_extract_json_object_*` (plain, fenced, trailing text, nested braces in strings, no object raises); `test_a_valid_reply_is_returned_in_one_call`; `test_a_fenced_reply_is_repaired_without_a_retry`; `test_banned_wording_is_retried_with_feedback`; `test_the_validator_runs_inside_the_retry_loop`; `test_two_bad_replies_raise_value_error`; `test_a_timeout_is_retried`; `test_an_unreachable_endpoint_is_an_http_error`; `test_build_chat_model_sets_temperature_tokens_and_no_retries`.

**Run:** `uv run --extra ingest --extra retrieval pytest services/backend/tests/test_chain.py -q`

### Task 2: The extract step

**Files:** modify `chain.py`, `triage/agent.py`, `test_chain.py`; create `services/backend/tests/test_agent_extract.py`.

**Produces:**
- `agent.FeatureExtractor` protocol: `extract(history: Sequence[Message], *, pending_feature: str | None) -> dict[str, str]`
- `TriageAgent.extractor: FeatureExtractor | None = None`. In `run_turn`, extracted values are merged over `observed` before the turn context is built, and merged under the returned decision's own `observed`, so the existing persistence carries them forward.
- `chain.LangChainFeatureExtractor(chat, base)`

**Tests:** `test_extraction_maps_a_message_to_listed_values`; `test_unknown_features_and_values_are_dropped`; `test_a_failed_extraction_returns_nothing`; `test_extracted_values_reach_the_turn_context`; `test_extracted_values_are_returned_on_the_decision`; `test_the_agent_runs_without_an_extractor`.

### Task 3: The inform gate

**Files:** modify `triage/agent.py`; create `services/backend/tests/test_inform_gate.py`.

**Produces:** `TriageAgent.refuse_inform_with_symptoms: bool = False`. When on, an `inform` is sent back once if the turn context holds any given feature other than `age_band`, or a warning sign has fired or is one answer away.

**Tests:** `test_inform_is_refused_when_she_described_a_symptom`; `test_inform_is_refused_when_a_warning_sign_is_near`; `test_inform_is_accepted_when_nothing_is_recorded`; `test_a_profile_age_band_alone_does_not_refuse`; `test_a_second_inform_stands`; `test_the_gate_is_off_by_default`.

### Task 4: The answer step

**Files:** modify `chain.py`, `triage/agent.py`; create `services/backend/tests/test_answer_writer.py`.

**Produces:**
- `agent.AnswerWriter` protocol: `write(question: str, passages: Sequence[RetrievedPassage], base_answer: str) -> str | None` and `name: str`
- `TriageAgent.answer_writer: AnswerWriter | None = None`; applied to an accepted `inform`, with a `ReasoningAttempt` recorded for it.
- `chain.LangChainAnswerWriter(chat, *, name)`, `chain.carry_warning_lines(answer: str, base_answer: str) -> str`, `chain.trim_adapter_answer(text: str) -> str`

**Tests:** `test_sources_section_is_trimmed`; `test_markdown_emphasis_is_stripped`; `test_warning_lines_are_appended_when_missing`; `test_warning_lines_are_not_duplicated`; `test_banned_wording_falls_back_to_the_base_answer`; `test_an_empty_or_overlong_answer_falls_back`; `test_a_failed_call_falls_back`; `test_only_cited_passages_are_shown_to_the_writer`; `test_the_writer_runs_only_for_inform`.

### Task 5: Wiring, and removing OpenRouter and the selector from the backend

**Files:** modify `app/main.py`, `app/config.py`, `app/triage/routes.py`, `triage/clients.py`, `tests/test_clients.py`, `tests/app/test_triage_routes.py`, `infra/envs/backend.env.example`, `infra/compose.prod.yml`, `infra/deploy/refresh-secrets.sh`; delete `app/triage/reasoning_models.py`.

**Produces:** modes `vllm | demo | off`; settings `HERHEALTH_DECISION_MODEL`, `HERHEALTH_ANSWER_MODEL`; `openrouter` rejected at start-up with the valid modes named. `GET /triage/models` and the per-turn `reasoning_model` field removed. `OpenRouterReasoningClient`, `VllmReasoningClient`, `FallbackReasoningClient` and `_decide_via_chat_completions` deleted; helper tests in `test_clients.py` kept.

**Tests:** `test_triage_mode_accepts_vllm_demo_off`; `test_triage_mode_rejects_openrouter_naming_the_valid_modes`; `test_unset_mode_is_off`; plus the existing suites.

**Run:** `make lint && make test`, `uv run mypy services/backend/src/herhealth_backend/app`, `uv run python -c "import herhealth_backend.app.main"`, `git grep -n -i openrouter -- services infra .github` (only migrations, Terraform and comments marked historical may remain).

### Task 6: Removing the selector from the frontend

**Files:** delete `services/frontend/src/components/chat/model-selector.tsx`, `unreviewed-model-notice.tsx`, `src/lib/model-preference.ts`; modify `src/app/(app)/chat/page.tsx`, `src/components/chat/chat-header.tsx`, `src/components/chat/conclusion-card.tsx`, `src/lib/api/triage.ts`, `src/lib/api/types.ts`.

**Run:** the frontend has no `node_modules` on the campus box and the volume has about 2.5 GB free. If `npm ci` fits, run `npm run lint` and `npx tsc --noEmit`; otherwise say so plainly and rely on `frontend.yml` in CI.

### Task 7: The decision measurement as a command

**Files:** create `services/backend/src/herhealth_backend/evaluation/decision_eval.py`, `services/backend/tests/test_decision_eval.py`, `services/data/eval/decision_questions.jsonl` (the 30 questions with a `describes_own_symptoms` flag), `services/data/eval/decision_scripts.jsonl` (ten scripted consultations); modify `services/backend/pyproject.toml` (`herhealth-eval-decisions`).

**Tests:** summary arithmetic on a scripted agent; a multi-turn script reaching a conclusion; a script that runs out of turns reported as unfinished.

### Task 8: Run it, switch the mode, record the result

- [ ] Run `herhealth-eval-decisions` on the campus box; save the output.
- [ ] Set `HERHEALTH_TRIAGE_MODE=vllm` in the untracked `infra/envs/backend.env` (that line only) and remove the `OPENROUTER_API_KEY` and selector lines from it.
- [ ] Write `docs/adr/0018-local-models-decide-and-the-adapter-answers.md` with the before and after numbers and their limits; mark ADR 0012 superseded; update `CLAUDE.md`, `README.md` and `backend.env.example`.
- [ ] `make lint && make test && python3 scripts/check_repo_hygiene.py`.

## Done when

The spec's "Done when" list holds, and ADR 0018 records the before and after measurement.
