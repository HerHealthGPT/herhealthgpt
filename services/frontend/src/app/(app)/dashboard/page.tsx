"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  MessageCircle,
  Sparkles,
} from "lucide-react";

import { GettingStartedCard } from "@/components/dashboard/getting-started-card";
import { RecentChatsSection } from "@/components/dashboard/recent-chats-section";
import { RecommendedArticlesSection } from "@/components/dashboard/recommended-articles-section";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { conditionLabel } from "@/lib/condition-labels";
import { hasCompletedOnboarding } from "@/lib/onboarding";
import { routes } from "@/lib/routes";

function DashboardContent() {
  const router = useRouter();
  const { user } = useAuth();
  const { data, loading } = useDashboardData();

  const firstName = user?.email?.split("@")[0];

  useEffect(() => {
    if (user && !hasCompletedOnboarding(user.id)) {
      router.replace(routes.onboarding);
    }
  }, [user, router]);

  if (user && !hasCompletedOnboarding(user.id)) {
    return null;
  }

  const heroSubtitle = data.hasChats
    ? data.concludedCount > 0
      ? `You've completed ${data.concludedCount} consultation${data.concludedCount === 1 ? "" : "s"}. Pick up where you left off or start fresh.`
      : "You have a chat in progress. Continue when you're ready."
    : "Tell us how you're feeling — we'll ask a few questions and help you decide what to do next.";

  return (
    <div className="flex flex-1 flex-col">
      <section className="relative overflow-hidden border-b border-border/60">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-accent/20" />
        <div className="absolute -right-16 top-0 size-64 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
          <p className="text-sm text-muted-foreground">Your home</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">
            {firstName ? `Hi, ${firstName}` : "Hi there"}
          </h1>
          <p className="mt-3 max-w-2xl text-muted-foreground">{heroSubtitle}</p>
        </div>
      </section>

      <div className="mx-auto w-full max-w-6xl flex-1 space-y-10 px-4 py-8 sm:px-6 sm:py-10">
        <Card className="overflow-hidden border-primary/25 shadow-lg shadow-primary/5">
          <div className="grid lg:grid-cols-[1fr_auto] lg:items-center">
            <CardHeader className="space-y-4 pb-4 lg:pb-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md shadow-primary/20">
                  <MessageCircle className="size-6" />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-2xl">Health chat</CardTitle>
                    <StatusBadge variant="ready">Ready</StatusBadge>
                  </div>
                  <CardDescription className="mt-1 text-base">
                    {data.hasChats ? "Continue or start a new conversation" : "Your main way to use HerHealthGPT"}
                  </CardDescription>
                </div>
              </div>
              <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                Something on your mind? Start a chat. We&apos;ll ask a few
                questions along the way, suggest conditions your symptoms might
                match, and tell you whether to wait, book a visit, or get seen
                sooner. We&apos;re not a doctor, and this isn&apos;t a diagnosis.
              </p>
            </CardHeader>
            <CardContent className="border-t border-border/60 bg-muted/30 px-6 py-5 lg:border-t-0 lg:border-l lg:py-8">
              <div className="flex flex-col gap-2">
                <Button size="lg" className="w-full min-w-[200px]" asChild>
                  <Link href={routes.chat}>
                    <Sparkles className="size-4" />
                    {data.hasChats ? "Open health chat" : "Start a chat"}
                  </Link>
                </Button>
                {data.hasChats && data.sessions[0]?.status === "active" ? (
                  <Button variant="outline" size="sm" className="w-full" asChild>
                    <Link href={`${routes.chat}?session=${data.sessions[0].id}`}>
                      Continue last chat
                      <ArrowRight className="size-4" />
                    </Link>
                  </Button>
                ) : null}
              </div>
              <p className="mt-3 text-center text-xs text-muted-foreground">
                Usually takes a few minutes.
              </p>
            </CardContent>
          </div>
        </Card>

        <RecentChatsSection sessions={data.sessions} loading={loading} />

        <RecommendedArticlesSection
          articles={data.articles}
          loading={loading}
          personalized={data.exploredTopics.length > 0}
        />

        {data.exploredTopics.length > 0 ? (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">
              Topics from your chats
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Patterns our sources associate with symptoms you&apos;ve discussed — not a diagnosis.
            </p>
            <div className="flex flex-wrap gap-2">
              {data.exploredTopics.map((topic) => (
                <Badge key={topic} variant="secondary" className="px-3 py-1">
                  {conditionLabel(topic)}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        <div className="grid gap-8 lg:grid-cols-2">
          <GettingStartedCard hasChats={data.hasChats} />

          <div className="space-y-5">
            <Card className="border-border/70 transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <CalendarDays className="size-5" />
                  </span>
                  <StatusBadge>Opening soon</StatusBadge>
                </div>
                <CardTitle>Health log</CardTitle>
                <CardDescription className="text-base leading-relaxed">
                  Track your cycle, symptoms, and patterns over time. Useful to
                  bring along to an appointment.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-border/70 bg-gradient-to-br from-secondary/50 to-card">
              <CardHeader>
                <CardTitle className="text-base font-medium text-muted-foreground">
                  Your account
                </CardTitle>
                <CardDescription className="space-y-3 text-base leading-relaxed text-foreground">
                  {loading ? (
                    <Skeleton className="h-5 w-48" />
                  ) : (
                    <span className="block font-medium break-all">{user?.email}</span>
                  )}
                  <span className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="size-4 text-primary" />
                    Email verified
                  </span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  We share information to help you decide what to do. We&apos;re
                  not a doctor. See one if you&apos;re worried.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}
