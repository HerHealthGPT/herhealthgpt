"use client";

import { FileText } from "lucide-react";

import type { HerDataUse } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

/**
 * Her imported cycle data, shown as a source of the reply, beside the pages
 * it cites: where it came from, and what the reply took from it. Present only
 * when the backend says the reply drew on it (`her_data`).
 */
export function HerDataSource({ use }: { use: HerDataUse }) {
  const { m, locale } = useI18n();
  const h = m.chat.herData;
  const lastEntry = new Date(`${use.last_entry}T00:00:00`).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const answered = use.answered
    .map((feature) => m.account.cycle.features[feature] ?? feature.replace(/_/g, " "))
    .join(locale === "ar" ? "، " : ", ");

  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-primary/25 bg-primary/5 p-2.5 text-xs">
      <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <FileText className="size-3.5" aria-hidden />
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="font-semibold text-foreground">{h.title}</p>
        <p className="text-muted-foreground">{h.summary(h.app(use.source_app), use.periods, lastEntry)}</p>
        {use.breakdown ? <p className="text-foreground/80">{h.breakdown}</p> : null}
        {answered ? <p className="text-foreground/80">{h.answered(answered)}</p> : null}
      </div>
    </div>
  );
}
