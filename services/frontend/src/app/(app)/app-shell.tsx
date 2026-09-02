"use client";

import { usePathname } from "next/navigation";

import { SiteHeader } from "@/components/layout/site-header";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isChat = pathname.startsWith("/chat");
  const isOnboarding =
    pathname.startsWith("/onboarding") || pathname.startsWith("/how-it-works");

  if (isChat || isOnboarding) {
    return <div className="flex h-dvh min-h-0 flex-col">{children}</div>;
  }

  return (
    <>
      <SiteHeader />
      <main className="flex min-w-0 flex-1 flex-col overflow-x-hidden">{children}</main>
    </>
  );
}
