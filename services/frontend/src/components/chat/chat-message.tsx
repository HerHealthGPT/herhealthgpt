import { Sparkles } from "lucide-react";

import { CitedSources } from "@/components/chat/cited-sources";
import { ReasoningDisclosure } from "@/components/chat/reasoning-disclosure";
import { StructuredText } from "@/components/chat/structured-text";
import { UnreviewedModelNotice } from "@/components/chat/unreviewed-model-notice";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { CitedPassage, DecisionReasoningModel } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** Blank-line-separated paragraphs. HTML collapses whitespace, so a long
 *  reply — an informational answer especially (ADR 0016), where the model is
 *  asked for a full one — would otherwise arrive as a single unbroken block.
 *  A message with no blank line in it yields one paragraph and renders
 *  exactly as it did before. */
function paragraphs(text: string): string[] {
  const parts = text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  return parts.length > 0 ? parts : [text];
}

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
          "space-y-2.5 rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words",
          "animate-in fade-in slide-in-from-bottom-2 duration-300",
          // Her messages are short, so 75% keeps the conversation feeling
          // like one. An informational answer is several hundred words with
          // headings and lists, and 75% of a desktop column wraps it into a
          // narrow ribbon; the extra room is what makes the structure read.
          isAssistant ? "max-w-[92%]" : "max-w-[75%]",
          isAssistant
            ? "rounded-bl-sm bg-muted text-foreground"
            : "rounded-br-sm bg-primary text-primary-foreground",
        )}
      >
        {/* An assistant turn gets its own structure rendered — headings and
            bullet lists — because an informational answer (ADR 0016) is long
            and is unreadable as one flat block. Her own messages stay plain
            paragraphs: she is not writing markup, and a line she happened to
            start with a dash should not become a list item. */}
        {isAssistant ? (
          <StructuredText text={text} />
        ) : (
          paragraphs(text).map((paragraph, index) => (
            <p key={index} className="whitespace-pre-line">
              {paragraph}
            </p>
          ))
        )}
        {isAssistant ? <UnreviewedModelNotice model={reasoningModel} /> : null}
        {sources.length > 0 ? <CitedSources passages={sources} variant="question" /> : null}
        {reasoning ? <ReasoningDisclosure rationale={reasoning} /> : null}
      </div>
    </div>
  );
}
