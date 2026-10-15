"use client";

import { useI18n } from "@/i18n/locale-provider";

type PageLoadingProps = {
  message?: string;
};

export function PageLoading({ message }: PageLoadingProps) {
  const { m } = useI18n();
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="flex flex-col items-center gap-3">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">{message ?? m.common.loading}</p>
      </div>
    </div>
  );
}
