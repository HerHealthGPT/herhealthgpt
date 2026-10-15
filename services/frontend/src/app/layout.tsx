import type { Metadata } from "next";
import { Inter, Noto_Sans_Arabic } from "next/font/google";

import { Providers } from "@/components/providers";
import { directionOf } from "@/i18n/config";
import { requestLocale, requestMessages } from "@/i18n/server";
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


export async function generateMetadata(): Promise<Metadata> {
  const m = await requestMessages();
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
