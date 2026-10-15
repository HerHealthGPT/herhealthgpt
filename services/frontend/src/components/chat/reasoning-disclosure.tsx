"use client";

import { useState } from "react";
import { Brain, ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";

/**
 * The model's own reasoning for a turn, collapsed by default.
 *
 * The content is `TriageDecision.rationale`, which the schema requires on
 * every decision — including a question — so that "why did it ask that?" is
 * answerable from the record. On a question turn the app otherwise shows only
 * `question_text` and drops the rationale on the floor, which is the gap this
 * fills.
 *
 * Deliberately **not** the model's raw chain of thought. Qwen's `<think>`
 * blocks are stripped in `triage/clients.py` before validation and never
 * persisted, and they are unvalidated text that can contain exactly the
 * "you have X" phrasing `CLAUDE.md` forbids this system from ever showing.
 * The rationale has been through `TriageDecision`; a thinking block has not.
 */
export function ReasoningDisclosure({ rationale }: { rationale: string }) {
  const { m } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-border/50 pt-2">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="flex w-full items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <Brain className="size-3.5 shrink-0" />
        <span>{open ? m.chat.hideReasoning : m.chat.showReasoning}</span>
        <ChevronDown
          className={cn("size-3.5 shrink-0 transition-transform", open && "rotate-180")}
        />
      </button>

      {open ? (
        <p className="animate-in fade-in slide-in-from-top-1 mt-2 text-xs leading-relaxed text-muted-foreground duration-200">
          {rationale}
        </p>
      ) : null}
    </div>
  );
}
