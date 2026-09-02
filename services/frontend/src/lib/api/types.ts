export type UserSummary = {
  id: string;
  email: string;
  email_verified: boolean;
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
  passage_type: "source_passage" | "evidence_statement" | "live_fallback";
};

/** Mirrors packages/contracts/src/herhealth_contracts/decision.py TriageDecision,
 *  plus `cited_passages`, which the API adds alongside the model's own fields
 *  (TriageDecision itself is `extra="forbid"` — what the model may emit and
 *  what this API renders are deliberately different contracts).
 *  next_feature_id is intentionally omitted here — it is internal bookkeeping
 *  for the backend's own vocabulary check, never meant for display. */
export type TriageDecision = {
  type: "ask" | "conclude";
  question_text: string | null;
  action_code: ActionCode | null;
  matching_conditions: string[];
  citations: string[];
  cited_passages?: CitedPassage[];
  red_flag_id: string | null;
  rationale: string;
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
