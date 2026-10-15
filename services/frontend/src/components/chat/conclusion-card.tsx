"use client";

import { AlertTriangle } from "lucide-react";

import { CitedSources } from "@/components/chat/cited-sources";
import { UnreviewedModelNotice } from "@/components/chat/unreviewed-model-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { TriageDecision } from "@/lib/api/types";
import {
  actionDisplay,
  buttonClassesForTone,
  headingClassesForTone,
  humanizeConditionId,
  surfaceClassesForTone,
} from "@/lib/design/action";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n/locale-provider";

type ConclusionCardProps = {
  decision: TriageDecision;
  onStartNewChat: () => void;
};

export function ConclusionCard({ decision, onStartNewChat }: ConclusionCardProps) {
  const { m } = useI18n();
  if (decision.action_code === null) {
    return null;
  }

  const display = actionDisplay[decision.action_code];
  // Keyed on the action code, not the tone — see ActionDisplay.icon. The
  // same icon appears on the landing page's urgency scale, so what she was
  // shown before signing up is what she gets in the answer.
  const Icon = display.icon;

  return (
    <Card className={cn("border shadow-sm animate-in fade-in slide-in-from-bottom-3 duration-500", surfaceClassesForTone(display.tone))}>
      <CardHeader>
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-full bg-background/60",
              headingClassesForTone(display.tone),
            )}
          >
            <Icon className="size-5" />
          </span>
          <div>
            <CardTitle className={cn("text-lg", headingClassesForTone(display.tone))}>
              {m.actions[decision.action_code].heading}
            </CardTitle>
            <CardDescription className="mt-1 text-sm leading-relaxed">
              {m.actions[decision.action_code].body}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <UnreviewedModelNotice model={decision.reasoning_model} />
        <p className="text-sm leading-relaxed text-foreground/90">{decision.rationale}</p>

        {decision.matching_conditions.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              {m.chat.patterns}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {decision.matching_conditions.map((conditionId) => (
                <Badge key={conditionId} variant="secondary">
                  {m.conditions[conditionId] ?? humanizeConditionId(conditionId)}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        <CitedSources passages={decision.cited_passages ?? []} />

        {decision.red_flag_id !== null ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {m.chat.redFlagNote}
          </p>
        ) : null}

        {/* Amber, not the urgency reds and not brand berry: `globals.css`
            reserves the reds for the urgency verdict itself, and colouring a
            standing notice the same way would compete with the thing it sits
            under. Amber reads as "read this" without reading as "emergency".
            Text sits at full foreground rather than muted — a disclaimer
            nobody can be bothered to read is not a disclaimer. */}
        <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
          <AlertTriangle
            className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-500"
            aria-hidden
          />
          <div className="text-xs leading-relaxed">
            <p className="font-bold tracking-wide text-amber-700 dark:text-amber-400">
              {m.chat.disclaimerTitle}
            </p>
            <p className="mt-1 text-foreground/90">
              {m.chat.disclaimer}
            </p>
          </div>
        </div>
      </CardContent>

      <CardFooter className="justify-end bg-transparent">
        <Button
          onClick={onStartNewChat}
          className={display.tone !== "calm" ? buttonClassesForTone(display.tone) : undefined}
        >
          {m.chat.startNewChat}
        </Button>
      </CardFooter>
    </Card>
  );
}
