"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

export default function HowItWorksPage() {
  return (
    <AuthGuard>
      <OnboardingWizard mode="review" />
    </AuthGuard>
  );
}
