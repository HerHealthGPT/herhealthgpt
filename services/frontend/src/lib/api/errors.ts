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
