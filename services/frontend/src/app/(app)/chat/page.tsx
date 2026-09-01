"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { RotateCcw } from "lucide-react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatMessage } from "@/components/chat/chat-message";
import { ChatShell } from "@/components/chat/chat-shell";
import { ConclusionCard } from "@/components/chat/conclusion-card";
import { ThinkingIndicator } from "@/components/chat/thinking-indicator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { friendlyTriageError } from "@/lib/api/errors";
import {
  getTriageSession,
  listTriageSessions,
  sendTriageTurn,
} from "@/lib/api/triage";
import type {
  TriageDecision,
  TriageSessionMessage,
  TriageSessionSummary,
} from "@/lib/api/types";
import { routes } from "@/lib/routes";

type ChatEntry =
  | { id: string; kind: "message"; role: "user" | "assistant"; text: string }
  | { id: string; kind: "conclusion"; decision: TriageDecision };

type DistributiveOmit<T, K extends keyof T> = T extends unknown ? Omit<T, K> : never;
type ChatEntryInput = DistributiveOmit<ChatEntry, "id">;

const GREETING: ChatEntry = {
  id: "greeting",
  kind: "message",
  role: "assistant",
  text: "Hi — I'm here to help you figure out what to do next. Tell me what's going on, in your own words, and I'll ask a few follow-up questions if I need to.",
};

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

function messageToEntry(message: TriageSessionMessage): ChatEntry | null {
  if (message.role === "user") {
    return {
      id: message.id,
      kind: "message",
      role: "user",
      text: message.content,
    };
  }

  const decision = message.decision;
  if (!decision) {
    return {
      id: message.id,
      kind: "message",
      role: "assistant",
      text: message.content,
    };
  }

  if (decision.type === "conclude") {
    return { id: message.id, kind: "conclusion", decision };
  }

  if (decision.question_text) {
    return {
      id: message.id,
      kind: "message",
      role: "assistant",
      text: decision.question_text,
    };
  }

  return {
    id: message.id,
    kind: "message",
    role: "assistant",
    text: message.content,
  };
}

function transcriptToEntries(messages: TriageSessionMessage[]): ChatEntry[] {
  if (messages.length === 0) {
    return [GREETING];
  }

  return messages
    .map((message) => messageToEntry(message))
    .filter((entry): entry is ChatEntry => entry !== null);
}

