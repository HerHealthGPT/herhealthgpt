"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";
import { directionOf, isLocale, LOCALE_COOKIE, DEFAULT_LOCALE } from "@/i18n/config";
import { messagesFor } from "@/i18n/locale-provider";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // No provider here: this page replaces the root layout. Read the cookie.
  const chosen =
    typeof document === "undefined"
      ? undefined
      : document.cookie
          .split("; ")
          .find((part) => part.startsWith(`${LOCALE_COOKIE}=`))
          ?.split("=")[1];
  const locale = isLocale(chosen) ? chosen : DEFAULT_LOCALE;
  const m = messagesFor(locale);
  return (
    <html lang={locale} dir={directionOf(locale)}>
      <body className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
        <h1 className="text-xl font-semibold">{m.errorPages.errorHeading}</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          {m.errorPages.globalBody}
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          <Button onClick={reset}>{m.errorPages.tryAgain}</Button>
          <Button variant="outline" asChild>
            <Link href={routes.home}>{m.errorPages.goHome}</Link>
          </Button>
        </div>
      </body>
    </html>
  );
}
