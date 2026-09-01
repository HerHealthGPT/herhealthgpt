"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/contexts/auth-context";
import { routes } from "@/lib/routes";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isLoading } = useAuth();

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
    }
  }, [isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading your account…</p>
        </div>
      </div>
    );
  }

  if (!user || !user.email_verified) {
    return null;
  }

  return <>{children}</>;
}
