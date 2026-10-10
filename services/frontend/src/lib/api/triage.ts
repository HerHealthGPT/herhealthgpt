/**
 * Triage API — mirrors services/backend/postman/HerHealthGPT.postman_collection.json's
 * "Triage" folder.
 *
 * One call per turn. The server owns the growing transcript (issue #20 item 6) —
 * the client only ever sends the newest message plus the session id it was
 * last given (or null, to start a new consultation).
 */
import { apiRequest } from "./client";
import type {
  ReasoningModelSummary,
  TriageSessionDetail,
  TriageSessionSummary,
  TriageTurnResponse,
} from "./types";

/** POST /triage/turn → 200, or 400/404/409/422/502/503 — see errors.ts's
 *  friendlyTriageError, which turns each of those into on-screen copy.
 *
 *  `reasoningModel` is an id from `listReasoningModels`; null uses the
 *  deployment default, which is always a reviewed model. A 400 means the id
 *  is not offered here. */
export function sendTriageTurn(
  sessionId: string | null,
  message: string,
  reasoningModel: string | null = null,
) {
  return apiRequest<TriageTurnResponse>("/triage/turn", {
    method: "POST",
    body: {
      session_id: sessionId,
      message,
      reasoning_model: reasoningModel,
    },
  });
}

/** GET /triage/models → 200. Empty unless HERHEALTH_MODEL_SELECTOR is on,
 *  in which case the UI shows no model control at all. */
export function listReasoningModels() {
  return apiRequest<ReasoningModelSummary[]>("/triage/models");
}

export function listTriageSessions() {
  return apiRequest<TriageSessionSummary[]>("/triage/sessions");
}

export function getTriageSession(sessionId: string) {
  return apiRequest<TriageSessionDetail>(`/triage/sessions/${sessionId}`);
}

export function deleteTriageSession(sessionId: string) {
  return apiRequest<void>(`/triage/sessions/${sessionId}`, { method: "DELETE" });
}
