"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, MessageCircle, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  hasDismissedGettingStarted,
  markGettingStartedDismissed,
} from "@/lib/onboarding";
import { routes } from "@/lib/routes";

type GettingStartedSectionProps = {
  userId: string;
  hasChats: boolean;
  loading?: boolean;
};

/**
 * Shown at most twice in a user's lifetime:
 * 1. Before first chat — a single next-step prompt (not a redundant checklist).
 * 2. Once after first chat — a short "you're all set" message, then hidden forever.
 *
 * Account setup and email verification are covered by onboarding — not repeated here.
 */
export function GettingStartedSection({
  userId,
  hasChats,
  loading,
}: GettingStartedSectionProps) {
  const [showComplete, setShowComplete] = useState(false);

  useEffect(() => {
    if (loading || !hasChats || hasDismissedGettingStarted(userId)) {
      return;
    }
    setShowComplete(true);
  }, [userId, hasChats, loading]);

  function dismissComplete() {
    markGettingStartedDismissed(userId);
    setShowComplete(false);
  }

  if (loading) {
    return null;
  }

  if (showComplete) {
    return (
      <Card className="border-primary/25 bg-primary/5">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-primary" />
            <CardTitle className="text-base">You&apos;re all set</CardTitle>
          </div>
          <CardDescription className="text-sm leading-relaxed">
            Your first health chat is saved. This dashboard will show recent
            conversations and reading from trusted sources as you go.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button size="sm" onClick={dismissComplete}>
            Got it
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (hasChats || hasDismissedGettingStarted(userId)) {
    return null;
  }

  return (
    <Card className="border-dashed border-primary/30 bg-muted/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">One step left</CardTitle>
        <CardDescription className="text-sm leading-relaxed">
          Start a health chat when you&apos;re ready. We&apos;ll ask a few
          questions and help you decide what to do next.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link href={routes.chat}>
            <MessageCircle className="size-4" />
            Start your first chat
            <Sparkles className="size-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
