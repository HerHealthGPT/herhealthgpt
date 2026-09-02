const STORAGE_KEY = "herhealth_onboarding_completed";

/** Per-user onboarding flag in localStorage until a profile field ships. */
export function hasCompletedOnboarding(userId: string): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const completed = JSON.parse(raw) as string[];
    return completed.includes(userId);
  } catch {
    return false;
  }
}

export function markOnboardingComplete(userId: string): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const completed: string[] = raw ? (JSON.parse(raw) as string[]) : [];
    if (!completed.includes(userId)) {
      completed.push(userId);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(completed));
    }
  } catch {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([userId]));
  }
}
