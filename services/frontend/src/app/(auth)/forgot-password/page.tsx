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

export default function ForgotPasswordPage() {
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
      toast.success("If that address is registered, a reset code has been sent.");
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      description={
        submitted
          ? "Check your inbox for a 6-digit reset code, then continue to set a new password."
          : "Enter your email and we'll send you a reset code if an account exists."
      }
      footer={
        <>
          Remember your password?{" "}
          <Link href={routes.signIn} className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      {submitted ? (
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            We won&apos;t tell you whether an email is registered. If you got
            a code, use the button below to enter it.
          </p>
          <Button asChild className="w-full" size="lg">
            <Link href={`${routes.resetPassword}?email=${encodeURIComponent(email)}`}>
              Enter reset code
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
                  toast.success(
                    "If that address is registered, a reset code has been sent.",
                  );
                } catch (submitError) {
                  setError(submitError);
                } finally {
                  setIsSubmitting(false);
                }
              })();
            }}
          >
            {isSubmitting ? "Sending…" : "Resend code"}
          </Button>
        </div>
      ) : (
        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
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
          </FieldGroup>

          <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "Sending…" : "Send reset code"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
