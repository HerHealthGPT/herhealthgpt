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
 *  `rationale`, and `citations` is guaranteed non-empty. action_code,
 *  matching_conditions and red_flag_id are forbidden there, so there is no
 *  urgency to render and no condition is being attached to her: render the
 *  answer and its sources. */
/** One selectable reasoning model, from GET /triage/models.
 *
 *  `reviewed: false` means this model's decisions are not cleared for use as
 *  guidance — the fine-tuned adapter was trained without clarifying-question
 *  examples, so it concludes too early. Every answer it produces must be
 *  labelled in the UI. */
export type ReasoningModelSummary = {
  id: string;
  label: string;
  description: string;
  reviewed: boolean;
  is_default: boolean;
};

/** Which model produced a decision. Absent when the selector is off, which
 *  is the default deployment. Stored with the turn, so a reopened chat still
 *  shows it. */
export type DecisionReasoningModel = {
  id: string;
  label: string;
  reviewed: boolean;
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
