"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Sparkles, X } from "lucide-react";

import { ProfileDetailsStep } from "@/components/onboarding/profile-details-step";
import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { useAuth } from "@/contexts/auth-context";
import { ONBOARDING_STEPS } from "@/lib/onboarding-content";
import { markOnboardingComplete } from "@/lib/onboarding";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

type OnboardingWizardProps = {
  /** First-time intro vs optional review from the menu. */
  mode?: "first-time" | "review";
};

export function OnboardingWizard({ mode = "first-time" }: OnboardingWizardProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const isReview = mode === "review";

  // The details step runs before the intro slides, and only for a first-time
  // user who has no date of birth yet. Accounts predating this field see it
  // too, on their next visit to onboarding, but are never blocked elsewhere
  // in the app — see ADR 0015 on why it is not a hard gate.
  const needsProfileDetails = !isReview && user !== null && user.date_of_birth === null;
  const [detailsDone, setDetailsDone] = useState(false);
  const showProfileDetails = needsProfileDetails && !detailsDone;

  const current = ONBOARDING_STEPS[step];
  const isLast = step === ONBOARDING_STEPS.length - 1;
  const Icon = current.icon;

  function finishFirstTime() {
    if (user) markOnboardingComplete(user.id);
    router.replace(routes.dashboard);
  }

  function closeReview() {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.replace(routes.dashboard);
  }

  function handlePrimaryAction() {
    if (isReview) {
      if (isLast) {
        closeReview();
        return;
      }
      setStep((currentStep) => currentStep + 1);
      return;
    }

    if (isLast) {
      finishFirstTime();
      return;
    }
    setStep((currentStep) => currentStep + 1);
  }

  if (showProfileDetails) {
    return (
      <div className="flex min-h-dvh flex-col bg-gradient-to-b from-primary/8 via-background to-background">
        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 py-10 sm:px-6 sm:py-14">
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              A little about you
            </h1>
            <p className="mt-3 text-base leading-relaxed text-muted-foreground">
              Two quick things, so we can give you better guidance and ask you
              fewer questions later.
            </p>
          </div>

          <ProfileDetailsStep onComplete={() => setDetailsDone(true)} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-gradient-to-b from-primary/8 via-background to-background">
      <div className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 py-10 sm:px-6 sm:py-14">
        {isReview ? (
          <div className="mb-4 flex justify-end">
            <Button
              variant="ghost"
              size="icon"
              onClick={closeReview}
              aria-label="Close"
            >
              <X className="size-5" />
            </Button>
          </div>
        ) : null}

        <div className="mb-8 flex items-center justify-center gap-2">
          {ONBOARDING_STEPS.map((item, index) => (
            <span
              key={item.id}
              className={cn(
                "h-1.5 rounded-full transition-all",
                index === step
                  ? "w-8 bg-primary"
                  : index < step
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

          {isReview && step === 0 ? (
            <p className="mb-2 text-sm font-medium text-primary">About HerHealthGPT</p>
          ) : null}

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
              {current.bullets.map((bullet, index) => (
                <li
                  key={bullet}
                  className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 px-4 py-3 text-sm"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {index + 1}
                  </span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {/* Fills the tall column this centred layout leaves under short
              copy — the emptiest space in the app. `mt-auto` pushes it to
              the bottom of the free area rather than leaving a gap beneath
              it, and it renders nothing at all when the file is absent, so
              the step still reads correctly on a fresh clone. */}
          {current.illustration ? (
            <Illustration
              name={current.illustration}
              className="mt-auto max-h-[22vh] w-full max-w-[220px] shrink object-contain pt-6"
            />
          ) : null}
        </div>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-between">
          {step > 0 ? (
            <Button
              variant="outline"
              className="sm:min-w-[120px]"
              onClick={() => setStep((currentStep) => currentStep - 1)}
            >
              Back
            </Button>
          ) : (
            <div className="hidden sm:block" />
          )}

          <Button
            size="lg"
            className="sm:ml-auto sm:min-w-[160px]"
            onClick={handlePrimaryAction}
          >
            {isReview ? (
              isLast ? (
                "Got it"
              ) : (
                <>
                  Continue
                  <ArrowRight className="size-4" />
                </>
              )
            ) : isLast ? (
              <>
                <Sparkles className="size-4" />
                Go to my dashboard
              </>
            ) : (
              <>
                Continue
                <ArrowRight className="size-4" />
              </>
            )}
          </Button>
        </div>

        {!isReview ? (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Ready to go?{" "}
            <button
              type="button"
              onClick={finishFirstTime}
              className="font-medium text-primary hover:underline"
            >
              Skip intro — go to dashboard
            </button>
          </p>
        ) : (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Ready to chat?{" "}
            <Link href={routes.chat} className="font-medium text-primary hover:underline">
              Open health chat
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
