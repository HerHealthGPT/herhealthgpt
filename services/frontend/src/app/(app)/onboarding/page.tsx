"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthGuard } from "@/components/auth/auth-guard";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";
import { useAuth } from "@/contexts/auth-context";
import { hasCompletedOnboarding } from "@/lib/onboarding";
import { routes } from "@/lib/routes";

function OnboardingContent() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    if (user && hasCompletedOnboarding(user.id)) {
      router.replace(routes.dashboard);
    }
  }, [user, router]);

  if (user && hasCompletedOnboarding(user.id)) {
    return null;
  }

  return <OnboardingWizard />;
}

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <OnboardingContent />
    </AuthGuard>
  );
}
