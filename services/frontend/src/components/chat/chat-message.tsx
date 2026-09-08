import { Sparkles } from "lucide-react";

import { CitedSources } from "@/components/chat/cited-sources";
import { ReasoningDisclosure } from "@/components/chat/reasoning-disclosure";
import { UnreviewedModelNotice } from "@/components/chat/unreviewed-model-notice";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { CitedPassage, DecisionReasoningModel } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  text: string;
  /** Sources behind an assistant question. A question is a decision too —
   *  the schema requires it to be grounded in a citation or a red flag —
   *  so it shows what prompted it, not just the question itself. */
  citedPassages?: CitedPassage[];
  /** The decision's `rationale`. Rendered behind a disclosure when
   *  `showReasoning` is on — see ReasoningDisclosure. */
  rationale?: string | null;
  showReasoning?: boolean;
  reasoningModel?: DecisionReasoningModel;
};

export function ChatMessage({
  role,
  text,
  citedPassages,
  rationale,
  showReasoning = false,
  reasoningModel,
}: ChatMessageProps) {
  const isAssistant = role === "assistant";
  const sources = isAssistant ? (citedPassages ?? []) : [];
  // Only ever on an assistant turn, and only when there is something to
  // show that is not already the visible message text.
  const reasoning =
    isAssistant && showReasoning && rationale && rationale.trim() !== text.trim()
      ? rationale
      : null;

  return (
    <div
      className={cn(
        "flex items-end gap-2.5",
        isAssistant ? "justify-start" : "justify-end",
      )}
    >
      {isAssistant ? (
        <Avatar size="sm" className="mb-0.5 shrink-0">
          <AvatarFallback className="bg-primary/10 text-primary">
            <Sparkles className="size-3.5" />
          </AvatarFallback>
        </Avatar>
      ) : null}

      <div
        className={cn(
          "max-w-[75%] space-y-2.5 rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words",
          "animate-in fade-in slide-in-from-bottom-2 duration-300",
          isAssistant
            ? "rounded-bl-sm bg-muted text-foreground"
            : "rounded-br-sm bg-primary text-primary-foreground",
        )}
      >
        <p>{text}</p>
        {isAssistant ? <UnreviewedModelNotice model={reasoningModel} /> : null}
        {sources.length > 0 ? <CitedSources passages={sources} variant="question" /> : null}
        {reasoning ? <ReasoningDisclosure rationale={reasoning} /> : null}
      </div>
    </div>
  );
}
