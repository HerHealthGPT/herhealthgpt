"use client";

import { useState } from "react";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

import { Separator } from "@/components/ui/separator";
import { signInWithGoogle } from "@/lib/api/accounts";
import { friendlyApiError } from "@/lib/api/errors";
import { googleClientId, isGoogleAuthConfigured } from "@/lib/google-auth";
import type { UserSummary } from "@/lib/api/types";

type GoogleSignInButtonProps = {
  onSuccess: (user: UserSummary) => void | Promise<void>;
  onError: (message: string) => void;
  disabled?: boolean;
};

function GoogleSignInInner({
  onSuccess,
  onError,
  disabled,
}: GoogleSignInButtonProps) {
  const [loading, setLoading] = useState(false);
  const clientId = googleClientId();

  if (!clientId) {
    return null;
  }

  async function handleCredential(credential: string) {
    setLoading(true);
    try {
      const user = await signInWithGoogle(credential);
      await onSuccess(user);
    } catch (error) {
      onError(friendlyApiError(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-center [&>div]:w-full">
        <GoogleLogin
          theme="outline"
          size="large"
          width="360"
          text="continue_with"
          shape="rectangular"
          onSuccess={async (response) => {
            if (disabled || loading) {
              return;
            }
            if (!response.credential) {
              onError("Google sign-in did not return a credential.");
              return;
            }
            await handleCredential(response.credential);
          }}
          onError={() => {
            onError("Google sign-in was cancelled or failed.");
          }}
        />
      </div>
      {loading ? (
        <p className="text-center text-xs text-muted-foreground">
          Signing you in…
        </p>
      ) : null}
    </div>
  );
}

export function GoogleSignInButton(props: GoogleSignInButtonProps) {
  if (!isGoogleAuthConfigured()) {
    return null;
  }

  const clientId = googleClientId();
  if (!clientId) {
    return null;
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <GoogleSignInInner {...props} />
    </GoogleOAuthProvider>
  );
}

type AuthDividerProps = {
  label?: string;
};

export function AuthDivider({ label = "or use email" }: AuthDividerProps) {
  return (
    <div className="relative">
      <div className="absolute inset-0 flex items-center">
        <Separator />
      </div>
      <div className="relative flex justify-center text-xs uppercase">
        <span className="bg-card px-2 text-muted-foreground">{label}</span>
      </div>
    </div>
  );
}
