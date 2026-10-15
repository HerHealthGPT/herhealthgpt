"use client";

import { TriangleAlert } from "lucide-react";

import type { DecisionReasoningModel } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

/**
 * Marks an answer produced by a model that is not cleared to give guidance.
 *
 * The fine-tuned adapter was trained on `gold_seeds_styled.csv`, in which no
 * answer contains a question mark — CLAUDE.md records that this collapsed
 * clarification-seeking from 0.856 to 0.000 and pushed French and Arabic
 * under-triage to 0.994. So an answer from it is a measurement, not advice,
 * and has to say so where the answer is.
 *
 * Renders nothing for a reviewed model, and nothing at all on a deployment
 * with the selector off, since the backend then omits `reasoning_model`.
 */
export function UnreviewedModelNotice({
  model,
}: {
  model?: DecisionReasoningModel;
}) {
  const { m } = useI18n();
  if (!model || model.reviewed) {
    return null;
  }

  return (
    <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-2.5 text-xs leading-relaxed text-destructive">
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      <p>
        {m.chat.unreviewed(model.label)}
      </p>
    </div>
  );
}
