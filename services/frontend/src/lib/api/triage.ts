/**
 * Triage API — mirrors services/backend/postman/HerHealthGPT.postman_collection.json's
 * "Triage" folder.
 *
 * One call per turn. The server owns the growing transcript (issue #20 item 6) —
 * the client only ever sends the newest message plus the session id it was
 * last given (or null, to start a new consultation).
 */
import { apiRequest } from "./client";
import type { TriageTurnResponse } from "./types";

/** POST /triage/turn → 200, or 404/409/422/502/503 — see errors.ts's
 *  friendlyTriageError, which turns each of those into on-screen copy. */
export function sendTriageTurn(sessionId: string | null, message: string) {
  return apiRequest<TriageTurnResponse>("/triage/turn", {
    method: "POST",
    body: { session_id: sessionId, message },
  });
}
