import Link from "next/link";
import { Download, Lock, Upload } from "lucide-react";

import { STEP_ILLUSTRATIONS } from "@/components/cycle-guide/step-illustrations";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { requestMessages } from "@/i18n/server";
import { CYCLE_TEMPLATE_URL, routes } from "@/lib/routes";

/** The importer's columns; see backend `CSV_TEMPLATE_HEADER`. */
const COLUMNS = ["date", "flow", "symptoms", "pain_intensity", "pregnancy_test"] as const;

/** An example shown as a table, never offered as a download: uploading it
 *  would import someone else's made-up period as hers. */
const EXAMPLE_ROWS = [
  ["2026-10-01", "heavy", "cramps;lower_back_pain", "moderate", ""],
  ["2026-10-02", "medium", "cramps", "mild", ""],
  ["2026-10-03", "light", "", "", ""],
  ["2026-10-04", "spotting", "", "", ""],
  ["2026-10-15", "", "bloating", "", "negative"],
];

export async function generateMetadata() {
  return { title: (await requestMessages()).cycleGuide.pageTitle };
}

/**
 * How to prepare a cycle-data file for the importer, step by step.
 *
 * Public, like the landing page: someone deciding whether to sign up should
 * be able to see what sharing their cycle history involves and what is kept.
 * The column names and allowed words are the importer's own English tokens
 * in every language, shown with their meaning, because a translated word in
 * the file would be rejected.
 */
export default async function CycleImportGuidePage() {
  const m = await requestMessages();
  const g = m.cycleGuide;

  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        <section className="border-b border-border/60 bg-gradient-to-b from-accent/40 to-background">
          <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 sm:py-16">
            <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              {g.pageTitle}
            </h1>
            <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted-foreground">{g.lead}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button size="lg" asChild>
                <a href={CYCLE_TEMPLATE_URL} download>
                  <Download className="size-4" />
                  {g.downloadTemplate}
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href={`${routes.settings}#cycle-data`}>
                  <Upload className="size-4" />
                  {g.goToUpload}
                </Link>
              </Button>
            </div>
          </div>
        </section>

        <section className="py-12 sm:py-14">
          <ol className="mx-auto grid max-w-4xl gap-6 px-4 sm:grid-cols-2 sm:px-6">
            {g.steps.map((step, index) => {
              const Illustration = STEP_ILLUSTRATIONS[index];
              return (
                <li
                  key={step.title}
                  className="rounded-2xl border border-border/70 bg-card p-5 shadow-sm"
                >
                  {Illustration ? <Illustration className="mx-auto h-32 w-full max-w-[220px]" /> : null}
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-primary">
                    {g.stepLabel(index + 1)}
                  </p>
                  <h2 className="mt-1 text-lg font-semibold tracking-tight">{step.title}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="border-y border-border/60 bg-muted/20 py-12">
          <div className="mx-auto max-w-4xl space-y-10 px-4 sm:px-6">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">{g.exampleTitle}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{g.exampleNote}</p>
              <div
                className="mt-4 overflow-x-auto rounded-xl border border-border/70 bg-background"
                dir="ltr"
              >
                <table className="w-full min-w-[560px] text-left font-mono text-xs">
                  <thead className="bg-muted">
                    <tr>
                      {COLUMNS.map((column) => (
                        <th key={column} className="px-3 py-2 font-semibold">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {EXAMPLE_ROWS.map((row) => (
                      <tr key={row[0]} className="border-t border-border/60">
                        {row.map((cell, index) => (
                          <td key={index} className="px-3 py-2 text-foreground/80">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h2 className="text-2xl font-semibold tracking-tight">{g.columnsTitle}</h2>
              <dl className="mt-4 space-y-3">
                {COLUMNS.map((column) => (
                  <div key={column} className="grid gap-1 sm:grid-cols-[11rem_1fr] sm:gap-4">
                    <dt className="font-mono text-sm font-semibold" dir="ltr">
                      {column}
                    </dt>
                    <dd className="text-sm leading-relaxed text-muted-foreground">
                      {g.columns[column]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div>
              <h2 className="text-2xl font-semibold tracking-tight">{g.valuesTitle}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{g.valuesNote}</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {(["flow", "pain_intensity", "pregnancy_test", "symptoms"] as const).map((column) => (
                  <div key={column} className="rounded-xl border border-border/70 bg-background p-4">
                    <p className="font-mono text-sm font-semibold" dir="ltr">
                      {column}
                    </p>
                    <ul className="mt-2 space-y-1.5">
                      {Object.entries(g.values[column] ?? {}).map(([token, meaning]) => (
                        <li key={token} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                          <code className="rounded bg-muted px-1.5 py-0.5 text-xs" dir="ltr">
                            {token}
                          </code>
                          <span className="text-muted-foreground">{meaning}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="py-12">
          <div className="mx-auto grid max-w-4xl gap-8 px-4 sm:px-6 lg:grid-cols-2">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">{g.tipsTitle}</h2>
              <ul className="mt-3 list-disc space-y-2 ps-5 text-sm leading-relaxed text-muted-foreground">
                {g.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-2xl border border-border/70 bg-card p-5">
              <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
                <Lock className="size-4 text-primary" aria-hidden />
                {g.privacyTitle}
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{g.privacy}</p>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{g.notDiagnosis}</p>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
