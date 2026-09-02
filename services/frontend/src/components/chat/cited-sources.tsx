import { BookOpen, ExternalLink } from "lucide-react";

import type { CitedPassage } from "@/lib/api/types";

/** Human names for the five sources in knowledge/sources.yaml. Kept here
 *  rather than fetched: these are five fixed, licence-reviewed sources, not
 *  data that varies at runtime (see CLAUDE.md's sources table). */
const SOURCE_LABELS: Record<string, string> = {
  nhs: "NHS",
  medlineplus: "MedlinePlus",
  womenshealth: "Office on Women's Health",
  nichd: "NICHD",
  cdc: "CDC",
};

function sourceLabel(sourceId: string): string {
  return SOURCE_LABELS[sourceId] ?? sourceId;
}

type CitedSourcesProps = {
  passages: CitedPassage[];
  /** Slightly tighter wording under a question than under a conclusion. */
  variant?: "conclusion" | "question";
};

/**
 * The sentences a decision actually rests on, quoted, with a link to the
 * page each came from.
 *
 * Deliberately shows the source text verbatim rather than paraphrasing it:
 * this project's whole verification protocol rests on every clinical claim
 * being traceable to a real sentence in a real page, and a paraphrase in
 * the UI would quietly break the one property that makes the knowledge base
 * checkable.
 */
export function CitedSources({ passages, variant = "conclusion" }: CitedSourcesProps) {
  if (passages.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <BookOpen className="size-3.5" />
        {variant === "question"
          ? "Why I'm asking — from our sources"
          : "What this is based on"}
      </p>

      <ul className="space-y-2">
        {passages.map((passage) => (
          <li
            key={passage.id}
            className="rounded-lg border border-border/60 bg-background/60 p-3"
          >
            <blockquote className="text-xs leading-relaxed text-foreground/85">
              &ldquo;{passage.text}&rdquo;
            </blockquote>

            <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              {passage.url ? (
                <a
                  href={passage.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  {sourceLabel(passage.source_id)}
                  <ExternalLink className="size-3" />
                </a>
              ) : (
                <span className="font-medium">{sourceLabel(passage.source_id)}</span>
              )}
              {passage.passage_type === "live_fallback" ? (
                <span className="text-muted-foreground/80">
                  · looked up live, not from our reviewed library
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
