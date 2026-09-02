"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ChatComposerProps = {
  disabled: boolean;
  placeholder: string;
  onSend: (message: string) => void;
  /** Shown before the first message — sets wait-time expectations. */
  showWaitHint?: boolean;
};

export function ChatComposer({
  disabled,
  placeholder,
  onSend,
  showWaitHint,
}: ChatComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }, [value]);

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-border/60 bg-background/95 p-3 backdrop-blur-sm sm:p-4">
      <div className="flex items-end gap-2">
        <Textarea
          ref={textareaRef}
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
          className="max-h-40 min-h-11 resize-none rounded-2xl bg-muted/40 py-3"
          aria-label="Type what's going on"
        />
        <Button
          className="mb-0.5 h-10 shrink-0 rounded-full px-4 sm:size-10 sm:px-0"
          disabled={disabled || !value.trim()}
          onClick={handleSend}
          aria-label="Send message"
        >
          <span className="text-sm font-medium sm:hidden">Send</span>
          <ArrowUp className="hidden size-4 sm:block" />
        </Button>
      </div>
      {showWaitHint ? (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          First reply can take up to a minute — we&apos;ll show progress while you
          wait.
        </p>
      ) : (
        <p className="mt-2 text-center text-[11px] text-muted-foreground/70">
          <span className="sm:hidden">Tap Send when you&apos;re ready.</span>
          <span className="hidden sm:inline">
            Enter to send · Shift+Enter for a new line
          </span>
        </p>
      )}
    </div>
  );
}
