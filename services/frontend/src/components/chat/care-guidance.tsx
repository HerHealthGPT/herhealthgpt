"use client";

import { useState } from "react";
import { Clock, MessageCircleQuestion, Siren } from "lucide-react";

import { useI18n } from "@/i18n/locale-provider";
import type { CareGuidance as CareGuidanceData } from "@/lib/api/types";
import { conditionLabel } from "@/lib/condition-labels";
import { urgencyHeadingClasses } from "@/lib/design/urgency";

/** Lines shown before "Show all": a long list of alarms buries the first one. */
const VISIBLE = 4;

/**
 * When to get help, under every informational answer.
 *
 * An informational answer carries no urgency level, and measured on the
 * benchmark the model's own prose rarely said when to seek care (ADR 0018).
 * This section does not depend on that prose: the backend assembles it from
 * the knowledge base (`triage/context.py`, `care_guidance`) — warning signs
 * from `red_flags.yaml` that touch the topic's symptoms, most severe first,
 * and the topic's baseline from `conditions.yaml` — and it always ends by
 * inviting her to describe her own symptoms, which is how she gets an
 * urgency level of her own.
 *
 * It says nothing about her. Warning signs are "if you have"; the baseline is
 * what our sources advise for symptoms linked to a topic, never "you have".
 */
export function CareGuidance({ guidance }: { guidance: CareGuidanceData }) {
  const { m } = useI18n();
  const c = m.chat.care;
  const [showAll, setShowAll] = useState(false);

  const emergency = guidance.warning_signs.filter((sign) => sign.action === "EMERGENCY");
  const urgent = guidance.warning_signs.filter((sign) => sign.action === "URGENT_SAME_DAY");
  const total = emergency.length + urgent.length;
  const emergencyShown = showAll ? emergency : emergency.slice(0, VISIBLE);
  const urgentShown = showAll
    ? urgent
    : urgent.slice(0, Math.max(0, VISIBLE - emergencyShown.length));
  const label = (ruleId: string) => c.signs[ruleId] ?? ruleId.replaceAll("_", " ");

  return (
    <section className="mt-3 space-y-3 rounded-xl border border-border/70 bg-background/70 p-3 text-sm">
      <p className="font-semibold">{c.title}</p>

      {emergencyShown.length > 0 ? (
        <div>
          <p className={`flex items-center gap-1.5 font-medium ${urgencyHeadingClasses.EMERGENCY}`}>
            <Siren className="size-4" aria-hidden />
            {c.emergency}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 ps-6">
            {emergencyShown.map((sign) => (
              <li key={sign.rule_id}>{label(sign.rule_id)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {urgentShown.length > 0 ? (
        <div>
          <p
            className={`flex items-center gap-1.5 font-medium ${urgencyHeadingClasses.URGENT_SAME_DAY}`}
          >
            <Clock className="size-4" aria-hidden />
            {c.urgent}
          </p>
          <ul className="mt-1 list-disc space-y-0.5 ps-6">
            {urgentShown.map((sign) => (
              <li key={sign.rule_id}>{label(sign.rule_id)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {total > VISIBLE ? (
        <button
          type="button"
          className="text-xs font-medium text-primary hover:underline"
          onClick={() => setShowAll((open) => !open)}
        >
          {showAll ? c.showFewer : c.showAll(total)}
        </button>
      ) : null}

      {guidance.topics.length > 0 ? (
        <div>
          <p className="text-muted-foreground">{c.baseline}</p>
          <ul className="mt-1 space-y-0.5">
            {guidance.topics.map((topic) => (
              <li key={topic.condition_id}>
                <span className="font-medium">{conditionLabel(topic.condition_id, m)}</span>
                {" — "}
                {m.actions[topic.baseline_action].heading}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="flex items-start gap-1.5 text-muted-foreground">
        <MessageCircleQuestion className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        {c.invite}
      </p>
    </section>
  );
}
