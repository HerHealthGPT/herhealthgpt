"use client";

import { usePathname } from "next/navigation";

import { SiteHeader } from "@/components/layout/site-header";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isChat = pathname.startsWith("/chat");
  const isOnboarding =
    pathname.startsWith("/onboarding") || pathname.startsWith("/how-it-works");

  if (isChat) {
    return (
      <div className="flex h-dvh min-h-0 flex-col overflow-hidden">
        {children}
      </div>
    );
  }

  // Full-screen like the chat, but it must scroll: the profile step (date of
  // birth, a note, the privacy line, the button) is taller than a phone
  // screen, and with `overflow-hidden` its Continue button was cut off with
  // no way to reach it.
  if (isOnboarding) {
    return <div className="h-dvh overflow-y-auto overscroll-contain">{children}</div>;
  }

  return (
    <>
      <SiteHeader />
      <main className="flex min-w-0 flex-1 flex-col overflow-x-hidden">{children}</main>
    </>
  );
}
