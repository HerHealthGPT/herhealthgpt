"use client";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";



type ChatStarterPromptsProps = {
  disabled: boolean;
  onSelect: (text: string) => void;
};

export function ChatStarterPrompts({ disabled, onSelect }: ChatStarterPromptsProps) {
  // In the interface language, so a tap starts the chat in that language.
  const { m } = useI18n();
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">{m.chat.starterIntro}</p>
      <div className="flex flex-wrap gap-2">
        {m.chat.starters.map((prompt) => (
          <Button
            key={prompt}
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-auto rounded-full px-3 py-1.5 text-start text-xs font-normal whitespace-normal"
            onClick={() => onSelect(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}
