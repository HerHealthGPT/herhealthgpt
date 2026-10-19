"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, FileText, Paperclip } from "lucide-react";

import { CycleDataImport } from "@/components/account/cycle-data-import";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n/locale-provider";
import { getCycleData } from "@/lib/api/accounts";
import type { CycleDataSummary } from "@/lib/api/types";

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
  const [showCycleData, setShowCycleData] = useState(false);
  // Her imported cycle data, shown as an attachment the chat reads, the way
  // an attached file sits above the input. Null when she has none.
  const [cycle, setCycle] = useState<CycleDataSummary | null>(null);
  const [cycleVersion, setCycleVersion] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    getCycleData()
      .then((status) => {
        if (!cancelled) setCycle(status.summary);
      })
      .catch(() => {
        if (!cancelled) setCycle(null);
      });
    return () => {
      cancelled = true;
    };
  }, [cycleVersion]);

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
      {showCycleData ? (
        <div className="mb-3 rounded-2xl border border-border/60 bg-background p-3">
          <CycleDataImport
            onSaved={() => {
              setShowCycleData(false);
              setCycleVersion((version) => version + 1);
            }}
          />
        </div>
      ) : null}
      {cycle && !showCycleData ? (
        <button
          type="button"
          onClick={() => setShowCycleData(true)}
          title={m.chat.herData.chipHint}
          className="mb-2 inline-flex max-w-full items-center gap-2 rounded-xl border border-primary/25 bg-primary/5 px-2.5 py-1.5 text-xs text-foreground hover:bg-primary/10"
        >
          <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FileText className="size-3.5" aria-hidden />
          </span>
          <span className="truncate">
            {m.chat.herData.chip(m.chat.herData.app(cycle.source_app), cycle.periods_found)}
          </span>
        </button>
      ) : null}
      <div className="flex items-end gap-2">
        {/* Cycle data is saved to her account and used from the next turn on,
            the same data Settings manages (ADR 0019). */}
        <Button
          type="button"
          variant="ghost"
          className="mb-0.5 size-10 shrink-0 rounded-full"
          onClick={() => setShowCycleData((open) => !open)}
          aria-label={m.account.cycle.attach}
          aria-expanded={showCycleData}
          title={m.account.cycle.attach}
        >
          <Paperclip className="size-4" />
        </Button>
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
