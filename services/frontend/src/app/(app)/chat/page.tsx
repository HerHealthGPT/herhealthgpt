"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MessageSquarePlus, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatMessage } from "@/components/chat/chat-message";
import { ChatShell } from "@/components/chat/chat-shell";
import { Illustration } from "@/components/ui/illustration";
import { ChatStarterPrompts } from "@/components/chat/chat-starter-prompts";
import { ConclusionCard } from "@/components/chat/conclusion-card";
import { DeclineCard } from "@/components/chat/decline-card";
import { ThinkingIndicator } from "@/components/chat/thinking-indicator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { friendlyTriageError } from "@/lib/api/errors";
import {
  deleteTriageSession,
  getTriageSession,
  listTriageSessions,
  sendTriageTurn,
} from "@/lib/api/triage";
import type {
  CitedPassage,
  DecisionReasoningModel,
  TriageDecision,
  TriageSessionMessage,
  TriageSessionSummary,
} from "@/lib/api/types";
import { useAuth } from "@/contexts/auth-context";
import { userDisplayName } from "@/lib/display-name";
import { routes } from "@/lib/routes";

type ChatEntry =
  | {
      id: string;
      kind: "message";
      role: "user" | "assistant";
      text: string;
      /** Present on an assistant question: the passages that prompted it.
       *  A question is a grounded decision too, not just filler between
       *  the opening message and a conclusion. */
      citedPassages?: CitedPassage[];
      /** The decision's `rationale`, shown behind the header's reasoning
       *  toggle. Only meaningful on an assistant turn. */
      rationale?: string | null;
      reasoningModel?: DecisionReasoningModel;
    }
  | { id: string; kind: "conclusion"; decision: TriageDecision }
  /** An off-scope message the model refused (ADR 0014). Its own kind, not a
   *  conclusion: `isConcluded` below keys off "conclusion", and a decline
   *  must leave the chat open. */
  | { id: string; kind: "decline"; rationale: string; reasoningModel?: DecisionReasoningModel };

type DistributiveOmit<T, K extends keyof T> = T extends unknown ? Omit<T, K> : never;
type ChatEntryInput = DistributiveOmit<ChatEntry, "id">;

const GREETING_TEXT =
  "I'm here to help you figure out what to do next. Tell me what's going on, in your own words, and I'll ask a few follow-up questions if I need to.";

/** The opening bubble, addressed to her by name when we have one.
 *
 *  A name is mandatory at sign-up now, so in practice we always do — but
 *  this still falls back, because the greeting renders from the very first
 *  paint and `user` can be null for a tick while the session loads. A
 *  bubble reading "Hi , " is worse than a bubble reading "Hi". */
function greetingText(name: string | null): string {
  return name ? `Hi ${name} — ${GREETING_TEXT}` : `Hi — ${GREETING_TEXT}`;
}

const GREETING: ChatEntry = {
  id: "greeting",
  kind: "message",
  role: "assistant",
  text: greetingText(null),
};

/** The greeting's text is derived from the signed-in user at render time,
 *  not stored. Storing it meant an effect rewriting state the moment the
 *  name loaded — a cascading render to say something the component already
 *  knew. Every other entry passes through untouched. */
