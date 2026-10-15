"use client";

import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatHeader } from "@/components/chat/chat-header";
import type { TriageModelOption, TriageSessionSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";

type ChatShellProps = {
  children: React.ReactNode;
  sessions: TriageSessionSummary[];
  sessionsLoading: boolean;
  sessionsError?: string | null;
  activeSessionId: string | null;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
  models?: TriageModelOption[];
  selectedModelId?: string;
  onSelectModel?: (modelId: string) => void;
  modelLocked?: boolean;
};

export function ChatShell({
  children,
  sessions,
  sessionsLoading,
  sessionsError,
  activeSessionId,
  sidebarOpen,
  onToggleSidebar,
  onCloseSidebar,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  models = [],
  selectedModelId,
  onSelectModel,
  modelLocked = false,
}: ChatShellProps) {
  const { m } = useI18n();
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {sidebarOpen ? (
          <button
            type="button"
            className="absolute inset-0 z-20 bg-black/40 lg:hidden"
            onClick={onCloseSidebar}
            aria-label={m.chat.closeSidebar}
          />
        ) : null}

        <aside
          className={cn(
            "absolute inset-y-0 start-0 z-30 flex h-full w-[min(100%,280px)] flex-col border-e border-border/60 bg-sidebar shadow-xl transition-transform duration-200 ease-out lg:static lg:z-0 lg:h-auto lg:translate-x-0 lg:shadow-none",
            sidebarOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full lg:translate-x-0 rtl:lg:translate-x-0",
          )}
        >
          <ConversationSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            isLoading={sessionsLoading}
            sessionsError={sessionsError}
            onSelectSession={(sessionId) => {
              onSelectSession(sessionId);
              onCloseSidebar();
            }}
            onNewChat={() => {
              onNewChat();
              onCloseSidebar();
            }}
            onDeleteSession={onDeleteSession}
          />
        </aside>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <ChatHeader
            onToggleSidebar={onToggleSidebar}
            sidebarOpen={sidebarOpen}
            models={models}
            selectedModelId={selectedModelId}
            onSelectModel={onSelectModel}
            modelLocked={modelLocked}
          />
          {models.length > 1 ? (
            <p className="shrink-0 border-b border-border/60 bg-muted/40 px-4 py-1.5 text-center text-xs text-muted-foreground">
              {m.chat.compareBanner}
            </p>
          ) : null}
          {children}
        </div>
      </div>
    </div>
  );
}
