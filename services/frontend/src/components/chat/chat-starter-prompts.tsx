"use client";

import { Button } from "@/components/ui/button";

const STARTER_PROMPTS = [
  "My periods have been irregular lately",
  "I'm having heavier bleeding than usual",
  "I've been trying to conceive for a while",
  "I have pelvic pain that won't go away",
] as const;

type ChatStarterPromptsProps = {
  disabled: boolean;
  onSelect: (text: string) => void;
};

export function ChatStarterPrompts({ disabled, onSelect }: ChatStarterPromptsProps) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Not sure where to start? Try one of these:</p>
      <div className="flex flex-wrap gap-2">
        {STARTER_PROMPTS.map((prompt) => (
          <Button
            key={prompt}
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className="h-auto rounded-full px-3 py-1.5 text-left text-xs font-normal whitespace-normal"
            onClick={() => onSelect(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}
