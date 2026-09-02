/**
 * Silent access-token refresh via the httpOnly refresh-token cookie.
 *
 * Access tokens expire after 15 minutes (see session_policy.py). The refresh
 * token lasts longer — this module exchanges it for a new access token without
 * sending the user back to sign-in.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

let refreshInFlight: Promise<boolean> | null = null;

export async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE}/accounts/refresh`, {
        method: "POST",
        credentials: "include",
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/** Paths where 401 means bad credentials, not an expired access token. */
export const AUTH_PATHS_WITHOUT_SILENT_REFRESH = new Set([
  "/accounts/refresh",
  "/accounts/sign-in",
  "/accounts/sign-in/google",
  "/accounts/register",
]);
