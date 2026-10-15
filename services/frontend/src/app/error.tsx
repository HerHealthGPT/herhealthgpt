"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { m } = useI18n();
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <Illustration
        name="error"
        className="mb-8 max-h-[220px] w-full max-w-[260px] object-contain"
      />
      <h1 className="text-2xl font-semibold tracking-tight">{m.errorPages.errorHeading}</h1>
      <p className="mt-3 max-w-[46ch] text-base leading-relaxed text-muted-foreground">
        {m.errorPages.errorBody}
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button onClick={reset}>{m.errorPages.tryAgain}</Button>
        <Button variant="outline" asChild>
          <Link href={routes.dashboard}>{m.errorPages.goToDashboard}</Link>
        </Button>
      </div>
    </div>
  );
}
