"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ChevronsUpDown,
  Heart,
  Info,
  LayoutDashboard,
  LogOut,
  MessageSquarePlus,
  MoreHorizontal,
  Settings,
} from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Illustration } from "@/components/ui/illustration";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import type { TriageSessionSummary, UserSummary } from "@/lib/api/types";
import { userDisplayName } from "@/lib/display-name";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

type ConversationSidebarProps = {
  sessions: TriageSessionSummary[];
  activeSessionId: string | null;
  isLoading: boolean;
  sessionsError?: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
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

function avatarInitial(user: UserSummary | null | undefined): string {
  const name = userDisplayName(user);
  if (name) {
    return name[0]?.toUpperCase() ?? "?";
  }
  if (!user?.email) {
    return "?";
  }
  return user.email[0]?.toUpperCase() ?? "?";
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
              className="h-10 w-full justify-start gap-2 px-3"
              asChild
              onClick={closeMenu}
            >
              <Link href={routes.howItWorks}>
                <Info className="size-4" />
                How this works
              </Link>
            </Button>
            <Button
              variant="ghost"
              className="h-10 w-full justify-start gap-2 px-3"
              asChild
              onClick={closeMenu}
            >
              <Link href={routes.settings}>
                <Settings className="size-4" />
                Account
              </Link>
            </Button>
            <Button
              variant="ghost"
              className="h-10 w-full justify-start gap-2 px-3"
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
            {avatarInitial(user)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {userDisplayName(user) ?? "Your account"}
          </p>
          <p className="truncate text-xs text-muted-foreground">Manage profile</p>
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
  sessionsError,
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
          {sessionsError ? (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs leading-relaxed text-destructive">
              {sessionsError}
            </p>
          ) : null}
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-3 w-16 rounded bg-sidebar-accent/40" />
              <Skeleton className="h-11 w-full rounded-xl bg-sidebar-accent/40" />
              <Skeleton className="h-11 w-full rounded-xl bg-sidebar-accent/40" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="px-2 py-6 text-center">
              <Illustration name="conversation" className="mx-auto mb-3 w-32" />
              <p className="text-sm leading-relaxed text-muted-foreground">
                No chats yet. Start one above and it&apos;ll show up here.
              </p>
            </div>
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
                        "group relative flex min-w-0 items-stretch rounded-xl transition-colors",
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
                            className="min-w-0 flex-1 overflow-hidden px-3 py-2.5 pr-3 text-left"
                          >
                            {/* block + w-full so `truncate` has a definite
                                width to truncate against: inside a flex row a
                                bare <p> can size to its content and push the
                                delete control off the panel instead of
                                ellipsing. */}
                            <p className="block w-full truncate text-sm">
                              {session.preview}
                            </p>
                            {session.status === "concluded" ? (
                              <p className="mt-0.5 text-xs text-muted-foreground">Completed</p>
                            ) : null}
                          </button>
                          {/* The "…" affordance. Sits over the end of the
                              title on a gradient rather than beside it, so
                              the title always gets the panel's full width to
                              truncate into and the control costs no layout.
                              The gradient fades the ellipsed text out under
                              the button instead of letting a half-letter
                              collide with it.

                              Always in the DOM and reachable by keyboard:
                              hidden by opacity, never `hidden`, so tab order
                              and screen readers are unaffected. */}
                          <div
                            className={cn(
                              "pointer-events-none absolute inset-y-0 right-0 flex items-center pl-8 pr-1.5",
                              "bg-gradient-to-l from-sidebar-accent via-sidebar-accent to-transparent",
                              "rounded-r-xl opacity-0 transition-opacity",
                              "group-hover:opacity-100 group-focus-within:opacity-100",
                              activeSessionId === session.id ? "" : "from-sidebar via-sidebar",
                            )}
                          >
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                setConfirmingDeleteId(session.id);
                              }}
                              className={cn(
                                "pointer-events-auto rounded-md p-1.5 text-muted-foreground transition",
                                "hover:bg-destructive/10 hover:text-destructive",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                              )}
                              aria-label={`Delete chat: ${session.preview}`}
                              title="Delete chat"
                            >
                              <MoreHorizontal className="size-4" aria-hidden />
                            </button>
                          </div>
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
