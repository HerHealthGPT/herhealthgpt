"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Globe,
  MessageCircle,
} from "lucide-react";

import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const features = [
  {
    icon: MessageCircle,
    title: "Say it your way",
    description:
      "Heavy periods, pelvic pain, or something that just feels off. Write it like you'd tell a friend.",
  },
  {
    icon: BookOpen,
    title: "Conditions that might fit",
    description:
      "We can suggest health conditions your symptoms may match, with links to trusted sources. Information to help you decide, not a doctor's verdict.",
  },
  {
    icon: Globe,
    title: "English, French, and Arabic",
    description: "Use whichever language you're most comfortable in.",
  },
];

export default function HomePage() {
  return (
    <>
      <SiteHeader />

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-background to-background" />
          <div className="absolute -right-24 top-0 size-96 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -left-24 bottom-0 size-80 rounded-full bg-accent/20 blur-3xl" />

          <div className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
            <div className="mx-auto max-w-3xl text-center">
              <p className="mb-3 text-3xl font-bold tracking-tight sm:text-4xl">
                HerHealth<span className="text-primary">GPT</span>
              </p>
              <p className="mb-4 text-sm text-muted-foreground">
                For when you&apos;re not sure what to do
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl sm:leading-tight">
                Talk through what&apos;s going on.{" "}
                <span className="text-primary">Work out what to do next.</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
                <span className="font-semibold text-foreground">HerHealthGPT</span>{" "}
                is a health chat for women. You tell us how you feel. We ask a
                few follow-up questions. We may suggest conditions your symptoms
                could fit, and how soon to see someone. We&apos;re not a doctor,
                and this isn&apos;t a diagnosis.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Button size="lg" asChild className="min-w-[180px]">
                  <Link href={routes.signUp}>
                    Create a free account
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" asChild className="min-w-[180px]">
                  <Link href={routes.signIn}>I already have an account</Link>
                </Button>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-border/60 bg-muted/30 py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mb-12 text-center">
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                What you get
              </h2>
              <p className="mt-3 text-muted-foreground">
                A private chat, a clear next step, and links you can check
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              {features.map((feature) => (
                <Card
                  key={feature.title}
                  className="border-border/70 bg-card/80 backdrop-blur-sm"
                >
                  <CardHeader>
                    <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <feature.icon className="size-5" />
                    </div>
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                    <CardDescription className="text-base leading-relaxed">
                      {feature.description}
                    </CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
            <p className="text-sm leading-relaxed text-muted-foreground">
              HerHealthGPT shares health information, not medical advice or a
              diagnosis. We&apos;re not a doctor. If something feels urgent,
              call emergency services or go to hospital.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
