import { BookOpen, ExternalLink } from "lucide-react";

import type { CitedPassage } from "@/lib/api/types";
import { sourceLabel } from "@/lib/source-labels";

type CitedSourcesProps = {
  passages: CitedPassage[];
  /**
   * `question` — a clarifying question. Shows source links only.
   * `conclusion` — the final answer. Shows a short list of sources, each
   * with the one sentence it rests on.
   */
  variant?: "conclusion" | "question";
};

/** Enough to recognise the claim, short enough to skim. Full text is one
 *  click away on the source's own page, which is where a reader who wants
 *  the whole thing should end up anyway. */
const QUOTE_MAX_CHARS = 180;

/** How many sources a conclusion lists before collapsing the rest into a
 *  count. Five citations of the same NHS page is noise, not provenance. */
const MAX_LISTED = 4;

function shortenQuote(text: string): string {
  const clean = text.trim();
  if (clean.length <= QUOTE_MAX_CHARS) {
    return clean;
  }
  // Cut at a word boundary so the ellipsis does not land mid-word.
  const cut = clean.slice(0, QUOTE_MAX_CHARS);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > 80 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

/** One entry per distinct source page, keeping the first passage from each.
 *
 *  Several cited passages routinely come from the same page — the retrieval
 *  index is sentence-level, so one NHS article can supply three of them. As
 *  a list of "sources" that reads as padding; deduplicating by URL makes the
 *  count mean what a reader assumes it means. */
function distinctSources(passages: CitedPassage[]): CitedPassage[] {
  const seen = new Set<string>();
  const out: CitedPassage[] = [];
  for (const passage of passages) {
    const key = passage.url ?? `${passage.source_id}:${passage.id}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(passage);
  }
  return out;
}

function SourceLink({ passage }: { passage: CitedPassage }) {
  const label = sourceLabel(passage.source_id);
  if (!passage.url) {
    return <span className="font-medium text-foreground/70">{label}</span>;
  }
  return (
    <a
      href={passage.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
    >
      {label}
      <ExternalLink className="size-3 shrink-0" aria-hidden />
    </a>
  );
}

/**
 * What a decision rests on.
 *
 * Two deliberately different shapes, because the two moments ask different
 * things of a reader. Mid-conversation she is being asked a question and
 * wants to answer it — a wall of quoted source text between her and the
 * reply is friction, so a question shows only where the material came from.
 * At the conclusion she is deciding what to do, and *there* the quote is the
 * point: this project's verification protocol rests on every claim being
 * traceable to a real sentence on a real page.
 *
 * Quotes are shortened but never paraphrased. A paraphrase in the UI would
 * quietly break the one property that makes the knowledge base checkable,
 * so the text is either the source's own words or it is a link.
 */
export function CitedSources({ passages, variant = "conclusion" }: CitedSourcesProps) {
  if (passages.length === 0) {
    return null;
  }

  const sources = distinctSources(passages);

  if (variant === "question") {
    return (
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span>Based on</span>
        {sources.slice(0, MAX_LISTED).map((passage, index) => (
          <span key={passage.id} className="inline-flex items-center gap-2">
            {index > 0 ? <span aria-hidden>·</span> : null}
            <SourceLink passage={passage} />
          </span>
        ))}
      </p>
    );
  }

  const listed = sources.slice(0, MAX_LISTED);
  const hidden = sources.length - listed.length;

  return (
    <div className="space-y-2.5">
      {/* Reads as a real heading rather than a caption. The quotes underneath
          are the whole basis of the answer, and a grey micro-label sent the
          opposite signal — people skipped straight past the evidence. */}
      <p className="flex items-center gap-1.5 text-sm font-semibold text-primary">
        <BookOpen className="size-4" aria-hidden />
        Sources
      </p>

      <ul className="space-y-2.5">
        {listed.map((passage) => (
          <li key={passage.id} className="border-l-2 border-primary/30 pl-3">
            <p className="text-xs leading-relaxed text-foreground/80">
              &ldquo;{shortenQuote(passage.text)}&rdquo;
            </p>
            <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs">
              <SourceLink passage={passage} />
              {passage.passage_type === "live_fallback" ? (
                <span className="text-muted-foreground/80">
                  · looked up live
                </span>
              ) : null}
            </p>
          </li>
        ))}
      </ul>

      {hidden > 0 ? (
        <p className="text-xs text-muted-foreground">
          and {hidden} more {hidden === 1 ? "source" : "sources"}
        </p>
      ) : null}
    </div>
  );
}
