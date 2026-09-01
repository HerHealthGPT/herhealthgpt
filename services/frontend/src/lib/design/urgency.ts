/**
 * Urgency palette for triage result screens only.
 *
 * Brand primary (--primary / berry) must never be used for clinical urgency —
 * these tokens are reserved for EMERGENCY and URGENT_SAME_DAY outcomes.
 */
export type UrgencyActionCode = "EMERGENCY" | "URGENT_SAME_DAY";

export const urgencySurfaceClasses: Record<UrgencyActionCode, string> = {
  EMERGENCY:
    "border-urgency-emergency/30 bg-urgency-emergency/10 text-urgency-emergency",
  URGENT_SAME_DAY:
    "border-urgency-urgent/30 bg-urgency-urgent/10 text-urgency-urgent",
};

export const urgencyHeadingClasses: Record<UrgencyActionCode, string> = {
  EMERGENCY: "text-urgency-emergency",
  URGENT_SAME_DAY: "text-urgency-urgent",
};

export const urgencyButtonClasses: Record<UrgencyActionCode, string> = {
  EMERGENCY:
    "bg-urgency-emergency text-urgency-emergency-foreground hover:bg-urgency-emergency/90",
  URGENT_SAME_DAY:
    "bg-urgency-urgent text-urgency-urgent-foreground hover:bg-urgency-urgent/90",
};
