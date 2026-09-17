import type { LucideIcon } from "lucide-react";
import { BookOpen, Heart, MessageCircle, Shield } from "lucide-react";

import type { IllustrationName } from "@/components/ui/illustration";

export type OnboardingStep = {
  id: string;
  icon: LucideIcon;
  title: string;
  body: string | null;
  bullets?: string[];
  /** Fills the tall empty column below this step's copy. Optional in
   *  practice as well as in the type: the file may not be present (see
   *  public/illustrations/README.md), and the step must read correctly
   *  without it. */
  illustration?: IllustrationName;
};

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: "welcome",
    illustration: "welcome",
    icon: Heart,
    title: "Welcome to HerHealthGPT",
    body: "Not sure what to do about a symptom? Tell us in your own words — we'll help you work out how urgently to seek care.",
  },
  {
    id: "how",
    illustration: "conversation",
    icon: MessageCircle,
    title: "How it works",
    // A paragraph rather than three numbered bullets. The bullets said
    // "clear next steps" and "only if we need to" without saying what the
    // steps are or what "need" means, so a reader finished the step knowing
    // no more than when she started. This says the concrete thing each
    // stage does — and names the one behaviour that surprises people, which
    // is that a warning sign skips the questions entirely.
    body: "Tell us what you're experiencing in your own words. We'll ask a few short follow-up questions — one at a time, and only when your answer would change the advice — then tell you how soon to seek care and why, with links to the pages it's based on. If you describe a warning sign, we skip the questions and tell you straight away.",
  },
  {
    id: "safety",
    illustration: "safety",
    icon: Shield,
    title: "Good to know",
    // The bullet this replaces read "We may mention patterns sources link to
    // symptoms — that's not a diagnosis", which is hard to parse on first
    // read and carries the load-bearing "never diagnose" framing. Said in
    // full sentences instead: what we do say, what we deliberately do not,
    // and why a warning sign short-circuits the questions.
    body: "We tell you how soon to seek care and why — never what you have. We may mention conditions your symptoms are associated with in our sources, but that is a pattern, not a diagnosis; only a clinician can give you one. If you describe something that needs urgent attention we say so straight away, without asking anything further. And if something feels urgent to you, get seen rather than waiting for a reply.",
  },
  {
    id: "sources",
    illustration: "sources",
    icon: BookOpen,
    title: "Trusted sources",
    // "When unsure, we err on the side of caution" was the vaguest line on
    // the page: a stock phrase that never said which way caution points, in
    // a section otherwise about provenance. It stands for a real rule — a
    // disagreement between sources resolves to the higher urgency — so it is
    // now stated as that rule, in the section it actually belongs to.
    body: "Everything we tell you comes from pages published by MedlinePlus, the Office on Women's Health, NICHD, the CDC and the NHS. We quote those pages directly rather than rewording them, and every quote links back to the page it came from so you can read it in full. Where two sources disagree about how urgent something is, we go with the more urgent one.",
  },
];
