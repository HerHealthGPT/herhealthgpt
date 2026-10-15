"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthErrorAlert } from "@/components/auth/auth-error-alert";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { requestPasswordReset } from "@/lib/api/accounts";
import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";

export default function ForgotPasswordPage() {
  const { m } = useI18n();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await requestPasswordReset(email);
      setSubmitted(true);
      toast.success(m.auth.forgot.sent);
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title={m.auth.forgot.title}
      description={
        submitted
          ? m.auth.forgot.descriptionSent
          : m.auth.forgot.description
      }
      footer={
        <>
          {m.auth.forgot.remember}{" "}
          <Link href={routes.signIn} className="font-medium text-primary hover:underline">
            {m.common.signIn}
          </Link>
        </>
      }
    >
      {submitted ? (
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {m.auth.forgot.privacyNote}
          </p>
          <Button asChild className="w-full" size="lg">
            <Link href={`${routes.resetPassword}?email=${encodeURIComponent(email)}`}>
              {m.auth.forgot.enterCode}
            </Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            disabled={isSubmitting}
            onClick={() => {
              void (async () => {
                setError(null);
                setIsSubmitting(true);
                try {
                  await requestPasswordReset(email);
                  toast.success(m.auth.forgot.sent);
                } catch (submitError) {
                  setError(submitError);
                } finally {
                  setIsSubmitting(false);
                }
              })();
            }}
          >
            {isSubmitting ? m.common.sending : m.common.resendCode}
          </Button>
        </div>
      ) : (
        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
          <AuthErrorAlert error={error} />

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
          </FieldGroup>

          <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
            {isSubmitting ? m.common.sending : m.auth.forgot.submit}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
