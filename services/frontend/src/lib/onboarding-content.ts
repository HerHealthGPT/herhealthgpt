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
    body: null,
    bullets: [
      "Describe what's going on in a short chat",
      "We ask a few follow-up questions only if we need to",
      "You get clear next steps, with links to trusted sources",
    ],
  },
  {
    id: "safety",
    illustration: "safety",
    icon: Shield,
    title: "Good to know",
    body: "We give urgency guidance and information — we never diagnose. If something feels urgent, seek care right away rather than waiting for a reply.",
    bullets: [
      "We may mention patterns sources link to symptoms — that's not a diagnosis",
      "Warning signs are escalated immediately",
      "When in doubt, see a clinician",
    ],
  },
  {
    id: "sources",
    illustration: "sources",
    icon: BookOpen,
    title: "Trusted sources",
    body: "Answers cite reviewed pages from MedlinePlus, Office on Women's Health, NICHD, CDC, and the NHS.",
    bullets: [
      "Articles open on the original site",
      "We quote sources directly",
      "When unsure, we err on the side of caution",
    ],
  },
];
