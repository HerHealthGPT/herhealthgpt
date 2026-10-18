"use client";

import { useEffect, useRef, useState } from "react";
import { Lock, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  deleteCycleData,
  getCycleData,
  previewCycleData,
  saveCycleData,
} from "@/lib/api/accounts";
import { ApiError, friendlyApiError } from "@/lib/api/errors";
import type { CycleDataPreview, CycleDataStatus, CycleDataSummary } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

/**
 * Upload a period-tracker export, check what was found, then keep it.
 *
 * One component for both places she can reach it — Settings and the chat's
 * attach button — so there is one flow to get right. Nothing is stored until
 * she presses confirm: the preview call reads the file and keeps nothing,
 * and the server validates the extraction again when it comes back. See
 * ADR 0019.
 */
export function CycleDataImport({ onSaved }: { onSaved?: () => void }) {
  const { m } = useI18n();
  const c = m.account.cycle;
  const fileInput = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<CycleDataStatus | null>(null);
  const [preview, setPreview] = useState<CycleDataPreview | null>(null);
  const [noPeriodPain, setNoPeriodPain] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<"reading" | "saving" | "deleting" | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      let loaded: CycleDataStatus;
      try {
        loaded = await getCycleData();
      } catch {
        // Show the empty state rather than an error for something she may
        // never have uploaded.
        loaded = { imported_at: null, summary: null };
      }
      if (!cancelled) setStatus(loaded);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function errorMessage(error: unknown): string {
    if (error instanceof ApiError) {
      const detail = error.detail as unknown;
      if (detail && typeof detail === "object" && "reason" in detail) {
        const reason = String((detail as { reason: unknown }).reason);
        if (c.errors[reason]) return c.errors[reason];
      }
    }
    return friendlyApiError(error);
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setBusy("reading");
    setNoPeriodPain(null);
    try {
      setPreview(await previewCycleData(file));
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setBusy("saving");
    try {
      setStatus(await saveCycleData(preview.extraction, noPeriodPain === true));
      setPreview(null);
      toast.success(c.saved);
      onSaved?.();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete() {
    setBusy("deleting");
    try {
      await deleteCycleData();
      setStatus({ imported_at: null, summary: null });
      toast.success(c.removed);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setBusy(null);
    }
  }

  const stored = status?.summary ?? null;

  return (
    <div className="space-y-4 text-sm">
      <input
        ref={fileInput}
        type="file"
        className="hidden"
        accept=".csv,.json,.xml,.zip,.pdf,.txt"
        onChange={(event) => void handleFile(event.target.files?.[0])}
      />

      {preview ? (
        <div className="space-y-3 rounded-lg border border-border/60 p-3">
          <p className="font-medium">{c.previewTitle}</p>
          <SummaryLines summary={preview.summary} />
          {preview.ask_about_period_pain ? (
            <div className="space-y-2">
              <p>{c.painQuestion}</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={noPeriodPain === true ? "default" : "outline"}
                  onClick={() => setNoPeriodPain(true)}
                >
                  {c.painYes}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={noPeriodPain === false ? "default" : "outline"}
                  onClick={() => setNoPeriodPain(false)}
                >
                  {c.painNo}
                </Button>
              </div>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" disabled={busy !== null} onClick={() => void handleConfirm()}>
              {busy === "saving" ? m.onboarding.saving : c.confirm}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setPreview(null)}>
              {m.account.cancel}
            </Button>
          </div>
        </div>
      ) : (
        <>
          {stored ? (
            <div className="space-y-1">
              <p>{c.lastUpdated(stored.days_since_last_entry)}</p>
              {!stored.fresh ? <p className="text-muted-foreground">{c.stale}</p> : null}
            </div>
          ) : status ? (
            <p className="text-muted-foreground">{c.none}</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy !== null}
              onClick={() => fileInput.current?.click()}
            >
              <Upload className="size-4" />
              {busy === "reading" ? c.reading : stored ? c.uploadAnother : c.upload}
            </Button>
            {stored ? (
              <Button
                type="button"
                variant="ghost"
                disabled={busy !== null}
                onClick={() => void handleDelete()}
              >
                {c.remove}
              </Button>
            ) : null}
          </div>
        </>
      )}

      <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
        <Lock className="mt-0.5 size-3.5 shrink-0" />
        <p>{c.privacy}</p>
      </div>
    </div>
  );
}

/** Cycle data in Settings: the same flow the chat's attach button opens. */
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

function SummaryLines({ summary }: { summary: CycleDataSummary }) {
  const { m } = useI18n();
  const c = m.account.cycle;
  const answered = Object.keys(summary.will_answer)
    .map((feature) => c.features[feature])
    .filter(Boolean);
  return (
    <ul className="space-y-1">
      <li>{c.periods(summary.periods_found)}</li>
      {summary.cycle_lengths.length ? (
        <li>{c.cycleLengths(summary.cycle_lengths.join(", "))}</li>
      ) : null}
      {summary.period_durations.length ? (
        <li>{c.periodLengths(summary.period_durations.join(", "))}</li>
      ) : null}
      {!summary.fresh ? <li className="text-muted-foreground">{c.stale}</li> : null}
      <li className="pt-1">
        {answered.length ? `${c.willAnswer} ${answered.join(", ")}` : c.willAnswerNone}
      </li>
    </ul>
  );
}
