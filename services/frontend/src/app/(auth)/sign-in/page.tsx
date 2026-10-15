"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthErrorAlert } from "@/components/auth/auth-error-alert";
import {
  AuthDivider,
  GoogleSignInButton,
} from "@/components/auth/google-sign-in-button";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { useI18n } from "@/i18n/locale-provider";
import { usePostAuthRedirect } from "@/hooks/use-post-auth-redirect";
import { signIn } from "@/lib/api/accounts";
import { resolvePostAuthRoute } from "@/lib/post-auth-route";
import { isGoogleAuthConfigured } from "@/lib/google-auth";
import { routes } from "@/lib/routes";

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshUser, setUser } = useAuth();
  const redirectAfterAuth = usePostAuthRedirect();
  const { m } = useI18n();
  const [email, setEmail] = useState(() => searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const showGoogle = isGoogleAuthConfigured();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const user = await signIn(email, password);
      setUser(user);
      await refreshUser();
      router.push(await resolvePostAuthRoute(user));
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title={m.auth.signIn.title}
      description={m.auth.signIn.description}
      footer={
        <>
          {m.auth.signIn.noAccount}{" "}
          <Link
            href={routes.signUp}
            className="font-medium text-primary hover:underline"
          >
            {m.auth.signIn.createOne}
          </Link>
        </>
      }
    >
      <div className="space-y-5">
        <AuthErrorAlert error={error} />

        {showGoogle ? (
          <>
            <GoogleSignInButton
              disabled={isSubmitting}
              onSuccess={redirectAfterAuth}
              onError={(message) => setError(new Error(message))}
            />
            <AuthDivider />
          </>
        ) : null}

        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="email">{m.common.email}</FieldLabel>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder={m.common.emailPlaceholder}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>

            <Field>
              <div className="flex items-center justify-between">
                <FieldLabel htmlFor="password">{m.common.password}</FieldLabel>
                <Link
                  href={routes.forgotPassword}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {m.auth.signIn.forgotPassword}
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

          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={isSubmitting}
          >
            {isSubmitting ? m.auth.signIn.submitting : m.auth.signIn.submit}
          </Button>
        </form>
      </div>
    </AuthShell>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center p-8">…</div>
      }
    >
      <SignInForm />
    </Suspense>
  );
}
