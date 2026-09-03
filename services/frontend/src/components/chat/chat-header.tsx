"use client";

import { useState } from "react";
import Link from "next/link";
import { LayoutDashboard, Menu, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
  /** The open consultation, if any. No session yet means a blank new chat
   *  with nothing to delete. */
  sessionId: string | null;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
};

export function ChatHeader({
  onToggleSidebar,
  sidebarOpen,
  sessionId,
  onDeleteSession,
}: ChatHeaderProps) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleConfirmDelete() {
    if (!sessionId) {
      return;
    }
    setDeleting(true);
    try {
      await onDeleteSession(sessionId);
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border/60 bg-background/95 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {sidebarOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">Health chat</p>
        <p className="truncate text-xs text-muted-foreground">
          Guidance only — not a diagnosis
        </p>
      </div>

      {sessionId ? (
        confirming ? (
          <div className="flex shrink-0 items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={deleting}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={deleting}
              onClick={() => void handleConfirmDelete()}
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => setConfirming(true)}
          >
            <Trash2 className="size-4" />
            Delete chat
          </Button>
        )
      ) : null}

      <Button
        variant="ghost"
        size="icon"
        className="shrink-0"
        asChild
        title="Home"
      >
        <Link href={routes.dashboard} aria-label="Home">
          <LayoutDashboard className="size-5" />
        </Link>
      </Button>
    </header>
  );
}
