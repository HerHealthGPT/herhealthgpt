import { ApiError, networkErrorMessage, parseApiError } from "./errors";
import { emitSessionExpired } from "./session-events";
import { currentMessages } from "@/i18n/locale-provider";
import {
  AUTH_PATHS_WITHOUT_SILENT_REFRESH,
  refreshAccessToken,
} from "./session-refresh";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  json?: boolean;
  /** Internal: set after one silent refresh attempt to avoid loops. */
  _retryAfterRefresh?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, json = true, headers, _retryAfterRefresh, ...rest } = options;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      credentials: "include",
      headers: {
        ...(json && body !== undefined ? { "Content-Type": "application/json" } : {}),
        // The interface language, so the server writes emails in it and can
        // fall back to it for a chat reply (backend app/locale.py).
        ...(typeof document !== "undefined" && document.documentElement.lang
          ? { "Accept-Language": document.documentElement.lang }
          : {}),
        ...headers,
      },
      body:
        body === undefined
          ? undefined
          : json
            ? JSON.stringify(body)
            : (body as BodyInit),
    });
  } catch {
    throw new ApiError(0, networkErrorMessage());
  }

  if (
    response.status === 401 &&
    !_retryAfterRefresh &&
    !AUTH_PATHS_WITHOUT_SILENT_REFRESH.has(path)
  ) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, _retryAfterRefresh: true });
    }
    emitSessionExpired();
  }

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(500, currentMessages().errors.generic);
  }
}

/**
 * GET a file and save it under ``filename``. A plain link would land on a
 * 401 page once the short-lived access token has expired; this refreshes it
 * once, the way ``apiRequest`` does.
 */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const get = () => fetch(`${API_BASE}${path}`, { credentials: "include" });
  let response: Response;
  try {
    response = await get();
    if (response.status === 401 && (await refreshAccessToken())) {
      response = await get();
    }
  } catch {
    throw new ApiError(0, networkErrorMessage());
  }
  if (!response.ok) {
    throw await parseApiError(response);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
