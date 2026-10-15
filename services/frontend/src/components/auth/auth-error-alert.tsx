"use client";

import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { formatApiError } from "@/lib/api/errors";
import type { ApiErrorDetail } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

type AuthErrorAlertProps = {
  error: unknown;
};

function isPasswordWeakDetail(
  detail: ApiErrorDetail,
): detail is { reasons: string[] } {
  return (
    typeof detail === "object" &&
    detail !== null &&
    !Array.isArray(detail) &&
    "reasons" in detail
  );
}

export function AuthErrorAlert({ error }: AuthErrorAlertProps) {
  const { m } = useI18n();
  if (!error) {
    return null;
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    isPasswordWeakDetail((error as { detail: ApiErrorDetail }).detail)
  ) {
    const reasons = (error as { detail: { reasons: string[] } }).detail
      .reasons;

    return (
      <Alert variant="destructive">
        <AlertCircle className="size-4" />
        <AlertDescription>
          <p className="font-medium">{m.auth.errors.passwordRequirements}</p>
          <ul className="mt-2 list-inside list-disc space-y-1">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </AlertDescription>
      </Alert>
    );
  }

  const message =
    error instanceof Error ? formatApiErrorFromUnknown(error) : String(error);

  return (
    <Alert variant="destructive">
      <AlertCircle className="size-4" />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function formatApiErrorFromUnknown(error: Error): string {
  if ("detail" in error) {
    return formatApiError((error as Error & { detail: ApiErrorDetail }).detail);
  }
  return error.message;
}
