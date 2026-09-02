"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Heart,
  MessageCircle,
  Shield,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import { markOnboardingComplete } from "@/lib/onboarding";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

const STEPS: Array<{
  id: string;
  icon: typeof Heart;
  title: string;
  body: string | null;
  bullets?: string[];
}> = [
  {
    id: "welcome",
    icon: Heart,
    title: "Welcome to HerHealthGPT",
    body: "A health companion for when you're not sure what to do next. Describe how you feel in your own words — we'll help you work out how urgently to seek care.",
  },
  {
    id: "how",
    icon: MessageCircle,
    title: "How it works",
    body: null,
    bullets: [
      "You describe your symptoms in a chat",
      "We ask a few clarifying questions if needed",
      "We suggest how soon to see someone, with links to trusted sources",
    ],
  },
  {
    id: "safety",
    icon: Shield,
    title: "Important to know",
    body: "HerHealthGPT provides urgency guidance and information — it never diagnoses. If something feels urgent, seek care right away rather than waiting for a chat reply.",
    bullets: [
      "We may suggest conditions your symptoms could match — that's not a diagnosis",
      "Red-flag symptoms trigger immediate escalation",
      "Always see a clinician if you're worried",
    ],
  },
  {
    id: "sources",
    icon: BookOpen,
    title: "Trusted sources",
    body: "Every claim traces back to reviewed pages from MedlinePlus, Office on Women's Health, NICHD, CDC, and the NHS. Your dashboard will surface articles based on what you discuss.",
    bullets: [
      "Articles open on the original source site",
      "Chat citations quote sources verbatim",
      "We bias toward caution when unsure",
    ],
  },
];

export function OnboardingWizard() {
  const router = useRouter();
  const { user } = useAuth();
  const [step, setStep] = useState(0);

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const Icon = current.icon;

  function finish() {
    if (user) markOnboardingComplete(user.id);
    router.replace(routes.dashboard);
  }

  return (
    <div className="flex min-h-dvh flex-col bg-gradient-to-b from-primary/8 via-background to-background">
      <div className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 py-10 sm:px-6 sm:py-14">
        <div className="mb-8 flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <span
              key={s.id}
              className={cn(
                "h-1.5 rounded-full transition-all",
                i === step
                  ? "w-8 bg-primary"
                  : i < step
                    ? "w-4 bg-primary/40"
                    : "w-4 bg-border",
              )}
            />
          ))}
        </div>

        <div className="flex flex-1 flex-col items-center text-center">
          <span className="mb-6 flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
            <Icon className="size-8" />
          </span>

          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {current.title}
          </h1>

          {current.body ? (
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              {current.body}
            </p>
          ) : null}

          {current.bullets ? (
            <ul className="mt-6 w-full max-w-sm space-y-3 text-left">
              {current.bullets.map((bullet, i) => (
                <li
                  key={bullet}
                  className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-4 py-3 text-sm"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {i + 1}
                  </span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-between">
          {step > 0 ? (
            <Button
              variant="outline"
              className="sm:min-w-[120px]"
              onClick={() => setStep((s) => s - 1)}
            >
              Back
            </Button>
          ) : (
            <div className="hidden sm:block" />
          )}

          {isLast ? (
            <Button size="lg" className="sm:min-w-[200px]" onClick={finish}>
              <Sparkles className="size-4" />
              Go to your dashboard
            </Button>
          ) : (
            <Button
              size="lg"
              className="sm:ml-auto sm:min-w-[160px]"
              onClick={() => setStep((s) => s + 1)}
            >
              Continue
              <ArrowRight className="size-4" />
            </Button>
          )}
        </div>

        {step === 0 ? (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Already know the basics?{" "}
            <button
              type="button"
              onClick={finish}
              className="font-medium text-primary hover:underline"
            >
              Skip to dashboard
            </button>
          </p>
        ) : null}

        {isLast ? (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Or jump straight in —{" "}
            <Link href={routes.chat} className="font-medium text-primary hover:underline">
              start your first chat
            </Link>
          </p>
        ) : null}
      </div>
    </div>
  );
}
