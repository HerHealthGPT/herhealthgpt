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
  TriageModelList,
  TriageSessionDetail,
  TriageSessionSummary,
  TriageTurnResponse,
} from "./types";

/** POST /triage/turn → 200, or 400/404/409/422/502/503 — see errors.ts's
 *  friendlyTriageError, which turns each of those into on-screen copy.
 */
export function sendTriageTurn(
  sessionId: string | null,
  message: string,
  modelId: string | null = null,
) {
  return apiRequest<TriageTurnResponse>("/triage/turn", {
    method: "POST",
    body: {
      session_id: sessionId,
      message,
      // Omitted unless an evaluator picked a version; the server then runs
      // its own path.
      ...(modelId ? { reasoning_model: modelId } : {}),
    },
  });
}

/** GET /triage/models → the versions on offer; an empty list means none. */
export function listTriageModels() {
  return apiRequest<TriageModelList>("/triage/models");
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
