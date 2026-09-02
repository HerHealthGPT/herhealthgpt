import { CheckCircle2, Circle } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type GettingStartedCardProps = {
  hasChats: boolean;
};

export function GettingStartedCard({ hasChats }: GettingStartedCardProps) {
  return (
    <Card className="border-dashed border-border bg-muted/20">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Getting started</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          <li className="flex items-start gap-3 text-sm">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>Account created</span>
          </li>
          <li className="flex items-start gap-3 text-sm">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>Email verified</span>
          </li>
          <li className="flex items-start gap-3 text-sm">
            {hasChats ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
            ) : (
              <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            )}
            <span className={hasChats ? "" : "text-muted-foreground"}>
              Start your first health chat
            </span>
          </li>
        </ol>
      </CardContent>
    </Card>
  );
}
