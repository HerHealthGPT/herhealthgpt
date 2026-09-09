import Link from "next/link";

import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { routes } from "@/lib/routes";

export const metadata = {
  title: "Page not found",
};

/**
 * The 404. There was no `not-found.tsx` before this, so a mistyped or stale
 * URL fell through to Next's unstyled default — no header, no way back, and
 * nothing identifying the app.
 *
 * Written as directions rather than an apology: someone who lands here
 * wants the way out, not a paragraph about what went wrong.
 */
export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
        <Illustration
          name="not-found"
          className="mb-8 max-h-[240px] w-full max-w-[280px] object-contain"
        />

        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          We can&apos;t find that page
        </h1>
        <p className="mt-3 max-w-[46ch] text-base leading-relaxed text-muted-foreground">
          The link may be out of date, or the address may have a typo in it.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button size="lg" asChild className="min-w-[180px]">
            <Link href={routes.dashboard}>Go to dashboard</Link>
          </Button>
          <Button size="lg" variant="outline" asChild className="min-w-[160px]">
            <Link href={routes.chat}>Start a chat</Link>
          </Button>
        </div>
      </main>
    </>
  );
}
