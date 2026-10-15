"use client";

import { AuthProvider } from "@/contexts/auth-context";
import { Toaster } from "@/components/ui/sonner";
import type { Locale } from "@/i18n/config";
import { LocaleProvider } from "@/i18n/locale-provider";

export function Providers({
  locale,
  children,
}: {
  locale: Locale;
  children: React.ReactNode;
}) {
  return (
    <LocaleProvider initialLocale={locale}>
      <AuthProvider>
        {children}
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </LocaleProvider>
  );
}
