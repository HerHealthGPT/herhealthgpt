"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";

type ThinkingStage = {
  afterSeconds: number;
  label: string;
  progress: number;
};

/**
 * Staged copy for long-running triage turns. A bare spinner for 60+ seconds
 * reads as frozen; honest phases matched to what the backend actually does
 * (retrieve → reason, sometimes retry) keep the wait feel intentional.
 */
const TRIAGE_STAGES: ThinkingStage[] = [
  { afterSeconds: 0, label: "Reading what you shared…", progress: 12 },
  { afterSeconds: 8, label: "Searching trusted health sources…", progress: 35 },
  { afterSeconds: 20, label: "Thinking through what to ask next…", progress: 58 },
  { afterSeconds: 40, label: "Still working — some cases take a minute…", progress: 78 },
  { afterSeconds: 70, label: "Almost there — thanks for waiting…", progress: 92 },
];

function stageForElapsed(seconds: number): ThinkingStage {
  let current = TRIAGE_STAGES[0];
  for (const stage of TRIAGE_STAGES) {
    if (seconds >= stage.afterSeconds) {
      current = stage;
    }
  }
  return current;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder > 0 ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

export function ThinkingIndicator({
  label,
  turnLabel,
}: {
  label?: string;
  /** e.g. "Question 2" — shown during an active consultation. */
  turnLabel?: string;
}) {
  const { m } = useI18n();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (label) {
      return;
    }
    const started = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [label]);

  const stage = stageForElapsed(elapsed);
  // The stages are fixed; their words come from the dictionary, by position.
  const text = label ?? m.chat.thinking[TRIAGE_STAGES.indexOf(stage)] ?? stage.label;

  return (
    <div className="flex items-end gap-2.5 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <Avatar size="sm" className="mb-0.5 shrink-0">
        <AvatarFallback className="bg-primary/10 text-primary">
          <Sparkles className="size-3.5" />
        </AvatarFallback>
      </Avatar>

      <div className="max-w-[85%] space-y-2 rounded-2xl rounded-es-sm bg-muted px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
          <span className="flex gap-1">
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:-0.3s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:-0.15s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70" />
          </span>
          <span>{text}</span>
          {!label ? (
            <span className="text-xs tabular-nums text-muted-foreground/70">
              {formatElapsed(elapsed)}
            </span>
          ) : null}
        </div>

        {!label ? (
          <>
            <div className="h-1 overflow-hidden rounded-full bg-background/80">
              <div
                className={cn(
                  "h-full rounded-full bg-primary/50 transition-[width] duration-1000 ease-out",
                )}
                style={{ width: `${stage.progress}%` }}
              />
            </div>
            {turnLabel ? (
              <p className="text-xs text-muted-foreground/80">{turnLabel}</p>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
