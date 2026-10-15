import type { Metadata } from "next";
import { Inter, Noto_Sans_Arabic } from "next/font/google";
import { cookies, headers } from "next/headers";

import { Providers } from "@/components/providers";
import {
  directionOf,
  isLocale,
  LOCALE_COOKIE,
  localeFromAcceptLanguage,
  type Locale,
} from "@/i18n/config";
import { messagesFor } from "@/i18n/locale-provider";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

// Inter has no Arabic letters; the browser falls back to this for them.
const arabic = Noto_Sans_Arabic({
  variable: "--font-arabic",
  subsets: ["arabic"],
});

/** The cookie the switcher writes, or else the browser's Accept-Language. */
async function requestLocale(): Promise<Locale> {
  const chosen = (await cookies()).get(LOCALE_COOKIE)?.value;
  if (isLocale(chosen)) {
    return chosen;
  }
  return localeFromAcceptLanguage((await headers()).get("accept-language"));
}

export async function generateMetadata(): Promise<Metadata> {
  const m = messagesFor(await requestLocale());
  return {
    title: {
      default: "HerHealthGPT",
      template: "%s | HerHealthGPT",
    },
    description: m.common.metaDescription,
  };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await requestLocale();
  return (
    <html
      lang={locale}
      dir={directionOf(locale)}
      className={`${inter.variable} ${arabic.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col font-sans">
        <Providers locale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
