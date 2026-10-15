"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
import { usePostAuthRedirect } from "@/hooks/use-post-auth-redirect";
import { resendVerification, verifyEmail } from "@/lib/api/accounts";
import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";

function VerifyEmailForm() {
  const searchParams = useSearchParams();
  const redirectAfterAuth = usePostAuthRedirect();
  const { m } = useI18n();
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
      const user = await verifyEmail(email, code);
      toast.success(m.auth.verify.verified);
      await redirectAfterAuth(user);
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
      toast.success(m.auth.verify.resent);
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsResending(false);
    }
  }

  return (
    <AuthShell
      title={m.auth.verify.title}
      description={m.auth.verify.description}
      footer={
        <>
          {m.auth.verify.alreadyVerified}{" "}
          <Link
            href={routes.signIn}
            className="font-medium text-primary hover:underline"
          >
            {m.common.signIn}
          </Link>
        </>
      }
    >
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
        <AuthErrorAlert error={error} />

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="email">{m.common.email}</FieldLabel>
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
            <FieldLabel htmlFor="code">{m.auth.verify.code}</FieldLabel>
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
              {m.auth.verify.codeHint}
            </FieldDescription>
          </Field>
        </FieldGroup>

        <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? m.auth.verify.submitting : m.auth.verify.submit}
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
          {isResending ? m.common.sending : m.common.resendCode}
        </Button>
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center p-8">…</div>
      }
    >
      <VerifyEmailForm />
    </Suspense>
  );
}
