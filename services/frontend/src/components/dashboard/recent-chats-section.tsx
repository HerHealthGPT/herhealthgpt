"use client";

import Link from "next/link";
import { MessageCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { TriageSessionSummary } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";
import type { Locale } from "@/i18n/config";

function formatWhen(iso: string, locale: Locale): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 7) {
    // "today", "yesterday", "3 days ago", in her language and its plurals.
    return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(-diffDays, "day");
  }
  return date.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

type RecentChatsSectionProps = {
  sessions: TriageSessionSummary[];
  loading?: boolean;
};

export function RecentChatsSection({ sessions, loading }: RecentChatsSectionProps) {
  const recent = sessions.slice(0, 5);
  const { m, locale } = useI18n();

  if (!loading && recent.length === 0) return null;

  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">{m.dashboard.recentChats}</h2>
        <Link
          href={routes.chat}
          className="text-sm font-medium text-primary hover:underline"
        >
          {m.dashboard.viewAll}
        </Link>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <ul className="space-y-2">
          {recent.map((session) => (
            <li key={session.id}>
              <Link
                href={`${routes.chat}?session=${session.id}`}
                className={cn(
                  "flex items-center gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 transition-colors hover:border-primary/25 hover:bg-accent/30",
                )}
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <MessageCircle className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {session.preview || m.dashboard.chatTitle}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatWhen(session.created_at, locale)}
                  </p>
                </div>
                {session.status === "concluded" ? (
                  <Badge variant="secondary" className="shrink-0 text-[10px]">
                    {m.dashboard.done}
                  </Badge>
                ) : (
                  <Badge className="shrink-0 text-[10px]">{m.dashboard.inProgress}</Badge>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
