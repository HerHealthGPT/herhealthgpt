/**
 * Accounts API — mirrors services/backend/postman/HerHealthGPT.postman_collection.json
 *
 * All requests use credentials: "include" (httpOnly cookies set by sign-in / Google).
 * Base path is proxied to the backend via Next.js rewrites (/api → localhost:8000).
 */
import { apiRequest } from "./client";
import type { HealthNote, UserSummary } from "./types";

/** POST /accounts/register → 201 */
export function register(email: string, password: string) {
  return apiRequest<UserSummary>("/accounts/register", {
    method: "POST",
    body: { email, password },
  });
}

/** POST /accounts/sign-in → 200 + access_token / refresh_token cookies */
export function signIn(email: string, password: string) {
  return apiRequest<UserSummary>("/accounts/sign-in", {
    method: "POST",
    body: { email, password },
  });
}

/** POST /accounts/sign-in/google → 200 + cookies (503 if Google not configured) */
export function signInWithGoogle(idToken: string) {
  return apiRequest<UserSummary>("/accounts/sign-in/google", {
    method: "POST",
    body: { id_token: idToken },
  });
}

/** POST /accounts/verify-email → 200 + access_token / refresh_token cookies */
export function verifyEmail(email: string, code: string) {
  return apiRequest<UserSummary>("/accounts/verify-email", {
    method: "POST",
    body: { email, code },
  });
}

/** POST /accounts/verify-email/resend → 204 */
export function resendVerification(email: string) {
  return apiRequest<void>("/accounts/verify-email/resend", {
    method: "POST",
    body: { email },
  });
}

/** POST /accounts/reset-password/request → 204 (409 for Google-only accounts) */
export function requestPasswordReset(email: string) {
  return apiRequest<void>("/accounts/reset-password/request", {
    method: "POST",
    body: { email },
  });
}

/** POST /accounts/reset-password → 204, clears all sessions */
export function resetPassword(
  email: string,
  code: string,
  newPassword: string,
) {
  return apiRequest<void>("/accounts/reset-password", {
    method: "POST",
    body: { email, code, new_password: newPassword },
  });
}

/** GET /accounts/me → 200 or 401 */
export function getCurrentUser() {
  return apiRequest<UserSummary>("/accounts/me");
}

/** PATCH /accounts/me → 200 */
export function updateProfile(displayName: string | null) {
  return apiRequest<UserSummary>("/accounts/me", {
    method: "PATCH",
    body: { display_name: displayName },
  });
}

/** PATCH /accounts/me → 200, or 400 if the date is implausible.
 *
 *  Sets BOTH mandatory profile fields in one request, and it has to be one
 *  request: the backend's `display_name` key means "clear the name" when
 *  absent (see UpdateProfileRequest), so a call sending only a date of birth
 *  wipes the name as a side effect. The previous `updateDateOfBirth` did
 *  exactly that — harmless while nothing set a name, a data-loss bug the
 *  moment one is collected.
 *
 *  `dateOfBirth` is ISO `YYYY-MM-DD`. */
export function completeProfile(displayName: string, dateOfBirth: string) {
  return apiRequest<UserSummary>("/accounts/me", {
    method: "PATCH",
    body: { display_name: displayName, date_of_birth: dateOfBirth },
  });
}

/** GET /accounts/health-note → 200 */
export function getHealthNote() {
  return apiRequest<HealthNote>("/accounts/health-note");
}

/** PUT /accounts/health-note → 200. Null or blank clears it. */
export function saveHealthNote(content: string | null) {
  return apiRequest<HealthNote>("/accounts/health-note", {
    method: "PUT",
    body: { content },
  });
}

/** DELETE /accounts/health-note → 204. Deletes the note, not the account. */
export function deleteHealthNote() {
  return apiRequest<void>("/accounts/health-note", { method: "DELETE" });
}

/** POST /accounts/refresh → 204 */
export function refreshSession() {
  return apiRequest<void>("/accounts/refresh", { method: "POST" });
}

/** POST /accounts/sign-out → 204 */
export function signOut() {
  return apiRequest<void>("/accounts/sign-out", { method: "POST" });
}

/** POST /accounts/sign-out-everywhere → 204 */
export function signOutEverywhere() {
  return apiRequest<void>("/accounts/sign-out-everywhere", {
    method: "POST",
  });
}

/** DELETE /accounts/me → 204, permanently deletes the signed-in user */
export function deleteAccount() {
  return apiRequest<void>("/accounts/me", { method: "DELETE" });
}
