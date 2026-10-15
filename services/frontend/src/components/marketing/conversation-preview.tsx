"use client";

import { ExternalLink, Sparkles } from "lucide-react";
import { useI18n } from "@/i18n/locale-provider";

/**
 * A still of a real consultation, in the chat's own visual language.
 *
 * This is the landing page's main visual, and it replaces roughly eighty
 * words of prose that used to describe the product instead of showing it.
 * Bubble shapes, radii and colours are copied from `chat-message.tsx` and
 * `conclusion-card.tsx` deliberately: a preview that does not look like the
 * thing it previews is a small lie, and this one is the first impression.
 *
 * Static by design. An animated or interactive fake would invite someone to
 * type into it, and the honest version of that is the real chat, one click
 * away.
 *
 * The exchange below is illustrative copy, not a stored transcript and not
 * clinical content — it names no condition and asserts nothing about the
 * speaker's health, only the shape of a turn: she describes something, one
 * clarifying question comes back, then an urgency with a source behind it.
 */
export function ConversationPreview() {
  const { m } = useI18n();
  const p = m.home.preview;
  return (
    <div
      className="rounded-3xl border border-border/70 bg-card/90 p-4 shadow-sm sm:p-5"
      aria-label={p.label}
      role="img"
    >
      <div className="space-y-3">
        {/* Her opening message — deliberately halting and unclinical, the way
            someone actually writes when they are not sure it is worth asking. */}
        <div className="flex justify-end">
          <p className="max-w-[85%] rounded-2xl rounded-ee-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
            {p.her1}
          </p>
        </div>

        <div className="flex items-end gap-2.5">
          <span
            className="mb-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
            aria-hidden
          >
            <Sparkles className="size-3.5" />
          </span>
          <p className="max-w-[85%] rounded-2xl rounded-es-sm bg-muted px-4 py-2.5 text-sm leading-relaxed">
            {p.question}
          </p>
        </div>

        <div className="flex justify-end">
          <p className="max-w-[85%] rounded-2xl rounded-ee-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
            {p.her2}
          </p>
        </div>
      </div>

      {/* The answer. Shows the two things that make this different from a
          search box: a named urgency, and a source you can open yourself. */}
      <div className="mt-4 rounded-2xl border border-border/70 bg-background p-4">
        <p className="text-sm font-semibold">{p.resultHeading}</p>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {p.resultBody}
        </p>

        <div className="mt-3 border-s-2 border-border ps-3">
          <p className="text-xs leading-relaxed text-foreground/75">
            &ldquo;{p.quote}&rdquo;
          </p>
          <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary">
            NHS
            <ExternalLink className="size-3" aria-hidden />
          </p>
        </div>
      </div>
    </div>
  );
}
