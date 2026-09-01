"use client";

import { MessageSquarePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import type { TriageSessionSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ConversationSidebarProps = {
  sessions: TriageSessionSummary[];
  activeSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
};

function formatWhen(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (sameDay) {
    return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ConversationSidebar({
  sessions,
  activeSessionId,
  isLoading,
  onSelectSession,
  onNewChat,
}: ConversationSidebarProps) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground">
      <div className="border-b border-sidebar-border p-3">
        <Button className="w-full justify-start gap-2" onClick={onNewChat}>
          <MessageSquarePlus className="size-4" />
          New chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {isLoading ? (
            <>
              <Skeleton className="h-14 w-full rounded-xl bg-sidebar-accent/40" />
              <Skeleton className="h-14 w-full rounded-xl bg-sidebar-accent/40" />
            </>
          ) : sessions.length === 0 ? (
            <p className="px-2 py-4 text-sm text-muted-foreground">
              Your past chats will show up here.
            </p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "w-full rounded-xl px-3 py-2.5 text-left transition-colors",
                  activeSessionId === session.id
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "hover:bg-sidebar-accent/60",
                )}
              >
                <p className="truncate text-sm font-medium">{session.preview}</p>
                <p className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>{formatWhen(session.created_at)}</span>
                  <span className="capitalize">{session.status}</span>
                </p>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