function ChatContent({ requestedSessionId }: { requestedSessionId: string | null }) {
  const router = useRouter();

  const [entries, setEntries] = useState<ChatEntry[]>([GREETING]);
  const [sessionId, setSessionId] = useState<string | null>(requestedSessionId);
  const [sessionStatus, setSessionStatus] = useState<"active" | "concluded" | null>(null);
  const [sessions, setSessions] = useState<TriageSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(Boolean(requestedSessionId));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const isConcluded =
    sessionStatus === "concluded" || entries.some((entry) => entry.kind === "conclusion");

  const reloadSessions = useCallback(async () => {
    try {
      const nextSessions = await listTriageSessions();
      setSessions(nextSessions);
    } catch {
      // Sidebar failure should not block the chat itself.
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      try {
        const nextSessions = await listTriageSessions();
        if (!cancelled) {
          setSessions(nextSessions);
        }
      } catch {
        // Sidebar failure should not block the chat itself.
      } finally {
        if (!cancelled) {
          setSessionsLoading(false);
        }
      }
    }

    void loadSessions();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!requestedSessionId) {
      return;
    }

    let cancelled = false;

    async function loadSession() {
      setIsLoadingSession(true);
      setErrorMessage(null);

      try {
        const detail = await getTriageSession(requestedSessionId);
        if (cancelled) {
          return;
        }

        setSessionId(detail.id);
        setSessionStatus(detail.status);
        setEntries(transcriptToEntries(detail.messages));
        setLastFailedMessage(null);
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(friendlyTriageError(error));
          setSessionId(null);
          setSessionStatus(null);
          setEntries([GREETING]);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSession(false);
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [requestedSessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries, isSending, isLoadingSession]);

  function appendEntry(entry: ChatEntryInput) {
    setEntries((current) => [...current, { ...entry, id: newId() } as ChatEntry]);
  }

  async function submitTurn(text: string) {
    setIsSending(true);
    setErrorMessage(null);

    try {
      const response = await sendTriageTurn(sessionId, text);
      setSessionId(response.session_id);
      setSessionStatus(response.decision.type === "conclude" ? "concluded" : "active");

      if (response.decision.type === "ask" && response.decision.question_text) {
        appendEntry({
          kind: "message",
          role: "assistant",
          text: response.decision.question_text,
        });
      } else {
        appendEntry({ kind: "conclusion", decision: response.decision });
      }

      setLastFailedMessage(null);
      await reloadSessions();

      if (!requestedSessionId || requestedSessionId !== response.session_id) {
        router.replace(`${routes.chat}?session=${response.session_id}`);
      }
    } catch (error) {
      setErrorMessage(friendlyTriageError(error));
      setLastFailedMessage(text);
    } finally {
      setIsSending(false);
    }
  }

  function handleSend(text: string) {
    appendEntry({ kind: "message", role: "user", text });
    void submitTurn(text);
  }

  function handleRetry() {
    if (lastFailedMessage) {
      void submitTurn(lastFailedMessage);
    }
  }

  function handleNewChat() {
    router.push(routes.chat);
  }

  function handleSelectSession(nextSessionId: string) {
    router.push(`${routes.chat}?session=${nextSessionId}`);
  }

  return (
    <ChatShell
      sessions={sessions}
      sessionsLoading={sessionsLoading}
      activeSessionId={sessionId}
      sidebarOpen={sidebarOpen}
      profileOpen={profileOpen}
      onToggleSidebar={() => setSidebarOpen((open) => !open)}
      onCloseSidebar={() => setSidebarOpen(false)}
      onOpenProfile={() => setProfileOpen(true)}
      onCloseProfile={() => setProfileOpen(false)}
      onSelectSession={handleSelectSession}
      onNewChat={handleNewChat}
    >
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col">
        <ScrollArea className="flex-1">
          <div className="flex flex-col gap-4 px-4 py-6 sm:px-6">
            {isLoadingSession ? <ThinkingIndicator label="Loading conversation…" /> : null}

            {entries.map((entry) =>
              entry.kind === "message" ? (
                <ChatMessage key={entry.id} role={entry.role} text={entry.text} />
              ) : (
                <ConclusionCard
                  key={entry.id}
                  decision={entry.decision}
                  onStartNewChat={handleNewChat}
                />
              ),
            )}

            {isSending ? <ThinkingIndicator /> : null}

            {errorMessage ? (
              <Alert variant="destructive">
                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                  <span>{errorMessage}</span>
                  {lastFailedMessage ? (
                    <Button size="sm" variant="outline" onClick={handleRetry}>
                      <RotateCcw className="size-3.5" />
                      Try again
                    </Button>
                  ) : null}
                </AlertDescription>
              </Alert>
            ) : null}

            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <ChatComposer
          disabled={isSending || isConcluded || isLoadingSession}
          placeholder={
            isConcluded
              ? "Start a new chat to keep talking"
              : entries.length <= 1
                ? "Tell me what's going on…"
                : "Type your reply…"
          }
          onSend={handleSend}
        />
      </div>
    </ChatShell>
  );
}

function ChatPageContent() {
  const searchParams = useSearchParams();
  const requestedSessionId = searchParams.get("session");

  return (
    <ChatContent
      key={requestedSessionId ?? "new"}
      requestedSessionId={requestedSessionId}
    />
  );
}

export default function ChatPage() {
  return (
    <AuthGuard>
      <Suspense fallback={<div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">Loading chat…</div>}>
        <ChatPageContent />
      </Suspense>
    </AuthGuard>
  );
}
