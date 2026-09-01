"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";

/**
 * A response can take anywhere from a few seconds to well over a minute —
 * measured directly against the real backend, not assumed. A bare spinner
 * left sitting that long reads as frozen. Rotating through a few honest,
 * specific phrases (never "diagnosing" — this app never does that) keeps it
 * feeling alive without promising a speed the backend can't guarantee.
 */
const PHRASES = [
  "Reading what you shared…",
  "Thinking this through…",
  "Checking trusted health sources…",
  "Still working on it — thanks for your patience…",
];

const ROTATE_MS = 6000;

export function ThinkingIndicator({ label }: { label?: string }) {
  const [phraseIndex, setPhraseIndex] = useState(0);

  useEffect(() => {
    if (label) {
      return;
    }
    const interval = setInterval(() => {
      setPhraseIndex((current) => Math.min(current + 1, PHRASES.length - 1));
    }, ROTATE_MS);
    return () => clearInterval(interval);
  }, [label]);

  const text = label ?? PHRASES[phraseIndex];

  return (
    <div className="flex items-end gap-2.5">
      <Avatar size="sm" className="mb-0.5 shrink-0">
        <AvatarFallback className="bg-primary/10 text-primary">
          <Sparkles className="size-3.5" />
        </AvatarFallback>
      </Avatar>
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm bg-muted px-4 py-2.5 text-sm text-muted-foreground">
        <span className="flex gap-1">
          <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-current" />
        </span>
        <span>{text}</span>
      </div>
    </div>
  );
}
