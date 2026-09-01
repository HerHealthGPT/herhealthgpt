import { AlertTriangle, CheckCircle2, PhoneCall, Siren } from "lucide-react";

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

const toneIcon = {
  calm: CheckCircle2,
  urgent: PhoneCall,
  emergency: Siren,
} as const;

type ConclusionCardProps = {
  decision: TriageDecision;
  onStartNewChat: () => void;
};

export function ConclusionCard({ decision, onStartNewChat }: ConclusionCardProps) {
  if (decision.action_code === null) {
    return null;
  }

  const display = actionDisplay[decision.action_code];
  const Icon = toneIcon[display.tone];

  return (
    <Card className={cn("border shadow-sm", surfaceClassesForTone(display.tone))}>
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
              {display.heading}
            </CardTitle>
            <CardDescription className="mt-1 text-sm leading-relaxed">
              {display.body}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-sm leading-relaxed text-foreground/90">{decision.rationale}</p>

        {decision.matching_conditions.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              May be related to
            </p>
            <div className="flex flex-wrap gap-1.5">
              {decision.matching_conditions.map((conditionId) => (
                <Badge key={conditionId} variant="secondary">
                  {humanizeConditionId(conditionId)}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {decision.citations.length > 0 ? (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            Grounded in {decision.citations.length} cited source
            {decision.citations.length === 1 ? "" : "s"} from our health library.
          </p>
        ) : null}

        <div className="flex items-start gap-2 rounded-lg bg-background/60 p-3 text-xs text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <p>
            This is urgency guidance from cited sources, not a diagnosis. We&apos;re
            an AI tool, not a clinician — if you&apos;re ever unsure, please see a
            doctor.
          </p>
        </div>
      </CardContent>

      <CardFooter className="justify-end bg-transparent">
        <Button
          onClick={onStartNewChat}
          className={display.tone !== "calm" ? buttonClassesForTone(display.tone) : undefined}
        >
          Start a new chat
        </Button>
      </CardFooter>
    </Card>
  );
}
