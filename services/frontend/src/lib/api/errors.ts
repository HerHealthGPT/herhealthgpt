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

/**
 * Triage's own error detail strings are internal/technical (they mention
 * things like OPENROUTER_API_KEY or "schema validation") — never meant for
 * her to read. Unlike account forms, where the backend's detail is already
 * user-facing copy, a triage error is translated here by status code alone,
 * ignoring whatever the backend actually said.
 */
export function friendlyTriageError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Please try again.";
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
      return "You've been signed out. Please sign in again to continue.";
    default:
      return "Something went wrong. Please try again.";
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
