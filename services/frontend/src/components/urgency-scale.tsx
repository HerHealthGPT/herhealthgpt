import type { ActionCode } from "@/lib/api/types";
import { actionDisplay } from "@/lib/design/action";

/**
 * The four answers a consultation can end with, as an ordered scale.
 *
 * Rendered in two places — the landing page, where it sets expectations
 * before signing up, and the dashboard, where it explains what a completed
 * chat's verdict meant. One component rather than two, because the moment
 * they drift is the moment the promise stops matching the product; the
 * previous pair of hand-written lists already had diverged on icons.
 *
 * Icons and headings come from `actionDisplay`, the same table the
 * conclusion card renders. Only the `detail` line is written here:
 * `actionDisplay.body` addresses someone who has just been given that
 * verdict, and reads oddly as a description of a category.
 *
 * Ordered, so `<ol>` — and the only reason a sequence device is justified
 * at all. `knowledge/actions.yaml` defines the same order by `severity`.
 */
const STEPS = [
  {
    code: "SELF_CARE",
    detail: "Nothing suggests you need to contact anyone right now.",
    weight: "font-normal text-muted-foreground",
  },
  {
    code: "ROUTINE_APPOINTMENT",
    detail: "Worth looking into, but it doesn't need attention today.",
    weight: "font-normal text-foreground/80",
  },
  {
    code: "URGENT_SAME_DAY",
    detail: "This shouldn't wait for a routine appointment.",
    weight: "font-medium text-foreground",
  },
  {
    code: "EMERGENCY",
    detail: "Seek emergency care immediately.",
    weight: "font-semibold text-primary",
  },
] as const satisfies ReadonlyArray<{
  code: ActionCode;
  detail: string;
  weight: string;
}>;

export function UrgencyScale({ className }: { className?: string }) {
  return (
    <ol className={`grid gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-4 ${className ?? ""}`}>
      {STEPS.map((step, index) => {
        const display = actionDisplay[step.code];
        const Icon = display.icon;

        return (
          <li key={step.code}>
            {/* The rule is the scale. It gains weight left to right, so the
                ordering reads without numbering it. */}
            <div
              className="h-1 rounded-full bg-primary"
              style={{ opacity: 0.25 + index * 0.25 }}
              aria-hidden
            />

            {/* The icon tint climbs with the rule, so severity is legible
                from the shapes alone. Deliberately not the `--urgency-*`
                reds: `globals.css` reserves those for a real verdict on a
                real symptom, and alarm colour on an explainer is a promise
                this block is not in a position to make. */}
            <span
              className="mt-4 flex size-9 items-center justify-center rounded-xl text-primary"
              style={{
                backgroundColor: `color-mix(in oklch, var(--primary) ${8 + index * 6}%, transparent)`,
              }}
              aria-hidden
            >
              <Icon className="size-4.5" />
            </span>

            <p className={`mt-3 text-sm ${step.weight}`}>{display.heading}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {step.detail}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
