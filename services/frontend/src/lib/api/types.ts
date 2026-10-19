export type UserSummary = {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  /** ISO `YYYY-MM-DD`. Null on accounts created before this was collected —
   *  that is what the post-sign-up step keys off, not a separate flag. */
  date_of_birth: string | null;
  /** Derived server-side from `date_of_birth` on every response, never stored:
   *  a stored band would be wrong the morning after a birthday. One of
   *  knowledge/features.yaml's `age_band` values. */
  age_band: string | null;
  /** Both mandatory profile fields — name and date of birth — are set.
   *  Computed server-side so one definition governs every caller. The app
   *  routes an incomplete profile to the onboarding step and refuses the
   *  chat until it is true; see `ProfileGuard`. */
  profile_complete: boolean;
  /** Whether she has written a health note. The text itself needs its own
   *  request (`getHealthNote`) so clinical free text is not on every poll. */
  has_health_note: boolean;
};

export type HealthNote = {
  content: string | null;
};

/** What a tracker export was read into. Opaque here on purpose: the client
 *  only shows the summary and sends this back unchanged when she confirms,
 *  and the server validates it again (backend ``CycleExtraction``). */
export type CycleExtraction = Record<string, unknown>;

export type CycleDataSummary = {
  source_app: string;
  last_entry: string;
  days_since_last_entry: number;
  /** False once the data is too old to skip questions. */
  fresh: boolean;
  periods_found: number;
  cycle_lengths: number[];
  period_durations: number[];
  /** Feature ids → values her data answers, so they are not asked again. */
  will_answer: Record<string, string>;
};

export type CycleDataPreview = {
  extraction: CycleExtraction;
  summary: CycleDataSummary;
  /** No pain was logged, so ask whether she gets none. */
  ask_about_period_pain: boolean;
};

export type CycleDataStatus = {
  imported_at: string | null;
  summary: CycleDataSummary | null;
};

/** A file she chose to keep (backend ``StoredFileSummary``, ADR 0020). */
export type StoredFile = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  /** When it is deleted automatically: 30 days after upload. */
  expires_at: string;
};

export type PasswordWeakDetail = {
  reasons: string[];
};

export type ValidationErrorItem = {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
};

export type ApiErrorDetail =
  | string
  | PasswordWeakDetail
  | ValidationErrorItem[];

export type ApiErrorBody = {
  detail: ApiErrorDetail;
};

/** Mirrors packages/contracts/src/herhealth_contracts/knowledge.py ActionCode. */
export type ActionCode =
  | "SELF_CARE"
  | "ROUTINE_APPOINTMENT"
  | "URGENT_SAME_DAY"
  | "EMERGENCY";

/** One source the decision actually rests on, resolved server-side.
 *
 *  `citations` on TriageDecision is only a list of content hashes. The
 *  backend resolves each against the passages that turn retrieved (see
 *  routes.py's `_decision_payload`) so the UI can show the sentence itself
 *  and a link to the page, rather than a hash or a bare count.
 *
 *  `url` is null when the passage predates the ingest lock that resolves it
 *  — render the citation label as plain text then, never a dead link. */
export type CitedPassage = {
  id: string;
  text: string;
  citation: string;
  source_id: string;
  url: string | null;
  /** `red_flag` is not a retrieved passage at all — it is the warning-sign
   *  rule a decision fired, carrying that rule's own verbatim source quote.
   *  It exists because `red_flags.yaml` is deliberately never embedded or
   *  retrieved, so a red-flag conclusion has no passage id to cite and would
   *  otherwise display no source whatsoever. It is also the only way NHS
   *  appears: NHS is `citable_only`, so its passages are filtered out of the
   *  served index, but quoting a rule with attribution is exactly what that
   *  licence permits. */
  /** `evidence_row` is an authored row from the evidence grid, reached by
   *  looking it up against her answers rather than by similarity search. It
   *  carries that row's own verbatim source quote. Like `red_flag`, it is the
   *  only way several sources can be credited at all — NHS is `citable_only`,
   *  so its passages are filtered out of the served index even though 47 of
   *  the 140 authored rows are NHS. */
  passage_type:
    | "source_passage"
    | "evidence_statement"
    | "live_fallback"
    | "red_flag"
    | "evidence_row";
};

/** Mirrors packages/contracts/src/herhealth_contracts/decision.py TriageDecision,
 *  plus `cited_passages`, which the API adds alongside the model's own fields
 *  (TriageDecision itself is `extra="forbid"` — what the model may emit and
 *  what this API renders are deliberately different contracts).
 *  next_feature_id is intentionally omitted here — it is internal bookkeeping
 *  for the backend's own vocabulary check, never meant for display.
 *
 *  On a `decline` (an off-scope message — see ADR 0014) every field below
 *  except `rationale` is null or empty, by schema rather than by convention:
 *  action_code, matching_conditions, citations and red_flag_id are all
 *  forbidden there, so render the rationale and nothing else.
 *
 *  On an `inform` (an in-scope question about the subject rather than about
 *  her — see ADR 0016) the answer she reads is `answer_text`, NOT
 *  `rationale`, and `citations` is non-empty unless `comparison_mode` is
 *  set (an evaluation answer from a version that uses no sources). action_code,
 *  matching_conditions and red_flag_id are forbidden there, so there is no
 *  urgency to render and no condition is being attached to her: render the
 *  answer and its sources. */
/** Which model produced a decision. Only on turns stored while the model
 *  selector existed (it was removed in ADR 0018); absent on every new turn.
 *  Stored with the turn, so a reopened chat still shows it. */
export type DecisionReasoningModel = {
  id: string;
  label: string;
  reviewed: boolean;
};

/** When to get help, on an informational answer: read from the knowledge
 *  base by the backend (`care_guidance`), never written by the model. */
export type CareGuidance = {
  topics: { condition_id: string; baseline_action: ActionCode }[];
  warning_signs: { rule_id: string; action: ActionCode; source_id: string }[];
};

export type TriageDecision = {
  type: "ask" | "conclude" | "inform" | "decline";
  question_text: string | null;
  /** The informational answer, on an `inform` and only there. Null on every
   *  other type, and the one field a `decline` and an `inform` do not
   *  share — a decline has nothing to say, an inform has the whole answer. */
  answer_text: string | null;
  action_code: ActionCode | null;
  matching_conditions: string[];
  citations: string[];
  cited_passages?: CitedPassage[];
  red_flag_id: string | null;
  rationale: string;
  reasoning_model?: DecisionReasoningModel;
  /** Set only on an answer from an evaluation version that runs without
   *  sources or checks (`model_a`, `model_b`). Absent on the product's own
   *  path. */
  comparison_mode?: string;
  /** Present on an `inform` from the product's own path. */
  care_guidance?: CareGuidance;
};

/** One version an evaluator may pick. The label is all there is to show. */
export type TriageModelOption = {
  id: string;
  label: string;
};

/** GET /triage/models. `models` is empty on an ordinary deployment. */
export type TriageModelList = {
  models: TriageModelOption[];
  default: string;
};

export type TriageTurnResponse = {
  session_id: string;
  decision: TriageDecision;
};

export type TriageSessionSummary = {
  id: string;
  status: "active" | "concluded";
  created_at: string;
  preview: string;
};

export type TriageSessionMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  decision: TriageDecision | null;
  created_at: string;
};

export type TriageSessionDetail = {
  id: string;
  status: "active" | "concluded";
  created_at: string;
  messages: TriageSessionMessage[];
};
