import type { UserSummary } from "@/lib/api/types";
import { displayNameFromEmail } from "@/lib/display-name";

/** Greeting name: saved display name, then a friendly email guess, then null. */
export function userDisplayName(user: UserSummary | null | undefined): string | null {
  if (!user) return null;
  const saved = user.display_name?.trim();
  if (saved) return saved;
  return displayNameFromEmail(user.email);
}
