"use client";

import Link from "next/link";
import { ArrowLeft, Menu, X } from "lucide-react";

import { ModelSelector } from "@/components/chat/model-selector";
import { Button } from "@/components/ui/button";
import type { TriageModelOption } from "@/lib/api/types";

import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";

type ChatHeaderProps = {
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
  /** Evaluation versions on offer; empty on an ordinary deployment. */
  models?: TriageModelOption[];
  selectedModelId?: string;
  onSelectModel?: (modelId: string) => void;
  modelLocked?: boolean;
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
 *   adapter words informational answers). A version selector is back for
 *   evaluation sessions only: it renders when the server offers comparison
 *   versions (`HERHEALTH_COMPARISON_MODES=on`) and not otherwise.
 * - **The Reasoning toggle.** It surfaced the decision's `rationale` a
 *   second time, behind a disclosure, on top of the answer the user is
 *   already reading. Two versions of the same sentence is not transparency.
 * - **Delete chat.** Deleting lived in two places at once, and the one up
 *   here acted on "the chat you happen to have open" rather than on a chat
 *   you pointed at. Deletion now belongs to the sidebar row it deletes,
 *   where the thing being destroyed is the thing under the cursor.
 */
export function ChatHeader({
  onToggleSidebar,
  sidebarOpen,
  models = [],
  selectedModelId,
  onSelectModel,
  modelLocked = false,
}: ChatHeaderProps) {
  const { m } = useI18n();
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border/60 bg-background/95 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 lg:hidden"
        onClick={onToggleSidebar}
        aria-label={sidebarOpen ? m.chat.closeSidebar : m.chat.openSidebar}
      >
        {sidebarOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      {/* Spacer on desktop, where the sidebar toggle is hidden, so the
          dashboard control stays pinned right instead of jumping left. */}
      {models.length > 1 && selectedModelId && onSelectModel ? (
        <ModelSelector
          models={models}
          selectedId={selectedModelId}
          onSelect={onSelectModel}
          locked={modelLocked}
        />
      ) : (
        <div className="hidden lg:block" aria-hidden />
      )}

      {/* Says where it goes, not what it is. This is the only way out of the
          chat, and as a bare grid glyph nobody read it as one — so it gets a
          back arrow, a full label, and an outline rather than ghost styling.
          The label stays "Back to dashboard" at every width: shortening it to
          an icon on mobile is exactly the case where it was being missed. */}
      <Button variant="outline" size="sm" className="shrink-0 gap-2" asChild>
        <Link href={routes.dashboard}>
          <ArrowLeft className="size-4 rtl:rotate-180" aria-hidden />
          {models.length > 1 ? (
            <>
              <span className="sm:hidden">{m.chat.dashboardShort}</span>
              <span className="hidden sm:inline">{m.chat.backToDashboard}</span>
            </>
          ) : (
            m.chat.backToDashboard
          )}
        </Link>
      </Button>
    </header>
  );
}
