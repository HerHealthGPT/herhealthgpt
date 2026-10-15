"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/contexts/auth-context";
import { routes } from "@/lib/routes";
import { PageLoading } from "@/components/ui/page-loading";
import { useI18n } from "@/i18n/locale-provider";

/**
 * Gates every signed-in page on three things, in order: signed in, email
 * verified, profile complete.
 *
 * The third is new. Name and date of birth are mandatory, and "mandatory"
 * only means anything if something enforces it — so an account missing
 * either is sent to onboarding and cannot reach the chat until both are
 * set. That deliberately catches accounts created before the fields
 * existed: they complete their profile on next sign-in rather than being
 * grandfathered in with a name the app cannot address them by and an age
 * the triage prompt has to spend a question asking for.
 *
 * Onboarding itself is exempt, or the redirect would loop into the page
 * that fixes the problem.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading } = useAuth();
  const { m } = useI18n();

  const onOnboarding = pathname?.startsWith(routes.onboarding) ?? false;
  const profileIncomplete = Boolean(user?.email_verified) && user?.profile_complete === false;

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!user) {
      router.replace(routes.signIn);
      return;
    }

    if (!user.email_verified) {
      router.replace(
        `${routes.verifyEmail}?email=${encodeURIComponent(user.email)}`,
      );
      return;
    }

    if (!user.profile_complete && !onOnboarding) {
      router.replace(routes.onboarding);
    }
  }, [isLoading, user, router, onOnboarding]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">{m.auth.guard.loadingAccount}</p>
        </div>
      </div>
    );
  }

  if (!user || !user.email_verified) {
    return <PageLoading message={m.auth.guard.almostThere} />;
  }

  if (profileIncomplete && !onOnboarding) {
    return <PageLoading message={m.auth.guard.oneThingFirst} />;
  }

  return <>{children}</>;
}
