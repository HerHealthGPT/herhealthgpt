"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { useAuth } from "@/contexts/auth-context";
import { resolvePostAuthRoute } from "@/lib/post-auth-route";
import type { UserSummary } from "@/lib/api/types";

/** Shared redirect after password or Google sign-in / sign-up. */
export function usePostAuthRedirect() {
  const router = useRouter();
  const { refreshUser, setUser } = useAuth();

  return useCallback(
    async (user: UserSummary) => {
      setUser(user);
      await refreshUser();
      router.push(await resolvePostAuthRoute(user));
    },
    [refreshUser, router, setUser],
  );
}
