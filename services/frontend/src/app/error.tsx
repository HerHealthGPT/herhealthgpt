"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { routes } from "@/lib/routes";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <Illustration
        name="error"
        className="mb-8 max-h-[220px] w-full max-w-[260px] object-contain"
      />
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-3 max-w-[46ch] text-base leading-relaxed text-muted-foreground">
        An unexpected error occurred. You can try again, or go back to your
        dashboard.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button onClick={reset}>Try again</Button>
        <Button variant="outline" asChild>
          <Link href={routes.dashboard}>Go to dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
