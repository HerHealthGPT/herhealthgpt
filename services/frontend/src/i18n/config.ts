/**
 * The languages the interface is written in, and how one is chosen.
 *
 * No i18n library: Next's own guide (node_modules/next/dist/docs, "Internationalization")
 * uses plain dictionaries, and a new dependency tree is exactly the surface a
 * foreign bundle once reached this repo through (docs/security/0001). The
 * dictionaries in ./messages are typed against the English one, so a missing
 * or misspelled key fails `tsc` instead of rendering blank.
 *
 * The choice lives in a cookie, not in the URL: every route stays where it
 * is, and the server can still render the right language and direction on
 * the first paint. With no cookie, the browser's Accept-Language decides.
 */
export const LOCALES = ["en", "ar", "fr"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_COOKIE = "herhealth_locale";

/** Each language named in itself, which is how a switcher must show it. */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  ar: "العربية",
  fr: "Français",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function directionOf(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

/** The first supported language in an Accept-Language header, by order. */
export function localeFromAcceptLanguage(header: string | null | undefined): Locale {
  if (!header) {
    return DEFAULT_LOCALE;
  }
  const ranked = header
    .split(",")
    .map((part) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.find((param) => param.trim().startsWith("q="));
      return { tag: tag.toLowerCase(), q: q ? Number(q.trim().slice(2)) || 0 : 1 };
    })
    .sort((a, b) => b.q - a.q);
  for (const { tag } of ranked) {
    const base = tag.split("-")[0];
    if (isLocale(base)) {
      return base;
    }
  }
  return DEFAULT_LOCALE;
}
