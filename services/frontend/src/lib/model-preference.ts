const MODEL_KEY = "herhealth_reasoning_model";

/**
 * Which reasoning model she last picked for a new chat.
 *
 * Same class of preference as `reasoning-preference.ts`: it lives on this
 * browser, not on the account, and it says nothing about her health. The
 * backend still decides what is actually offered — a stored id that is not
 * on `GET /triage/models` is ignored, never sent.
 */
export function preferredReasoningModel(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(MODEL_KEY);
  } catch {
    return null;
  }
}

export function setPreferredReasoningModel(modelId: string): void {
  try {
    localStorage.setItem(MODEL_KEY, modelId);
  } catch {
    // Preference simply will not persist; the current session still honours it.
  }
}
