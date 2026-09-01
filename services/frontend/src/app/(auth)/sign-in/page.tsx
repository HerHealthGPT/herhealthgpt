"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthErrorAlert } from "@/components/auth/auth-error-alert";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { signIn } from "@/lib/api/accounts";
import { routes } from "@/lib/routes";
import { CheckCircle2 } from "lucide-react";

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshUser } = useAuth();
  const [email, setEmail] = useState(() => searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const justVerified = searchParams.get("verified") === "1";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const user = await signIn(email, password);
      await refreshUser();

      if (!user.email_verified) {
        router.push(
          `${routes.verifyEmail}?email=${encodeURIComponent(user.email)}`,
        );
        return;
      }

      router.push(routes.dashboard);
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      description="Sign in to open your health chat."
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link
            href={routes.signUp}
            className="font-medium text-primary hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      {justVerified ? (
        <Alert className="border-primary/30 bg-primary/5">
          <CheckCircle2 className="size-4 text-primary" />
          <AlertDescription>
            You&apos;re verified. Sign in with your password to continue.
          </AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-6">
        <AuthErrorAlert error={error} />

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>

          <Field>
            <div className="flex items-center justify-between">
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Link
                href={routes.forgotPassword}
                className="text-sm font-medium text-primary hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <PasswordInput
              id="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>
        </FieldGroup>

        <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <GoogleSignInButton
        onSuccess={async () => {
          await refreshUser();
          router.push(routes.dashboard);
        }}
        onError={setError}
      />
    </AuthShell>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center p-8">Loading…</div>
      }
    >
      <SignInForm />
    </Suspense>
  );
}
