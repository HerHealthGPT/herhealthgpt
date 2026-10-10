"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CalendarDays,
  MessageCircle,
  Sparkles,
} from "lucide-react";

import { GettingStartedSection } from "@/components/dashboard/getting-started-card";
import { RecentChatsSection } from "@/components/dashboard/recent-chats-section";
import { RecommendedArticlesSection } from "@/components/dashboard/recommended-articles-section";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Illustration } from "@/components/ui/illustration";
import { UrgencyScale } from "@/components/urgency-scale";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageLoading } from "@/components/ui/page-loading";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { conditionLabel } from "@/lib/condition-labels";
import { userDisplayName } from "@/lib/display-name";
import { needsFirstTimeOnboarding } from "@/lib/onboarding";
import { routes } from "@/lib/routes";

function DashboardContent() {
  const router = useRouter();
  const { user } = useAuth();
  const { data, loading, error, reload } = useDashboardData();

  const greetingName = userDisplayName(user);

  useEffect(() => {
    if (!user || loading) {
      return;
    }

    if (needsFirstTimeOnboarding(user.id, data.hasChats)) {
      router.replace(routes.onboarding);
    }
  }, [user, router, loading, data.hasChats]);

  if (user && !loading && needsFirstTimeOnboarding(user.id, data.hasChats)) {
    return <PageLoading message="One moment…" />;
  }

  const heroSubtitle = data.activeSession
    ? "You have a chat in progress. Pick up where you left off, or start fresh."
    : data.hasChats
      ? data.concludedCount > 0
        ? `You've completed ${data.concludedCount} consultation${data.concludedCount === 1 ? "" : "s"}. Start a new chat anytime.`
        : "Your chats are saved here. Open one or start something new."
      : "Tell us how you're feeling — we'll ask a few questions and help you decide what to do next.";

  return (
    <div className="flex flex-1 flex-col">
      {/* The widest band on the page, and it was text on a gradient with a
          blur blob in the corner. The illustration sits here rather than
          inside the chat card below, and unconditionally: keying it to
          "no chats yet" meant the space only ever filled for a brand-new
          account and stayed empty for everyone who actually uses the app. */}
      <section className="relative overflow-hidden border-b border-border/60 bg-gradient-to-br from-primary/10 via-background to-accent/20">
        <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-10 sm:px-6 sm:py-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,15rem)] lg:items-center lg:gap-12">
          <div>
            <p className="text-sm text-muted-foreground">Your home</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight sm:text-4xl">
              {greetingName ? `Hi, ${greetingName}` : "Hi there"}
            </h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">{heroSubtitle}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              <Link
                href={routes.howItWorks}
                className="font-medium text-primary hover:underline"
              >
                How this works
              </Link>
              {" · "}
              <Link
                href={routes.settings}
                className="font-medium text-primary hover:underline"
              >
                Account settings
              </Link>
            </p>
          </div>

          {/* Every width, every state. It was `hidden lg:block`, which meant
              the whole point of it — the page not being a wall of text —
              stopped applying on the devices most of this audience uses. */}
          <Illustration
            name="welcome"
            className="order-first mx-auto max-h-[140px] w-full max-w-[180px] object-contain sm:max-h-[160px] lg:order-none lg:max-h-[180px] lg:max-w-[220px] lg:justify-self-end"
          />
        </div>
      </section>

      <div className="mx-auto w-full max-w-6xl flex-1 space-y-10 px-4 py-8 sm:px-6 sm:py-10">
        {error ? (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              <span>{error}</span>
              <Button size="sm" variant="outline" onClick={reload}>
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}

        {user ? (
          <GettingStartedSection
            userId={user.id}
            hasChats={data.hasChats}
            loading={loading}
          />
        ) : null}

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
                Something on your mind? Describe it in your own words. We&apos;ll
                ask a few follow-up questions if needed, then suggest how soon to
                see someone — with links to trusted sources. This isn&apos;t a
                diagnosis.
              </p>
            </CardHeader>
            <CardContent className="border-t border-border/60 bg-muted/30 px-6 py-5 lg:border-t-0 lg:border-l lg:py-8">
              <Illustration
                name="conversation"
                className="mx-auto mb-4 max-h-[130px] w-full max-w-[180px] object-contain"
              />
              <div className="flex flex-col gap-2">
                <Button size="lg" className="w-full min-w-[200px]" asChild>
                  <Link href={routes.chat}>
                    <Sparkles className="size-4" />
                    {data.hasChats ? "Open health chat" : "Start a chat"}
                  </Link>
                </Button>
                {data.activeSession ? (
                  <Button variant="outline" size="sm" className="w-full" asChild>
                    <Link href={`${routes.chat}?session=${data.activeSession.id}`}>
                      Continue your chat
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

        {/* What a finished chat's verdict actually meant. Placed after
            Recent chats so it reads as a key to the list above rather than
            as marketing, and shown unconditionally — the four levels do not
            depend on whether this account has used any of them. */}
        <section>
          <h2 className="text-lg font-semibold tracking-tight">
            The four answers a chat can end with
          </h2>
          <p className="mt-1 max-w-[62ch] text-sm text-muted-foreground">
            We never tell you what you have. Every consultation ends by
            placing what you described on this scale, with the sources behind
            it.
          </p>
          <UrgencyScale className="mt-8" />
        </section>

        <RecentChatsSection sessions={data.sessions} loading={loading} />

        <RecommendedArticlesSection
          articles={data.articles}
          loading={loading}
          personalized={data.exploredTopics.length > 0}
        />

        {data.exploredTopics.length > 0 ? (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">
              Topics you&apos;ve explored
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Patterns our sources connect to symptoms you&apos;ve discussed — not
              a diagnosis.
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

        <Card className="border-border/50 bg-muted/10 opacity-80">
          <CardHeader>
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <CalendarDays className="size-5" />
              </span>
              <StatusBadge>Coming later</StatusBadge>
            </div>
            <CardTitle className="text-base">Health log</CardTitle>
            <CardDescription className="text-sm leading-relaxed">
              Track your cycle and symptoms over time — we&apos;re building this
              next.
            </CardDescription>
          </CardHeader>
        </Card>
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
