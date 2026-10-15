"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { DEFAULT_LOCALE, directionOf, isLocale, LOCALE_COOKIE, type Locale } from "@/i18n/config";
import { ar } from "@/i18n/messages/ar";
import { en, type Messages } from "@/i18n/messages/en";
import { fr } from "@/i18n/messages/fr";

const DICTIONARIES: Record<Locale, Messages> = { en, ar, fr };

type LocaleContextValue = {
  locale: Locale;
  dir: "rtl" | "ltr";
  /** The dictionary for the current language. */
  m: Messages;
  setLocale: (locale: Locale) => void;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

export function LocaleProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: React.ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    // A preference about this browser, like the theme: not health data and
    // not tied to the account.
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
    document.documentElement.lang = next;
    document.documentElement.dir = directionOf(next);
  }, []);

  const value = useMemo(
    () => ({ locale, dir: directionOf(locale), m: DICTIONARIES[locale], setLocale }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useI18n(): LocaleContextValue {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useI18n must be used inside LocaleProvider");
  }
  return value;
}

/**
 * The dictionary for the page's current language, for code outside React
 * (error messages, recommendation reasons). Reads `<html lang>`, which the
 * server sets and the switcher updates, so there is no second copy of the
 * choice to keep in step.
 */
export function currentMessages(): Messages {
  const lang = typeof document === "undefined" ? undefined : document.documentElement.lang;
  return DICTIONARIES[isLocale(lang) ? lang : DEFAULT_LOCALE];
}

/** The dictionary for a language, for code outside React (error mapping). */
export function messagesFor(locale: Locale): Messages {
  return DICTIONARIES[locale];
}
