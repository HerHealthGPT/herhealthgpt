"use client";

import { useState } from "react";

/**
 * An unDraw illustration served from `public/illustrations/`.
 *
 * **The SVG files are not in this repository, and that is deliberate.**
 * unDraw's licence lets you use the art freely, with no attribution and for
 * commercial work — but it bars collecting the assets "whether automated or
 * manual" without consent, and bars redistributing them "in packs or
 * otherwise". Committing them to a public repo sits inside that second
 * clause, and this project already excludes NICE CKS, RCOG, ACOG and UMLS
 * over licence wording, so it should not import a new grey area to decorate
 * an empty state.
 *
 * So the files are fetched by hand, kept out of git, and dropped into
 * `public/illustrations/`. `public/illustrations/README.md` lists exactly
 * which ones and what to name them.
 *
 * Until a file is there this renders nothing at all — not a broken-image
 * glyph, and not a reserved gap. Layouts using it must therefore read
 * correctly with the illustration absent, which is the right constraint
 * anyway: art is the last thing to load and the first thing a slow
 * connection drops.
 */
export type IllustrationName =
  | "conversation"
  | "sources"
  | "resolved"
  | "safety"
  | "welcome"
  | "onboarding"
  | "error"
  | "not-found"
  | "urgency";

type IllustrationProps = {
  name: IllustrationName;
  className?: string;
};

export function Illustration({ name, className }: IllustrationProps) {
  const [missing, setMissing] = useState(false);

  if (missing) {
    return null;
  }

  return (
    /* eslint-disable-next-line jsx-a11y/alt-text, @next/next/no-img-element --
       next/image adds nothing for a static SVG: no resizing, no format
       negotiation, and it demands width/height that CSS should own here.
       It also cannot fail softly, and failing softly is this component's
       whole job while the files are absent. */
    <img
      src={`/illustrations/${name}.svg`}
      alt=""
      aria-hidden
      loading="lazy"
      decoding="async"
      onError={() => setMissing(true)}
      className={className}
    />
  );
}
