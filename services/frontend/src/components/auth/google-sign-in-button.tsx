"use client";

import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

import { Separator } from "@/components/ui/separator";
import { signInWithGoogle } from "@/lib/api/accounts";
import type { UserSummary } from "@/lib/api/types";

type GoogleSignInButtonProps = {
  onSuccess: (user: UserSummary) => void;
  onError: (message: string) => void;
};

const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

function GoogleSignInInner({
  onSuccess,
  onError,
}: GoogleSignInButtonProps) {
  if (!googleClientId) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <Separator />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>

      <div className="flex justify-center [&>div]:w-full">
        <GoogleLogin
          theme="outline"
          size="large"
          width="100%"
          text="continue_with"
          onSuccess={async (response) => {
            if (!response.credential) {
              onError("Google sign-in did not return a credential.");
              return;
            }

            try {
              const user = await signInWithGoogle(response.credential);
              onSuccess(user);
            } catch (error) {
              onError(
                error instanceof Error
                  ? error.message
                  : "Google sign-in failed.",
              );
            }
          }}
          onError={() => {
            onError("Google sign-in was cancelled or failed.");
          }}
        />
      </div>
    </div>
  );
}

export function GoogleSignInButton(props: GoogleSignInButtonProps) {
  if (!googleClientId) {
    return null;
  }

  return (
    <GoogleOAuthProvider clientId={googleClientId}>
      <GoogleSignInInner {...props} />
    </GoogleOAuthProvider>
  );
}
