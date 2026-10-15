"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthGuard } from "@/components/auth/auth-guard";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { listTriageSessions } from "@/lib/api/triage";
import {
  hasCompletedOnboarding,
  markOnboardingComplete,
} from "@/lib/onboarding";
import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";

function OnboardingContent() {
  const router = useRouter();
  const { user } = useAuth();
  const { m } = useI18n();

  useEffect(() => {
    if (!user || hasCompletedOnboarding(user.id)) {
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        const sessions = await listTriageSessions();
        if (cancelled) return;
        if (sessions.length > 0) {
          markOnboardingComplete(user.id);
          router.replace(routes.dashboard);
        }
      } catch {
        // Stay on onboarding if we cannot confirm chat history.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [user, router]);

  if (user && hasCompletedOnboarding(user.id)) {
    return <PageLoading message={m.dashboard.toDashboard} />;
  }

  return <OnboardingWizard mode="first-time" />;
}

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <OnboardingContent />
    </AuthGuard>
  );
}
