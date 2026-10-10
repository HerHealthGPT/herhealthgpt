import { Info } from "lucide-react";

import { UnreviewedModelNotice } from "@/components/chat/unreviewed-model-notice";
import { Card, CardContent } from "@/components/ui/card";
import type { DecisionReasoningModel } from "@/lib/api/types";

/**
 * An off-scope message, refused — see ADR 0014.
 *
 * Deliberately not a ConclusionCard variant. A conclusion carries an urgency
 * headline, matched patterns and cited sources; a decline has none of those
 * by schema, and reusing that card would leave a row of empty affordances
 * implying the system assessed something it did not. Neutral tone, no
 * urgency palette: this is not a clinical outcome and must not read as one.
 *
 * No "Start a new chat" button either, unlike a conclusion. Declining does
 * not conclude the consultation server-side (routes.py leaves the session
 * active), so the composer stays open and she can ask something in scope
 * next. An off-scope question should cost her nothing.
 */
export function DeclineCard({
  rationale,
  reasoningModel,
}: {
  rationale: string;
  reasoningModel?: DecisionReasoningModel;
}) {
  return (
    <Card className="animate-in fade-in slide-in-from-bottom-3 border-border/60 bg-muted/40 shadow-none duration-500">
      <CardContent className="flex items-start gap-3 py-1">
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-background/70 text-muted-foreground">
          <Info className="size-4" />
        </span>
        <div className="space-y-2">
          <UnreviewedModelNotice model={reasoningModel} />
          <p className="text-sm leading-relaxed text-foreground/90">{rationale}</p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            No urgency level and no sources are shown here, because nothing was
            assessed.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
