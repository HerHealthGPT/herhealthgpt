"use client";

import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { ChatHeader } from "@/components/chat/chat-header";
import { ChatProfilePanel } from "@/components/chat/chat-profile-panel";
import type { TriageSessionSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ChatShellProps = {
  children: React.ReactNode;
  sessions: TriageSessionSummary[];
  sessionsLoading: boolean;
  activeSessionId: string | null;
  sidebarOpen: boolean;
  profileOpen: boolean;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onOpenProfile: () => void;
  onCloseProfile: () => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
};

export function ChatShell({
  children,
  sessions,
  sessionsLoading,
  activeSessionId,
  sidebarOpen,
  profileOpen,
  onToggleSidebar,
  onCloseSidebar,
  onOpenProfile,
  onCloseProfile,
  onSelectSession,
  onNewChat,
}: ChatShellProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ChatHeader
        onToggleSidebar={onToggleSidebar}
        onOpenProfile={onOpenProfile}
        sidebarOpen={sidebarOpen}
      />

      <div className="relative flex min-h-0 flex-1">
        {sidebarOpen ? (
          <button
            type="button"
            className="absolute inset-0 z-20 bg-black/30 lg:hidden"
            onClick={onCloseSidebar}
            aria-label="Close conversations"
          />
        ) : null}

        <aside
          className={cn(
            "absolute inset-y-0 left-0 z-30 w-72 border-r border-border/60 bg-sidebar shadow-lg transition-transform lg:static lg:translate-x-0 lg:shadow-none",
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

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</div>
      </div>

      <ChatProfilePanel open={profileOpen} onClose={onCloseProfile} />
    </div>
  );
}
