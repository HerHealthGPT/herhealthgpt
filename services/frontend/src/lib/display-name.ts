import type { UserSummary } from "@/lib/api/types";

/** Friendly first name from email — not a real profile name. */
export function displayNameFromEmail(email?: string | null): string | null {
  if (!email) return null;
  const local = email.split("@")[0]?.trim();
  if (!local) return null;
  const segment = local.split(/[._+-]/)[0]?.trim();
  if (!segment) return null;
  return segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase();
}

/** Greeting name: saved display name, then a friendly email guess, then null. */
export function userDisplayName(user: UserSummary | null | undefined): string | null {
  if (!user) return null;
  const saved = user.display_name?.trim();
  if (saved) return saved;
  return displayNameFromEmail(user.email);
}
