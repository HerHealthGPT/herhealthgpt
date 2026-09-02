"use client";

import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatHeader } from "@/components/chat/chat-header";
import type { TriageSessionSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ChatShellProps = {
  children: React.ReactNode;
  sessions: TriageSessionSummary[];
  sessionsLoading: boolean;
  activeSessionId: string | null;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
};

export function ChatShell({
  children,
  sessions,
  sessionsLoading,
  activeSessionId,
  sidebarOpen,
  onToggleSidebar,
  onCloseSidebar,
  onSelectSession,
  onNewChat,
}: ChatShellProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="relative flex min-h-0 flex-1">
        {sidebarOpen ? (
          <button
            type="button"
            className="absolute inset-0 z-20 bg-black/40 lg:hidden"
            onClick={onCloseSidebar}
            aria-label="Close sidebar"
          />
        ) : null}

        <aside
          className={cn(
            "absolute inset-y-0 left-0 z-30 flex w-[min(100%,280px)] flex-col border-r border-border/60 bg-sidebar shadow-xl transition-transform duration-200 ease-out lg:static lg:z-0 lg:translate-x-0 lg:shadow-none",
            sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
          )}
        >
          <ConversationSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            isLoading={sessionsLoading}
            onSelectSession={(sessionId) => {
              onSelectSession(sessionId);
              onCloseSidebar();
            }}
            onNewChat={() => {
              onNewChat();
              onCloseSidebar();
            }}
          />
        </aside>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <ChatHeader onToggleSidebar={onToggleSidebar} sidebarOpen={sidebarOpen} />
          {children}
        </div>
      </div>
    </div>
  );
}
