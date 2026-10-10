import Link from "next/link";
import { Heart } from "lucide-react";

import { Illustration } from "@/components/ui/illustration";

type AuthShellProps = {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

/**
 * The frame around every sign-in, sign-up and password screen.
 *
 * Rebuilt 2026-09-10 because the previous version was mostly air. What
 * changed and why:
 *
 * - **`justify-between` on a full-height column is gone.** It pinned the
 *   logo to the top edge and the small print to the bottom, so on a tall
 *   monitor the panel's own content was separated by several hundred pixels
 *   of nothing. The column is centred now and the small print sits with the
 *   content it qualifies.
 * - **The two blurred gradient blobs are gone.** They cost a repaint on
 *   every scroll and said nothing; one flat tint reads calmer.
 * - **The card no longer floats.** `min-h-full` plus centring on a viewport
 *   with a short form left the card marooned; the form column now has real
 *   padding and stops stretching.
 * - **Vertical rhythm tightened** from `space-y-6` throughout to a 4/5
 *   scale, and the `shadow-xl` dropped to `shadow-sm`. A heavy shadow on a
 *   pale card was doing the work a border should do.
 *
 * The side panel is `lg:` and up only. Below that it would push the form —
 * the entire reason anyone is on this page — below the fold.
 */
export function AuthShell({
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  return (
    <div className="flex min-h-full flex-1">
      <aside className="relative hidden w-[42%] max-w-lg shrink-0 flex-col justify-center border-r border-border/60 bg-accent/30 px-10 py-12 lg:flex xl:px-14">
        <Link href="/" className="mb-10 flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Heart className="size-5 fill-current" aria-hidden />
          </span>
          <span className="text-xl font-bold tracking-tight">
            HerHealth<span className="text-primary">GPT</span>
          </span>
        </Link>

        <h2 className="max-w-[18ch] text-3xl font-semibold leading-tight tracking-tight text-balance">
          Not sure if you should see someone?
        </h2>
        <p className="mt-4 max-w-[42ch] text-base leading-relaxed text-muted-foreground">
          Describe what&apos;s going on in your own words. We&apos;ll ask a
          couple of questions, then tell you how soon to be seen — and show
          you where that came from.
        </p>

        {/* Fills the space the old layout left blank. Renders nothing until
            the SVG is dropped in (public/illustrations/README.md), so the
            panel has to look finished without it — hence the copy above
            carrying the panel on its own. */}
        <Illustration
          name="onboarding"
          className="mt-10 max-h-[30vh] w-full max-w-[280px] self-start object-contain"
        />

        <p className="mt-10 max-w-[42ch] text-xs leading-relaxed text-muted-foreground">
          Urgency guidance and health information, never a diagnosis. Ask in
          English, French or Arabic.
        </p>
      </aside>

      <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 sm:px-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Heart className="size-4 fill-current" aria-hidden />
            </span>
            <span className="text-lg font-bold tracking-tight">
              HerHealth<span className="text-primary">GPT</span>
            </span>
          </div>

          {/* No Card wrapper. On the desktop split the panel already frames
              this column, and a bordered card inside a framed column is two
              boxes doing one job. */}
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>

          <div className="mt-6">{children}</div>

          {footer ? (
            <p className="mt-6 text-sm text-muted-foreground">{footer}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
