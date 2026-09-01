"use client";

import { useState } from "react";
import { ArrowUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ChatComposerProps = {
  disabled: boolean;
  placeholder: string;
  onSend: (message: string) => void;
};

export function ChatComposer({ disabled, placeholder, onSend }: ChatComposerProps) {
  const [value, setValue] = useState("");

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="flex items-end gap-2 border-t border-border/60 bg-background p-3 sm:p-4">
      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSend();
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="max-h-40 resize-none rounded-2xl bg-muted/40 py-3"
        aria-label="Type what's going on"
      />
      <Button
        size="icon-lg"
        className="mb-0.5 shrink-0 rounded-full"
        disabled={disabled || !value.trim()}
        onClick={handleSend}
        aria-label="Send message"
      >
        <ArrowUp className="size-4" />
      </Button>
    </div>
  );
}
