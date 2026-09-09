/**
 * Human, warm copy and visual tone for each of the four action codes.
 *
 * The model's own `rationale` carries the specific, cited reasoning; this is
 * the guaranteed, unambiguous headline shown alongside it — never solely
 * relying on the model's own phrasing for the one thing that actually has
 * to be crystal clear: what to do next. No locale-specific instructions
 * ("call 111", "see your GP") are invented here — see CLAUDE.md: those are
 * resolved per locale server-side, not something this repo has real data
 * for from Egypt yet, so this stays deliberately general rather than
 * fabricating a phone number or service name.
 */
import type { LucideIcon } from "lucide-react";
import { CalendarDays, Clock, House, Siren } from "lucide-react";

import type { ActionCode } from "@/lib/api/types";
import {
  urgencyButtonClasses,
  urgencyHeadingClasses,
  urgencySurfaceClasses,
  type UrgencyActionCode,
} from "./urgency";

export type ActionTone = "calm" | "urgent" | "emergency";

export type ActionDisplay = {
  heading: string;
  body: string;
  tone: ActionTone;
  /**
   * One icon per action code, and the reason it lives here rather than in a
   * component is that two places draw it: the conclusion card and the
   * landing page's urgency scale. They disagreed until 2026-09-10 — the
   * landing page taught house / calendar / clock / siren, then the real
   * answer arrived wearing a different set, so the page was advertising a
   * product it did not match.
   *
   * It is keyed on the action code, not on `tone`. The card previously
   * picked its icon by tone, and because SELF_CARE and ROUTINE_APPOINTMENT
   * share the "calm" tone they drew the *same* icon — collapsing the very
   * distinction the user most needs: manage this at home, or book an
   * appointment.
   */
  icon: LucideIcon;
};

export const actionDisplay: Record<ActionCode, ActionDisplay> = {
  SELF_CARE: {
    icon: House,
    heading: "Self-care should be enough",
    body: "Based on what you've shared, this looks like something you can manage yourself for now. If it changes or doesn't settle, it's worth checking in with a doctor.",
    tone: "calm",
  },
  ROUTINE_APPOINTMENT: {
    icon: CalendarDays,
    heading: "Worth a routine appointment",
    body: "Nothing here looks urgent, but it's worth arranging a non-urgent appointment with a healthcare professional to look into it.",
    tone: "calm",
  },
  URGENT_SAME_DAY: {
    icon: Clock,
    heading: "Please get seen today",
    body: "What you've described should be looked at by a healthcare professional the same day — please arrange to be seen today.",
    tone: "urgent",
  },
  EMERGENCY: {
    icon: Siren,
    heading: "This needs emergency care now",
    body: "Please seek emergency care right away — go to the nearest emergency department or call your local emergency number now.",
    tone: "emergency",
  },
};

const isUrgencyTone = (tone: ActionTone): tone is "urgent" | "emergency" =>
  tone === "urgent" || tone === "emergency";

const toneToActionCode: Record<"urgent" | "emergency", UrgencyActionCode> = {
  urgent: "URGENT_SAME_DAY",
  emergency: "EMERGENCY",
};

/** Surface (card background/border/text) classes for a tone — calm tones use
 * ordinary brand styling; urgent/emergency reach for the reserved urgency
 * palette (see urgency.ts's own rule: brand primary never means clinical
 * urgency). */
export function surfaceClassesForTone(tone: ActionTone): string {
  if (isUrgencyTone(tone)) {
    return urgencySurfaceClasses[toneToActionCode[tone]];
  }
  return "border-primary/25 bg-primary/5 text-foreground";
}

export function headingClassesForTone(tone: ActionTone): string {
  if (isUrgencyTone(tone)) {
    return urgencyHeadingClasses[toneToActionCode[tone]];
  }
  return "text-foreground";
}

export function buttonClassesForTone(tone: ActionTone): string {
  if (isUrgencyTone(tone)) {
    return urgencyButtonClasses[toneToActionCode[tone]];
  }
  return "";
}

/** "uterine_fibroids" -> "Uterine fibroids". A reformatting of real data
 * returned by the API, never an invented label. */
export function humanizeConditionId(id: string): string {
  const spaced = id.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