function entryText(entry: ChatEntry & { kind: "message" }, name: string | null): string {
  return entry.id === "greeting" ? greetingText(name) : entry.text;
}

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

  if (decision.type === "decline") {
    return {
      id: message.id,
      kind: "decline",
      rationale: decision.rationale,
      reasoningModel: decision.reasoning_model,
    };
  }

  // An informational answer (ADR 0016) is an ordinary assistant bubble, not
  // a card: it is a reply in the conversation and she carries on talking
  // after it, exactly as after a clarifying question. `content` is the stored
  // copy of the same text (routes.py writes answer_text there), so a row
  // written before answer_text existed still reads.
  if (decision.type === "inform") {
    return {
      id: message.id,
      kind: "message",
      role: "assistant",
      text: decision.answer_text ?? message.content,
      citedPassages: decision.cited_passages,
      rationale: decision.rationale,
      reasoningModel: decision.reasoning_model,
    };
  }

  if (decision.question_text) {
    return {
      id: message.id,
      kind: "message",
      role: "assistant",
      text: decision.question_text,
      citedPassages: decision.cited_passages,
      rationale: decision.rationale,
      reasoningModel: decision.reasoning_model,
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
  const { user } = useAuth();
  const greetingName = userDisplayName(user);

  const [entries, setEntries] = useState<ChatEntry[]>([GREETING]);
  const [sessionId, setSessionId] = useState<string | null>(requestedSessionId);
  const [sessionStatus, setSessionStatus] = useState<"active" | "concluded" | null>(null);
  const [sessions, setSessions] = useState<TriageSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(Boolean(requestedSessionId));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesRef = useRef<HTMLDivElement>(null);

  const isConcluded =
    sessionStatus === "concluded" || entries.some((entry) => entry.kind === "conclusion");

  const userTurnCount = entries.filter(
    (entry) => entry.kind === "message" && entry.role === "user",
  ).length;

  const showStarters =
    !isLoadingSession &&
    !isSending &&
    !isConcluded &&
    userTurnCount === 0 &&
    entries.length === 1;

  const thinkingTurnLabel =
    userTurnCount === 0
      ? "First question — this usually takes 15–60 seconds"
      : `Follow-up ${userTurnCount + 1} — still checking sources`;

  const reloadSessions = useCallback(async () => {
    try {
      const nextSessions = await listTriageSessions();
      setSessions(nextSessions);
      setSessionsError(null);
    } catch (error) {
      setSessionsError(friendlyTriageError(error));
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
          setSessionsError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setSessionsError(friendlyTriageError(error));
        }
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

    // Captured into a const before the closure: TypeScript drops the
    // narrowing from the guard above once a parameter is read inside a
    // nested function, since it cannot prove the value is unchanged by
    // the time that function runs.
    const sessionToLoad = requestedSessionId;
    let cancelled = false;

    async function loadSession() {
      setIsLoadingSession(true);
      setErrorMessage(null);

      try {
        const detail = await getTriageSession(sessionToLoad);
        if (cancelled) {
          return;
        }

        setSessionId(detail.id);
        setSessionStatus(detail.status);
        setEntries(transcriptToEntries(detail.messages));
        // Reopening a chat no longer restores which model produced it: the
        // app runs one reasoning path and the selector is gone. Stored turns
        // still carry `reasoning_model`, so an evaluation run can tell which
        // model answered — it just does not steer the UI any more.
        setLastFailedMessage(null);
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            "We couldn't open that chat. Start a new one below — we're still here to help.",
          );
          setSessionId(null);
          setSessionStatus(null);
          setEntries([GREETING]);
          router.replace(routes.chat);
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
  }, [requestedSessionId, router]);

  useEffect(() => {
    const pane = messagesRef.current;
    if (!pane) {
      return;
    }
    // Scroll only the message pane — scrollIntoView can drag the whole page.
    pane.scrollTo({ top: pane.scrollHeight, behavior: "smooth" });
  }, [entries, isSending, isLoadingSession]);

  function appendEntry(entry: ChatEntryInput) {
    setEntries((current) => [...current, { ...entry, id: newId() } as ChatEntry]);
  }

  async function submitTurn(text: string) {
    setIsSending(true);
    setErrorMessage(null);

    try {
      const response = await sendTriageTurn(sessionId, text, null);
      setSessionId(response.session_id);
      setSessionStatus(response.decision.type === "conclude" ? "concluded" : "active");

      if (response.decision.type === "ask" && response.decision.question_text) {
        appendEntry({
          kind: "message",
          role: "assistant",
          text: response.decision.question_text,
          citedPassages: response.decision.cited_passages,
          rationale: response.decision.rationale,
          reasoningModel: response.decision.reasoning_model,
        });
      } else if (response.decision.type === "decline") {
        appendEntry({
          kind: "decline",
          rationale: response.decision.rationale,
          reasoningModel: response.decision.reasoning_model,
        });
      } else if (response.decision.type === "inform") {
        appendEntry({
          kind: "message",
          role: "assistant",
          text: response.decision.answer_text ?? response.decision.rationale,
          citedPassages: response.decision.cited_passages,
          rationale: response.decision.rationale,
          reasoningModel: response.decision.reasoning_model,
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

  const handleDeleteSession = useCallback(
    async (sessionIdToDelete: string) => {
      try {
        await deleteTriageSession(sessionIdToDelete);
        // Drop it immediately so the row cannot be clicked again while the
        // refetch is in flight...
        setSessions((current) => current.filter((session) => session.id !== sessionIdToDelete));
        toast.success("Chat deleted");

        if (sessionId === sessionIdToDelete || requestedSessionId === sessionIdToDelete) {
          // Deleting the chat you are reading. `ChatPageContent` keys this
          // component on the session id, so this navigation remounts it and
          // its own effect refetches — reloading here as well would be a
          // duplicate request against a component about to be torn down.
          router.push(routes.chat);
          return;
        }

        // ...then reconcile with the server, which is the authority. The
        // optimistic filter alone left the pane wrong whenever local state
        // and the server had diverged for any other reason, and a stale row
        // pointing at a deleted chat 404s when clicked.
        await reloadSessions();
      } catch (error) {
        toast.error(friendlyTriageError(error));
        // The delete may still have landed before the failure. Re-read
        // rather than leave the pane asserting something we do not know.
        await reloadSessions();
      }
    },
    [reloadSessions, requestedSessionId, router, sessionId],
  );

  return (
    <ChatShell
      sessions={sessions}
      sessionsLoading={sessionsLoading}
      sessionsError={sessionsError}
      activeSessionId={sessionId}
      sidebarOpen={sidebarOpen}
      onToggleSidebar={() => setSidebarOpen((open) => !open)}
      onCloseSidebar={() => setSidebarOpen(false)}
      onSelectSession={handleSelectSession}
      onNewChat={handleNewChat}
      onDeleteSession={handleDeleteSession}
    >
      <div className="mx-auto flex min-h-0 w-full max-w-2xl flex-1 flex-col overflow-hidden">
        <div
          ref={messagesRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 sm:px-6"
        >
          <div className="flex flex-col gap-4">
            {isLoadingSession ? <ThinkingIndicator label="Loading conversation…" /> : null}

            {showStarters ? (
              <ChatStarterPrompts disabled={isSending} onSelect={handleSend} />
            ) : null}

            {entries.map((entry) => {
              if (entry.kind === "message") {
                return (
                  <ChatMessage
                    key={entry.id}
                    role={entry.role}
                    text={entryText(entry, greetingName)}
                    citedPassages={entry.citedPassages}
                    rationale={entry.rationale}
                    reasoningModel={entry.reasoningModel}
                  />
                );
              }

              if (entry.kind === "decline") {
                return (
                  <DeclineCard
                    key={entry.id}
                    rationale={entry.rationale}
                    reasoningModel={entry.reasoningModel}
                  />
                );
              }

              return (
                <ConclusionCard
                  key={entry.id}
                  decision={entry.decision}
                  onStartNewChat={handleNewChat}
                />
              );
            })}

            {isSending ? <ThinkingIndicator turnLabel={thinkingTurnLabel} /> : null}

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
          </div>
        </div>

        <div className="shrink-0">
          {isConcluded ? (
            <div className="border-t border-border/60 bg-muted/20 p-4">
              {/* The end of a consultation is a resolution, not a dead end.
                  Absent until the SVG is added, which is why the copy below
                  still carries the moment on its own. */}
              <Illustration
                name="resolved"
                className="mx-auto mb-3 w-24"
              />
              <p className="mb-3 text-center text-sm text-muted-foreground">
                This chat is complete. Start a new one if something else comes up.
              </p>
              <Button size="lg" className="w-full" onClick={handleNewChat}>
                <MessageSquarePlus className="size-4" />
                Start a new chat
              </Button>
            </div>
          ) : (
            <ChatComposer
              disabled={isSending || isLoadingSession}
              placeholder={
                entries.length <= 1
                  ? "Tell me what's going on…"
                  : "Type your reply…"
              }
              showWaitHint={userTurnCount === 0 && !isSending && !isLoadingSession}
              onSend={handleSend}
            />
          )}
          {/* Persistent, always under the composer — the disclaimers inside a
              conclusion card only appear once an answer exists, so nothing
              carried this while she was typing. One line, deliberately: the
              longer this gets the faster it becomes furniture nobody reads,
              and the "not a diagnosis" half is the part that has to land. */}
          <p className="px-4 pb-3 text-center text-xs text-muted-foreground">
            HerHealthGPT can make mistakes. It gives urgency guidance, not a
            diagnosis.
          </p>
        </div>
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
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <Suspense
          fallback={
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
              Loading chat…
            </div>
          }
        >
          <ChatPageContent />
        </Suspense>
      </div>
    </AuthGuard>
  );
}
