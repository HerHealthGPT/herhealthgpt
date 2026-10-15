import { currentMessages } from "@/i18n/locale-provider";

import type { ApiErrorBody, ApiErrorDetail } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail;

  constructor(status: number, detail: ApiErrorDetail) {
    super(formatApiError(detail));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Kept for callers that import it; reads the current language each time. */
export function networkErrorMessage(): string {
  return currentMessages().errors.network;
}

/**
 * The account API answers with fixed English sentences. Translated here by
 * their exact text, and passed through unchanged when unknown, so a new
 * sentence on the server shows in English rather than not at all.
 */
function translateServerText(text: string): string {
  return currentMessages().errors.server[text] ?? text;
}

/** One password rule, from the API's English reason. */
function translatePasswordReason(reason: string): string {
  const e = currentMessages().errors;
  if (reason.startsWith("must be at least")) return e.passwordTooShort;
  if (reason.startsWith("must be at most")) return e.passwordTooLong;
  if (reason.startsWith("is too common")) return e.passwordCommon;
  return reason;
}

export function translatePasswordReasons(reasons: string[]): string[] {
  return reasons.map(translatePasswordReason);
}

export function formatApiError(detail: ApiErrorDetail): string {
  if (typeof detail === "string") {
    return translateServerText(detail);
  }

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(" ");
  }

  if ("reasons" in detail && Array.isArray(detail.reasons)) {
    return translatePasswordReasons(detail.reasons).join(" ");
  }

  return currentMessages().errors.generic;
}

/** User-facing message for any API failure (accounts, triage, etc.). */
export function friendlyApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return networkErrorMessage();
  }

  if (error.status === 0) {
    return networkErrorMessage();
  }

  switch (error.status) {
    case 401:
      return currentMessages().errors.sessionEnded;
    case 503:
      if (
        typeof error.detail === "string" &&
        error.detail.toLowerCase().includes("google")
      ) {
        return translateServerText(error.detail);
      }
      return currentMessages().errors.unavailable;
    case 500:
      return currentMessages().errors.generic;
    default:
      return formatApiError(error.detail);
  }
}

/**
 * Triage's own error detail strings are internal/technical — never meant for
 * her to read. Translate by status code alone.
 */
export function friendlyTriageError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return networkErrorMessage();
  }

  switch (error.status) {
    case 503:
      return currentMessages().errors.chatUnavailable;
    case 502:
      return currentMessages().errors.wrongTurn;
    case 504:
      return currentMessages().errors.tooSlow;
    case 404:
    case 409:
      return currentMessages().errors.conversationGone;
    case 422:
      return currentMessages().errors.addWords;
    case 401:
      return currentMessages().errors.sessionEnded;
    case 405:
      return currentMessages().errors.deleteFailed;
    case 500:
      return currentMessages().errors.generic;
    case 0:
      return networkErrorMessage();
    default:
      return friendlyApiError(error);
  }
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let detail: ApiErrorDetail = currentMessages().errors.generic;

  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body.detail !== undefined) {
      detail = body.detail;
    }
  } catch {
    // Response body was not JSON — keep the generic message.
  }

  return new ApiError(response.status, detail);
}
