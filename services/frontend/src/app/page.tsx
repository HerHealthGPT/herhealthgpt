import Link from "next/link";
import { Heart } from "lucide-react";

import { SiteHeader } from "@/components/layout/site-header";
import { ConversationPreview } from "@/components/marketing/conversation-preview";
import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { UrgencyScale } from "@/components/urgency-scale";
import { routes } from "@/lib/routes";

/**
 * The four urgency levels, in severity order — `knowledge/actions.yaml`.
 *
 * Shown as a scale rather than a card grid because it *is* an ordered
 * sequence, which is the only thing that justifies a sequence device. It is
 * also the honest summary of what this product does: it does not tell you
 * what you have, it tells you where on this line you are.
 *
 * Deliberately not coloured with the `--urgency-*` tokens. `globals.css`
 * reserves those saturated reds for result screens, and putting alarm red on
 * a marketing page would be both a token violation and bad manners toward
 * someone who is already worried.
 */
export default function HomePage() {
  return (
    <>
      <SiteHeader />

      <main className="flex-1">
        <section className="border-b border-border/60 bg-gradient-to-b from-accent/40 to-background">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-center lg:gap-16">
            <div>
              {/* The wordmark, as the lockup used in the header and the chat
                  sidebar — heart mark, and GPT in primary. Reads as a logo
                  rather than a styled heading, which is why the coloured
                  fragment belongs here and not in the h1 below. A first-time
                  visitor has to be told what this is called, and the header
                  logo is too small to carry that on its own. */}
              <p className="flex items-center gap-2.5 text-2xl font-bold tracking-tight sm:text-3xl">
                <span
                  className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary sm:size-11"
                  aria-hidden
                >
                  <Heart className="size-5 fill-current sm:size-6" />
                </span>
                {/* The wordmark is ONE flex item, not two. Left as a bare text
                    node plus a <span>, flexbox treats "HerHealth" and "GPT" as
                    separate children and puts the container's gap between
                    them — the name renders broken in half. Same lockup as
                    `site-header.tsx`, which wraps it for this reason. */}
                <span>
                  HerHealth<span className="text-primary">GPT</span>
                </span>
              </p>

              <h1 className="mt-6 max-w-[15ch] text-4xl font-semibold leading-[1.1] tracking-tight text-balance sm:text-5xl">
                Not sure if this needs a doctor?
              </h1>

              <p className="mt-5 max-w-[46ch] text-lg leading-relaxed text-muted-foreground">
                Describe what&apos;s going on in your own words. We ask a couple
                of questions, then tell you how soon to be seen — and show you
                the source we got that from.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button size="lg" asChild className="min-w-[180px]">
                  <Link href={routes.signUp}>Start a chat</Link>
                </Button>
                <Button size="lg" variant="outline" asChild className="min-w-[160px]">
                  <Link href={routes.signIn}>Sign in</Link>
                </Button>
              </div>

              <p className="mt-6 text-sm text-muted-foreground">
                Ask in English, French or Arabic.
              </p>
            </div>

            <div className="lg:pl-4">
              <ConversationPreview />
            </div>
          </div>
        </section>

        <section className="border-b border-border/60 py-14 sm:py-16">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)] lg:items-center lg:gap-16">
              <div>
                <h2 className="max-w-[24ch] text-2xl font-semibold tracking-tight sm:text-3xl">
                  Every answer lands somewhere on this line
                </h2>
                <p className="mt-3 max-w-[52ch] text-muted-foreground">
                  We don&apos;t tell you what you have. We tell you how urgent
                  it is, and why we think so.
                </p>
              </div>
              {/* Its own slot rather than reusing `welcome`: someone who
                  signs up meets that one again on onboarding step 1 and on
                  the dashboard, and the same drawing three times in five
                  minutes reads as a placeholder. */}
              <Illustration
                name="urgency"
                className="max-h-[240px] w-full max-w-[280px] object-contain justify-self-center lg:justify-self-end"
              />
            </div>

            <UrgencyScale className="mt-10" />
          </div>
        </section>

        {/* Evidence, then the ask. The illustration leads on this one so the
            two visual sections alternate sides rather than stacking down one
            edge of the page. */}
        <section className="border-b border-border/60 bg-accent/20 py-14 sm:py-16">
          <div className="mx-auto grid max-w-6xl gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:items-center lg:gap-16">
            <Illustration
              name="sources"
              className="max-h-[240px] w-full max-w-[280px] object-contain justify-self-center lg:justify-self-start"
            />
            <div>
              <h2 className="max-w-[24ch] text-2xl font-semibold tracking-tight sm:text-3xl">
                You can check where every answer came from
              </h2>
              <p className="mt-3 max-w-[52ch] text-muted-foreground">
                Answers quote the NHS, MedlinePlus, the Office on Women&apos;s
                Health, NICHD and the CDC — and link straight to the page.
              </p>
              <Button size="lg" asChild className="mt-6 min-w-[180px]">
                <Link href={routes.signUp}>Start a chat</Link>
              </Button>
            </div>
          </div>
        </section>

        <section className="py-12 sm:py-14">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <p className="max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
              HerHealthGPT gives health information and urgency guidance, never
              a diagnosis, and it can be wrong. It isn&apos;t a doctor. If
              something feels urgent, contact emergency services or go to
              hospital.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
