"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError } from "@/lib/api/errors";
import * as accountsApi from "@/lib/api/accounts";
import type { UserSummary } from "@/lib/api/types";

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
        try {
          await accountsApi.refreshSession();
          const currentUser = await accountsApi.getCurrentUser();
          setUser(currentUser);
          return currentUser;
        } catch {
          setUser(null);
          return null;
        }
      }

      setUser(null);
      return null;
    }
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
