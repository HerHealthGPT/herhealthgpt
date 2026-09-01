"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { routes } from "@/lib/routes";
import { useAuth } from "@/contexts/auth-context";

const VERIFY_EMAIL_PATH = routes.verifyEmail;

/**
 * Auth pages are for guests. Signed-in users with a verified email go to the
 * dashboard; unverified users may only stay on verify-email.
 */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading || !user) {
      return;
    }

    if (!user.email_verified) {
      if (pathname !== VERIFY_EMAIL_PATH) {
        router.replace(
          `${VERIFY_EMAIL_PATH}?email=${encodeURIComponent(user.email)}`,
        );
      }
      return;
    }

    router.replace(routes.dashboard);
  }, [isLoading, user, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (user?.email_verified) {
    return null;
  }

  if (user && !user.email_verified && pathname !== VERIFY_EMAIL_PATH) {
    return null;
  }

  return <>{children}</>;
}
