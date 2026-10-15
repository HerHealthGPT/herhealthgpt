import { cookies, headers } from "next/headers";

import { isLocale, LOCALE_COOKIE, localeFromAcceptLanguage, type Locale } from "@/i18n/config";
import { ar } from "@/i18n/messages/ar";
import { en, type Messages } from "@/i18n/messages/en";
import { fr } from "@/i18n/messages/fr";

/**
 * The language for this request, for server components, which cannot use
 * the `useI18n` hook: the cookie the switcher writes, or else the browser's
 * Accept-Language. Reading either makes the page render per request.
 */
export async function requestLocale(): Promise<Locale> {
  const chosen = (await cookies()).get(LOCALE_COOKIE)?.value;
  if (isLocale(chosen)) {
    return chosen;
  }
  return localeFromAcceptLanguage((await headers()).get("accept-language"));
}

const DICTIONARIES: Record<Locale, Messages> = { en, ar, fr };

/** The dictionary for this request's language. */
export async function requestMessages(): Promise<Messages> {
  return DICTIONARIES[await requestLocale()];
}
