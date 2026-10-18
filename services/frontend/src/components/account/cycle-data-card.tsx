"use client";

import { CycleDataImport } from "@/components/account/cycle-data-import";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useI18n } from "@/i18n/locale-provider";

/** Cycle data in Settings: the same import flow the chat's attach button opens. */
export function CycleDataCard() {
  const { m } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{m.account.cycle.title}</CardTitle>
        <CardDescription>{m.account.cycle.lead}</CardDescription>
      </CardHeader>
      <CardContent>
        <CycleDataImport />
      </CardContent>
    </Card>
  );
}
