"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthErrorAlert } from "@/components/auth/auth-error-alert";
import {
  AuthDivider,
  GoogleSignInButton,
} from "@/components/auth/google-sign-in-button";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { usePostAuthRedirect } from "@/hooks/use-post-auth-redirect";
import { useI18n } from "@/i18n/locale-provider";
import { register } from "@/lib/api/accounts";
import { isGoogleAuthConfigured } from "@/lib/google-auth";
import { routes } from "@/lib/routes";

export default function SignUpPage() {
  const router = useRouter();
  const redirectAfterAuth = usePostAuthRedirect();
  const { m } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const showGoogle = isGoogleAuthConfigured();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(new Error(m.common.passwordsDoNotMatch));
      return;
    }

    setIsSubmitting(true);

    try {
      const user = await register(email, password);
      router.push(
        `${routes.verifyEmail}?email=${encodeURIComponent(user.email)}`,
      );
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title={m.auth.signUp.title}
      description={
        showGoogle
          ? m.auth.signUp.descriptionWithGoogle
          : m.auth.signUp.description
      }
      footer={
        <>
          {m.auth.signUp.haveAccount}{" "}
          <Link
            href={routes.signIn}
            className="font-medium text-primary hover:underline"
          >
            {m.common.signIn}
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
            <AuthDivider label={m.auth.signUp.divider} />
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
              <FieldLabel htmlFor="password">{m.common.password}</FieldLabel>
              <PasswordInput
                id="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <FieldDescription>{m.common.passwordHint}</FieldDescription>
            </Field>

            <Field>
              <FieldLabel htmlFor="confirm-password">{m.auth.signUp.confirmPassword}</FieldLabel>
              <PasswordInput
                id="confirm-password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
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
            {isSubmitting ? m.auth.signUp.submitting : m.auth.signUp.submit}
          </Button>
        </form>
      </div>

      <p className="text-center text-xs leading-relaxed text-muted-foreground">
        {m.auth.signUp.disclaimer}
      </p>
    </AuthShell>
  );
}
