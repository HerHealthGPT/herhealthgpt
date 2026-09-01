/**
 * Accounts API — mirrors services/backend/postman/HerHealthGPT.postman_collection.json
 *
 * All requests use credentials: "include" (httpOnly cookies set by sign-in / Google).
 * Base path is proxied to the backend via Next.js rewrites (/api → localhost:8000).
 */
import { apiRequest } from "./client";
import type { UserSummary } from "./types";

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

/** POST /accounts/verify-email → 200 */
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
