"use client";

import {
  CalendarDays,
  CheckCircle2,
  Circle,
  MessageCircle,
  Sparkles,
} from "lucide-react";

import { StatusBadge } from "@/components/dashboard/status-badge";
import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";

function DashboardContent() {
  const { user } = useAuth();
  const firstName = user?.email?.split("@")[0];

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
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Welcome to{" "}
            <span className="font-semibold text-foreground">HerHealthGPT</span>.
            When the health chat opens, this is where you&apos;ll start.
          </p>
        </div>
      </section>

      <div className="mx-auto w-full max-w-6xl flex-1 space-y-8 px-4 py-8 sm:px-6 sm:py-10">
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
                    <StatusBadge>Opening soon</StatusBadge>
                  </div>
                  <CardDescription className="mt-1 text-base">
                    Your main way to use HerHealthGPT
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
              <Button size="lg" className="w-full min-w-[200px]" disabled>
                <Sparkles className="size-4" />
                Start a chat
              </Button>
              <p className="mt-3 text-center text-xs text-muted-foreground">
                We&apos;re finishing this up. Check back soon.
              </p>
            </CardContent>
          </div>
        </Card>

        <div>
          <h2 className="mb-4 text-lg font-semibold tracking-tight">
            More coming soon
          </h2>
          <div className="grid gap-5 sm:grid-cols-2">
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
                  <span className="block font-medium">{user?.email}</span>
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

        <Card className="border-dashed border-border bg-muted/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Getting started</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              <li className="flex items-start gap-3 text-sm">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>Account created</span>
              </li>
              <li className="flex items-start gap-3 text-sm">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>Email verified</span>
              </li>
              <li className="flex items-start gap-3 text-sm text-muted-foreground">
                <Circle className="mt-0.5 size-4 shrink-0" />
                <span>Start your first health chat</span>
              </li>
            </ol>
          </CardContent>
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
