"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { CycleDataCard } from "@/components/account/cycle-data-import";
import { DeleteAccountSection } from "@/components/account/delete-account-section";
import { HealthDetailsForm } from "@/components/account/health-details-form";
import { ProfileSettingsForm } from "@/components/account/profile-settings-form";
import { useI18n } from "@/i18n/locale-provider";

function AccountSettingsContent() {
  const { m } = useI18n();
  return (
    <div className="flex flex-1 flex-col">
      <section className="border-b border-border/60 bg-muted/20">
        <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {m.account.title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {m.account.lead}
          </p>
        </div>
      </section>

      <div className="mx-auto w-full max-w-2xl flex-1 space-y-8 px-4 py-8 sm:px-6 sm:py-10">
        <ProfileSettingsForm />
        <HealthDetailsForm />
        <CycleDataCard />
        <DeleteAccountSection />
      </div>
    </div>
  );
}

export default function AccountSettingsPage() {
  return (
    <AuthGuard>
      <AccountSettingsContent />
    </AuthGuard>
  );
}
