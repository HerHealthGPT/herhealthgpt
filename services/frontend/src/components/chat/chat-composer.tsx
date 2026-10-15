"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n/locale-provider";

/** Tallest the composer grows before it starts scrolling instead. Matches
 *  `max-h-40` on the textarea below — the two must agree, or the JS caps the
 *  height at one value while CSS clips at another. */
const MAX_COMPOSER_HEIGHT = 160;

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
  const { m } = useI18n();
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) {
      return;
    }
    // Measure from scratch, then grow to fit up to the cap.
    element.style.height = "auto";
    const contentHeight = element.scrollHeight;
    element.style.height = `${Math.min(contentHeight, MAX_COMPOSER_HEIGHT)}px`;

    // A textarea defaults to `overflow: auto`, so a box even a pixel short of
    // its content shows a scrollbar — which is what produced a permanent
    // scrollbar on a single-line composer. Below the cap the box always fits
    // its own content, so there is nothing to scroll and the bar should not
    // exist; only once we stop growing is scrolling real.
    element.style.overflowY =
      contentHeight > MAX_COMPOSER_HEIGHT ? "auto" : "hidden";
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
          // `field-sizing-fixed` overrides the `field-sizing-content` the base
          // Textarea sets. Browser auto-sizing and the manual measurement in
          // the effect above each recompute against the other's result, and
          // the disagreement is what put a scrollbar on an empty composer.
          // One mechanism owns the height, and it is the effect.
          className="field-sizing-fixed max-h-40 min-h-11 resize-none overflow-y-hidden rounded-2xl bg-muted/40 py-3"
          aria-label={m.chat.composerLabel}
        />
        <Button
          className="mb-0.5 h-10 shrink-0 rounded-full px-4 sm:size-10 sm:px-0"
          disabled={disabled || !value.trim()}
          onClick={handleSend}
          aria-label={m.chat.sendLabel}
        >
          <span className="text-sm font-medium sm:hidden">{m.chat.send}</span>
          <ArrowUp className="hidden size-4 sm:block" />
        </Button>
      </div>
      {showWaitHint ? (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          {m.chat.waitHint}
        </p>
      ) : (
        <p className="mt-2 text-center text-[11px] text-muted-foreground/70">
          <span className="sm:hidden">{m.chat.tapSend}</span>
          <span className="hidden sm:inline">
            {m.chat.keyboardHint}
          </span>
        </p>
      )}
    </div>
  );
}
