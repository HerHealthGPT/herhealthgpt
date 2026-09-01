import Link from "next/link";
import { Globe, Heart, MessageCircle } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type AuthShellProps = {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function AuthShell({
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  return (
    <div className="flex min-h-full flex-1">
      <div className="relative hidden w-[45%] overflow-hidden lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-accent/30" />
        <div className="absolute -left-20 top-20 size-72 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute -right-10 bottom-10 size-80 rounded-full bg-accent/20 blur-3xl" />

        <div className="relative flex flex-1 flex-col justify-between p-10 xl:p-14">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
              <Heart className="size-5 fill-current" aria-hidden />
            </span>
            <span className="text-xl font-semibold tracking-tight">
              HerHealth<span className="text-primary">GPT</span>
            </span>
          </Link>

          <div className="space-y-8">
            <div className="space-y-4">
              <h1 className="max-w-md text-4xl font-semibold leading-tight tracking-tight text-balance">
                Not sure if you should see someone?
              </h1>
              <p className="max-w-md text-base leading-relaxed text-muted-foreground">
                Chat about what&apos;s bothering you. We can suggest conditions
                your symptoms might match and how soon to get care. We&apos;re
                not a doctor, and this isn&apos;t a diagnosis.
              </p>
            </div>

            <ul className="space-y-4">
              <li className="flex items-start gap-3 text-sm text-muted-foreground">
                <MessageCircle className="mt-0.5 size-4 shrink-0 text-primary" />
                It&apos;s a conversation, not a quiz. Say it your own way.
              </li>
              <li className="flex items-start gap-3 text-sm text-muted-foreground">
                <Globe className="mt-0.5 size-4 shrink-0 text-primary" />
                English, French, and Arabic
              </li>
            </ul>
          </div>

          <p className="text-xs text-muted-foreground">
            Information only. Not medical advice. Not a diagnosis. We&apos;re not
            a doctor.
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 sm:px-6">
        <div className="mb-8 flex items-center gap-2 lg:hidden">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Heart className="size-4 fill-current" aria-hidden />
          </span>
          <span className="text-lg font-semibold">HerHealthGPT</span>
        </div>

        <Card className="w-full max-w-md border-border/70 shadow-xl shadow-primary/5">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-2xl font-semibold tracking-tight">
              {title}
            </CardTitle>
            <CardDescription className="text-base leading-relaxed">
              {description}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">{children}</CardContent>
        </Card>

        {footer ? (
          <div className="mt-6 text-center text-sm text-muted-foreground">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
