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
import { useI18n } from "@/i18n/locale-provider";

type OnboardingWizardProps = {
  /** First-time intro vs optional review from the menu. */
  mode?: "first-time" | "review";
};

export function OnboardingWizard({ mode = "first-time" }: OnboardingWizardProps) {
  const router = useRouter();
  const { user } = useAuth();
  const { m } = useI18n();
  const o = m.onboarding;
  const [step, setStep] = useState(0);
  const isReview = mode === "review";

  // The details step runs before the intro slides, for anyone whose profile
  // is incomplete. Keyed on `profile_complete` — the server's own definition
  // — rather than on `date_of_birth` alone, now that a name is mandatory
  // too. `AuthGuard` sends incomplete accounts here and refuses every other
  // page until it is done, so this is a hard gate rather than a suggestion.
  const needsProfileDetails = !isReview && user !== null && !user.profile_complete;
  const [detailsDone, setDetailsDone] = useState(false);
  const showProfileDetails = needsProfileDetails && !detailsDone;

  const current = ONBOARDING_STEPS[step];
  const isLast = step === ONBOARDING_STEPS.length - 1;
  const Icon = current.icon;
  const words = o.steps[current.id] ?? current;

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
              {o.aboutYou}
            </h1>
            <p className="mt-3 text-base leading-relaxed text-muted-foreground">
              {o.aboutYouLead}
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
              aria-label={o.close}
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
            <p className="mb-2 text-sm font-medium text-primary">{o.about}</p>
          ) : null}

          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {words.title}
          </h1>

          {words.body ? (
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              {words.body}
            </p>
          ) : null}

          {current.bullets ? (
            <ul className="mt-6 w-full max-w-sm space-y-3 text-start">
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
              {o.back}
            </Button>
          ) : (
            <div className="hidden sm:block" />
          )}

          <Button
            size="lg"
            className="sm:ms-auto sm:min-w-[160px]"
            onClick={handlePrimaryAction}
          >
            {isReview ? (
              isLast ? (
                o.gotIt
              ) : (
                <>
                  {o.continue}
                  <ArrowRight className="size-4 rtl:rotate-180" />
                </>
              )
            ) : isLast ? (
              <>
                <Sparkles className="size-4" />
                {o.goToDashboard}
              </>
            ) : (
              <>
                {o.continue}
                <ArrowRight className="size-4 rtl:rotate-180" />
              </>
            )}
          </Button>
        </div>

        {/* No skip link while the profile is incomplete: AuthGuard sends
            her straight back, so offering the escape only produces a loop. */}
        {!isReview && user?.profile_complete ? (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            {o.readyToGo}{" "}
            <button
              type="button"
              onClick={finishFirstTime}
              className="font-medium text-primary hover:underline"
            >
              {o.skipIntro}
            </button>
          </p>
        ) : (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            {o.readyToChat}{" "}
            <Link href={routes.chat} className="font-medium text-primary hover:underline">
              {o.openChat}
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
