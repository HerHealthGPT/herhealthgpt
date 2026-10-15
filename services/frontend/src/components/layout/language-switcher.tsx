"use client";

import { Languages } from "lucide-react";

import { isLocale, LOCALE_NAMES, LOCALES } from "@/i18n/config";
import { useI18n } from "@/i18n/locale-provider";
import { cn } from "@/lib/utils";

/**
 * Picks the interface language. Each option is written in its own language,
 * so someone who cannot read the current one can still find theirs.
 *
 * A native `select`: a real control on a phone and with a keyboard. The
 * choice is kept in a cookie (see i18n/config.ts), so it survives a reload
 * and the server renders the next page in it.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, m, setLocale } = useI18n();

  return (
    <label className={cn("flex shrink-0 items-center gap-1.5 text-sm", className)}>
      <Languages className="size-4 text-muted-foreground" aria-hidden />
      <span className="sr-only">{m.common.language}</span>
      <select
        className="h-8 rounded-md border border-input bg-background px-1.5 text-sm"
        value={locale}
        onChange={(event) => {
          if (isLocale(event.target.value)) {
            setLocale(event.target.value);
          }
        }}
      >
        {LOCALES.map((code) => (
          <option key={code} value={code} lang={code}>
            {LOCALE_NAMES[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
