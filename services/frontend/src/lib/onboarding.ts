const ONBOARDING_KEY = "herhealth_onboarding_completed";
const GETTING_STARTED_DISMISSED_KEY = "herhealth_getting_started_dismissed";

function readUserList(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    return JSON.parse(raw) as string[];
  } catch {
    return [];
  }
}

function writeUserList(key: string, userIds: string[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(userIds));
  } catch {
    // localStorage blocked — fail open.
  }
}

function markUserFlag(key: string, userId: string): void {
  const list = readUserList(key);
  if (!list.includes(userId)) {
    writeUserList(key, [...list, userId]);
  }
}

/** Per-user onboarding flag in localStorage until a profile field ships. */
export function hasCompletedOnboarding(userId: string): boolean {
  if (typeof window === "undefined") return true;
  return readUserList(ONBOARDING_KEY).includes(userId);
}

export function markOnboardingComplete(userId: string): void {
  markUserFlag(ONBOARDING_KEY, userId);
}

/**
 * Returning users who already have chats should not see first-time onboarding
 * again — e.g. they signed up before the intro shipped.
 */
export function grandfatherReturningUser(userId: string, hasChats: boolean): void {
  if (hasChats && !hasCompletedOnboarding(userId)) {
    markOnboardingComplete(userId);
  }
}

/** True when a brand-new user still needs the one-time intro. */
export function needsFirstTimeOnboarding(
  userId: string,
  hasChats: boolean,
): boolean {
  if (hasChats) {
    grandfatherReturningUser(userId, true);
    return false;
  }
  return !hasCompletedOnboarding(userId);
}

/** User has seen the one-time "you're all set" message after their first chat. */
export function hasDismissedGettingStarted(userId: string): boolean {
  if (typeof window === "undefined") return true;
  return readUserList(GETTING_STARTED_DISMISSED_KEY).includes(userId);
}

export function markGettingStartedDismissed(userId: string): void {
  markUserFlag(GETTING_STARTED_DISMISSED_KEY, userId);
}
