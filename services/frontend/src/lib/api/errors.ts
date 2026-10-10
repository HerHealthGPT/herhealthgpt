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

export const NETWORK_ERROR_MESSAGE =
  "We couldn't reach the server. Check your connection and try again.";

export function formatApiError(detail: ApiErrorDetail): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(" ");
  }

  if ("reasons" in detail && Array.isArray(detail.reasons)) {
    return detail.reasons.join(" ");
  }

  return "Something went wrong. Please try again.";
}

/** User-facing message for any API failure (accounts, triage, etc.). */
export function friendlyApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return NETWORK_ERROR_MESSAGE;
  }

  if (error.status === 0) {
    return NETWORK_ERROR_MESSAGE;
  }

  switch (error.status) {
    case 401:
      return "Your session ended. Please sign in again to continue.";
    case 503:
      if (
        typeof error.detail === "string" &&
        error.detail.toLowerCase().includes("google")
      ) {
        return error.detail;
      }
      return "Service temporarily unavailable. Try again shortly.";
    case 500:
      return "Something went wrong. Please try again.";
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
    return NETWORK_ERROR_MESSAGE;
  }

  switch (error.status) {
    case 503:
      return "Chat isn't available right now. Please try again in a little while.";
    case 502:
      return "That took a wrong turn on our end. Please try again.";
    case 504:
      return "That's taking longer than it should. Please try again.";
    case 404:
    case 409:
      return "That conversation isn't available anymore. Start a new chat to continue.";
    case 422:
      return "Try adding a few words about what's going on.";
    case 401:
      return "Your session ended. Please sign in again to continue.";
    case 405:
      return "Couldn't delete that chat — the server may need a restart to pick up the latest update.";
    case 500:
      return "Something went wrong. Please try again.";
    case 0:
      return NETWORK_ERROR_MESSAGE;
    default:
      return friendlyApiError(error);
  }
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let detail: ApiErrorDetail = "Something went wrong. Please try again.";

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
