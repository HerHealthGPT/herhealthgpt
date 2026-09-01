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
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { resetPassword } from "@/lib/api/accounts";
import { routes } from "@/lib/routes";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser } = useAuth();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError(new Error("Passwords do not match."));
      return;
    }

    setIsSubmitting(true);

    try {
      await resetPassword(email, code, newPassword);
      setUser(null);
      toast.success("Password updated. Please sign in with your new password.");
      router.push(`${routes.signIn}?email=${encodeURIComponent(email)}`);
    } catch (submitError) {
      setError(submitError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Set a new password"
      description="Enter the code from your email and choose a new password."
      footer={
        <>
          Need a new code?{" "}
          <Link
            href={routes.forgotPassword}
            className="font-medium text-primary hover:underline"
          >
            Request another
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
            <FieldLabel htmlFor="code">Reset code</FieldLabel>
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
          </Field>

          <Field>
            <FieldLabel htmlFor="new-password">New password</FieldLabel>
            <PasswordInput
              id="new-password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
            <FieldDescription>At least 8 characters.</FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="confirm-password">Confirm new password</FieldLabel>
            <PasswordInput
              id="confirm-password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </Field>
        </FieldGroup>

        <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="flex flex-1 items-center justify-center p-8">Loading…</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
