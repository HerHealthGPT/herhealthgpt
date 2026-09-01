import { Sparkles } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  text: string;
};

export function ChatMessage({ role, text }: ChatMessageProps) {
  const isAssistant = role === "assistant";

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
          "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words",
          isAssistant
            ? "rounded-bl-sm bg-muted text-foreground"
            : "rounded-br-sm bg-primary text-primary-foreground",
        )}
      >
        {text}
      </div>
    </div>
  );
}
