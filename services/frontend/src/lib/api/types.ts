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

/** Mirrors packages/contracts/src/herhealth_contracts/decision.py TriageDecision.
 *  next_feature_id is intentionally omitted here — it is internal bookkeeping
 *  for the backend's own vocabulary check, never meant for display. */
export type TriageDecision = {
  type: "ask" | "conclude";
  question_text: string | null;
  action_code: ActionCode | null;
  matching_conditions: string[];
  citations: string[];
  red_flag_id: string | null;
  rationale: string;
};

export type TriageTurnResponse = {
  session_id: string;
  decision: TriageDecision;
};
