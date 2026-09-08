"use client";

import { useState } from "react";
import Link from "next/link";
import { Brain, LayoutDashboard, Menu, Trash2, X } from "lucide-react";

import { ModelSelector } from "@/components/chat/model-selector";
import { Button } from "@/components/ui/button";
import type { ReasoningModelSummary } from "@/lib/api/types";
import { routes } from "@/lib/routes";
import { cn } from "@/lib/utils";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
  /** The open consultation, if any. No session yet means a blank new chat
   *  with nothing to delete. */
  sessionId: string | null;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
  showReasoning: boolean;
  onToggleReasoning: () => void;
  models: ReasoningModelSummary[];
  selectedModelId: string | null;
  onSelectModel: (modelId: string) => void;
  modelLocked: boolean;
};

export function ChatHeader({
  onToggleSidebar,
  sidebarOpen,
  sessionId,
  onDeleteSession,
  showReasoning,
  onToggleReasoning,
  models,
  selectedModelId,
  onSelectModel,
  modelLocked,
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

      <div className="flex min-w-0 flex-1 justify-center">
        <ModelSelector
          models={models}
          selectedId={selectedModelId}
          onSelect={onSelectModel}
          disabled={modelLocked}
        />
      </div>

      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          role="switch"
          aria-checked={showReasoning}
          onClick={onToggleReasoning}
          title={
            showReasoning
              ? "Hide the reasoning behind each reply"
              : "Show the reasoning behind each reply"
          }
          className={cn(
            "shrink-0",
            showReasoning ? "text-primary" : "text-muted-foreground",
          )}
        >
          <Brain className="size-4" />
          <span className="hidden sm:inline">Reasoning</span>
        </Button>

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
              <span className="hidden sm:inline">Delete chat</span>
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
      </div>
    </header>
  );
}
