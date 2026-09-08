const REASONING_KEY = "herhealth_show_reasoning";

/**
 * Whether to show the model's stated reasoning alongside each turn.
 *
 * Not stored per user, unlike the onboarding flags in `onboarding.ts`: this
 * is a display preference for whoever is at the keyboard, not a fact about
 * an account, and it carries nothing about her health.
 *
 * Defaults to **on**. The reasoning is the model's own `rationale`, which
 * this project's schema requires on every decision precisely so a
 * consultation is auditable without a deterministic trace to read — hiding
 * it by default would make the app less honest than the contract behind it.
 */
export function shouldShowReasoning(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = localStorage.getItem(REASONING_KEY);
    return raw === null ? true : raw === "1";
  } catch {
    // localStorage blocked — fail open, matching onboarding.ts.
    return true;
  }
}

export function setShowReasoning(show: boolean): void {
  try {
    localStorage.setItem(REASONING_KEY, show ? "1" : "0");
  } catch {
    // Preference simply will not persist; the current session still honours it.
  }
}
