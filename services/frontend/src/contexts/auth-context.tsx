"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api/errors";
import { onSessionExpired } from "@/lib/api/session-events";
import * as accountsApi from "@/lib/api/accounts";
import type { UserSummary } from "@/lib/api/types";
import { currentMessages } from "@/i18n/locale-provider";

type AuthContextValue = {
  user: UserSummary | null;
  isLoading: boolean;
  refreshUser: () => Promise<UserSummary | null>;
  setUser: (user: UserSummary | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await accountsApi.getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        return null;
      }
      // Transient failure (network, 503) — keep existing user if we have one.
      return null;
    }
  }, []);

  useEffect(() => {
    return onSessionExpired(() => {
      setUser(null);
      toast.error(currentMessages().errors.sessionEnded);
    });
  }, []);

  useEffect(() => {
    void (async () => {
      await refreshUser();
      setIsLoading(false);
    })();
  }, [refreshUser]);

  const signOut = useCallback(async () => {
    try {
      await accountsApi.signOut();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      refreshUser,
      setUser,
      signOut,
    }),
    [user, isLoading, refreshUser, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
