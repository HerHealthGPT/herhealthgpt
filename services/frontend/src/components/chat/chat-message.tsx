import { Sparkles } from "lucide-react";

import { CitedSources } from "@/components/chat/cited-sources";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { CitedPassage } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  text: string;
  /** Sources behind an assistant question. A question is a decision too —
   *  the schema requires it to be grounded in a citation or a red flag —
   *  so it shows what prompted it, not just the question itself. */
  citedPassages?: CitedPassage[];
};

export function ChatMessage({ role, text, citedPassages }: ChatMessageProps) {
  const isAssistant = role === "assistant";
  const sources = isAssistant ? (citedPassages ?? []) : [];

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
        {sources.length > 0 ? <CitedSources passages={sources} variant="question" /> : null}
      </div>
    </div>
  );
}
