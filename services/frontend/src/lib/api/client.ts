import { parseApiError } from "./errors";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  json?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, json = true, headers, ...rest } = options;

  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    credentials: "include",
    headers: {
      ...(json && body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body:
      body === undefined
        ? undefined
        : json
          ? JSON.stringify(body)
          : (body as BodyInit),
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
