import { listTriageSessions } from "@/lib/api/triage";
import type { UserSummary } from "@/lib/api/types";
import {
  hasCompletedOnboarding,
  markOnboardingComplete,
} from "@/lib/onboarding";
import { routes } from "@/lib/routes";

/** Where to send someone right after sign-in / sign-up. */
export async function resolvePostAuthRoute(user: UserSummary): Promise<string> {
  if (!user.email_verified) {
    return `${routes.verifyEmail}?email=${encodeURIComponent(user.email)}`;
  }

  if (hasCompletedOnboarding(user.id)) {
    return routes.chat;
  }

  try {
    const sessions = await listTriageSessions();
    if (sessions.length > 0) {
      markOnboardingComplete(user.id);
      return routes.chat;
    }
  } catch {
    // If sessions cannot be loaded, fall through to onboarding.
  }

  return routes.onboarding;
}
