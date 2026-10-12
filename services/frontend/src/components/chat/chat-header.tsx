"use client";

import Link from "next/link";
import { ArrowLeft, Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";

import { routes } from "@/lib/routes";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
};

/**
 * The chat's top bar: get to the conversation list, get back to the
 * dashboard. Nothing else.
 *
 * Three controls were removed from here on 2026-09-09, each for its own
 * reason:
 *
 * - **The Base / Fine-tuned selector.** The app runs a single reasoning path
 *   (`HERHEALTH_TRIAGE_MODE=vllm`: the base model decides and the fine-tuned
 *   adapter words informational answers), so there is nothing to choose
 *   between. The selector component and its endpoint were deleted (ADR 0018).
 * - **The Reasoning toggle.** It surfaced the decision's `rationale` a
 *   second time, behind a disclosure, on top of the answer the user is
 *   already reading. Two versions of the same sentence is not transparency.
 * - **Delete chat.** Deleting lived in two places at once, and the one up
 *   here acted on "the chat you happen to have open" rather than on a chat
 *   you pointed at. Deletion now belongs to the sidebar row it deletes,
 *   where the thing being destroyed is the thing under the cursor.
 */
export function ChatHeader({ onToggleSidebar, sidebarOpen }: ChatHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border/60 bg-background/95 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {sidebarOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      {/* Spacer on desktop, where the sidebar toggle is hidden, so the
          dashboard control stays pinned right instead of jumping left. */}
      <div className="hidden lg:block" aria-hidden />

      {/* Says where it goes, not what it is. This is the only way out of the
          chat, and as a bare grid glyph nobody read it as one — so it gets a
          back arrow, a full label, and an outline rather than ghost styling.
          The label stays "Back to dashboard" at every width: shortening it to
          an icon on mobile is exactly the case where it was being missed. */}
      <Button variant="outline" size="sm" className="shrink-0 gap-2" asChild>
        <Link href={routes.dashboard}>
          <ArrowLeft className="size-4" aria-hidden />
          Back to dashboard
        </Link>
      </Button>
    </header>
  );
}
