"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ChevronsUpDown,
  Heart,
  LayoutDashboard,
  LogOut,
  MessageSquarePlus,
  Trash2,
} from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import type { TriageSessionSummary } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

type ConversationSidebarProps = {
  sessions: TriageSessionSummary[];
  activeSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
};

type SessionGroup = {
  label: string;
  sessions: TriageSessionSummary[];
};

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function groupSessions(sessions: TriageSessionSummary[]): SessionGroup[] {
  const now = startOfDay(new Date());
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const weekAgo = new Date(now);
  weekAgo.setDate(weekAgo.getDate() - 7);

  const groups: Record<string, TriageSessionSummary[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 days": [],
    Older: [],
  };

  for (const session of sessions) {
    const day = startOfDay(new Date(session.created_at));
    if (day.getTime() === now.getTime()) {
      groups.Today.push(session);
    } else if (day.getTime() === yesterday.getTime()) {
      groups.Yesterday.push(session);
    } else if (day > weekAgo) {
      groups["Previous 7 days"].push(session);
    } else {
      groups.Older.push(session);
    }
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, sessions: items }));
}

function userInitial(email: string | undefined): string {
  if (!email) {
    return "?";
  }
  return email[0]?.toUpperCase() ?? "?";
}

function displayName(email: string | undefined): string {
  if (!email) {
    return "Account";
  }
  const local = email.split("@")[0];
  return local.length > 20 ? `${local.slice(0, 18)}…` : local;
}

function SidebarProfileFooter({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  function closeMenu() {
    setMenuOpen(false);
    onNavigate?.();
  }

  return (
    <div className="relative shrink-0 border-t border-sidebar-border p-2">
      {menuOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-10 lg:absolute"
            onClick={() => setMenuOpen(false)}
            aria-label="Close account menu"
          />
          <div className="absolute bottom-full left-2 right-2 z-20 mb-1 overflow-hidden rounded-xl border border-border/60 bg-popover p-1 shadow-lg">
            <Button
              variant="ghost"
              className="h-10 w-full justify-start gap-2 px-3"
              asChild
              onClick={closeMenu}
            >
              <Link href={routes.dashboard}>
                <LayoutDashboard className="size-4" />
                Dashboard
              </Link>
            </Button>
            <Button
              variant="ghost"
              className="h-10 w-full justify-start gap-2 px-3 text-destructive hover:text-destructive"
              onClick={() => {
                closeMenu();
                void signOut();
              }}
            >
              <LogOut className="size-4" />
              Sign out
            </Button>
          </div>
        </>
      ) : null}

      <button
        type="button"
        onClick={() => setMenuOpen((open) => !open)}
        className={cn(
          "relative z-30 flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors",
          menuOpen ? "bg-sidebar-accent" : "hover:bg-sidebar-accent/70",
        )}
        aria-expanded={menuOpen}
        aria-label="Account menu"
      >
        <Avatar size="sm">
          <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
            {userInitial(user?.email)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{displayName(user?.email)}</p>
          <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
        </div>
        <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
      </button>
    </div>
  );
}

export function ConversationSidebar({
  sessions,
  activeSessionId,
  isLoading,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: ConversationSidebarProps) {
  const grouped = groupSessions(sessions);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function handleConfirmDelete(sessionId: string) {
    setDeletingId(sessionId);
    try {
      await onDeleteSession(sessionId);
      setConfirmingDeleteId(null);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex shrink-0 items-center gap-2 border-b border-sidebar-border px-4 py-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Heart className="size-4 fill-current" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">
            HerHealth<span className="text-primary">GPT</span>
          </p>
          <p className="truncate text-xs text-muted-foreground">Health chat</p>
        </div>
      </div>

      <div className="shrink-0 p-2">
        <Button
          className="w-full justify-start gap-2 shadow-sm"
          onClick={onNewChat}
        >
          <MessageSquarePlus className="size-4" />
          New chat
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-4 px-2 pb-2">
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-3 w-16 rounded bg-sidebar-accent/40" />
              <Skeleton className="h-11 w-full rounded-xl bg-sidebar-accent/40" />
              <Skeleton className="h-11 w-full rounded-xl bg-sidebar-accent/40" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="px-2 py-6 text-center text-sm leading-relaxed text-muted-foreground">
              No past chats yet.
              <br />
              Start one above.
            </p>
          ) : (
            grouped.map((group) => (
              <div key={group.label}>
                <p className="mb-1.5 px-2 text-xs font-medium text-muted-foreground">
                  {group.label}
                </p>
                <div className="space-y-0.5">
                  {group.sessions.map((session) => (
                    <div
                      key={session.id}
                      className={cn(
                        "group relative flex items-stretch rounded-xl transition-colors",
                        activeSessionId === session.id
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "hover:bg-sidebar-accent/60",
                      )}
                    >
                      {confirmingDeleteId === session.id ? (
                        <div className="flex w-full flex-col gap-2 px-3 py-2.5">
                          <p className="text-xs text-muted-foreground">
                            Delete this chat permanently?
                          </p>
                          <div className="flex gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="h-7 flex-1 text-xs"
                              disabled={deletingId === session.id}
                              onClick={() => setConfirmingDeleteId(null)}
                            >
                              Cancel
                            </Button>
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              className="h-7 flex-1 text-xs"
                              disabled={deletingId === session.id}
                              onClick={() => void handleConfirmDelete(session.id)}
                            >
                              Delete
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => onSelectSession(session.id)}
                            className="min-w-0 flex-1 px-3 py-2.5 pr-10 text-left"
                          >
                            <p className="truncate text-sm">{session.preview}</p>
                            {session.status === "concluded" ? (
                              <p className="mt-0.5 text-xs text-muted-foreground">Completed</p>
                            ) : null}
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setConfirmingDeleteId(session.id);
                            }}
                            className={cn(
                              "absolute right-1 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-opacity hover:bg-background/60 hover:text-destructive",
                              "opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100",
                            )}
                            aria-label={`Delete chat: ${session.preview}`}
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      <SidebarProfileFooter />
    </div>
  );
}
