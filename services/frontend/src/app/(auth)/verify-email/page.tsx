"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { AuthErrorAlert } from "@/components/auth/auth-error-alert";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { resendVerification, verifyEmail } from "@/lib/api/accounts";
import { routes } from "@/lib/routes";

function VerifyEmailForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResending, setIsResending] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await verifyEmail(email, code);
      toast.success("Email verified. Sign in to continue.");
      router.push(
        `${routes.signIn}?email=${encodeURIComponent(email)}&verified=1`,
      );
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResend() {
    setError(null);
    setIsResending(true);

    try {
      await resendVerification(email);
      toast.success("If that address is registered, a new code has been sent.");
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsResending(false);
    }
  }

  return (
    <AuthShell
      title="Verify your email"
      description="We sent a 6-digit code to your email. Enter it below."
      footer={
        <>
          Already verified?{" "}
          <Link
            href={routes.signIn}
            className="font-medium text-primary hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-6">
        <AuthErrorAlert error={error} />

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="code">Verification code</FieldLabel>
            <Input
              id="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              maxLength={6}
              pattern="[0-9]{6}"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
            />
            <FieldDescription>
              Check your email. If you&apos;re running this locally, the code
              may show up in the server console.
            </FieldDescription>
          </Field>
        </FieldGroup>

        <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Verifying…" : "Verify email"}
        </Button>
      </form>

      <div className="text-center">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={isResending || !email}
          onClick={() => void handleResend()}
        >
          {isResending ? "Sending…" : "Resend code"}
        </Button>
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center p-8">Loading…</div>
      }
    >
      <VerifyEmailForm />
    </Suspense>
  );
}
