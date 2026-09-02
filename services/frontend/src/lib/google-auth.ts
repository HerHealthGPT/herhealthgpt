/** Same OAuth client ID as backend ``HERHEALTH_GOOGLE_CLIENT_ID``. */
export function googleClientId(): string | undefined {
  const id = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
  return id || undefined;
}

export function isGoogleAuthConfigured(): boolean {
  return Boolean(googleClientId());
}
