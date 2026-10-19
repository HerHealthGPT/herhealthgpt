"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, FileText, Lock, Trash2, Upload } from "lucide-react";
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
  deleteStoredFile,
  downloadStoredFile,
  listStoredFiles,
  uploadStoredFile,
} from "@/lib/api/accounts";
import { ApiError, friendlyApiError } from "@/lib/api/errors";
import type { StoredFile } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

/** Sent when a file is kept from somewhere else (the cycle-data import), so
 *  the list below shows it without a reload. */
export const STORED_FILES_CHANGED = "herhealth:stored-files-changed";

/**
 * The files she chose to keep, each deleted automatically 30 days after
 * upload (ADR 0020). Download, delete, or upload another.
 */
export function StoredFilesCard() {
  const { m, locale } = useI18n();
  const f = m.account.files;
  const fileInput = useRef<HTMLInputElement>(null);
  // Undefined while loading; empty once loaded with nothing kept.
  const [files, setFiles] = useState<StoredFile[] | undefined>(undefined);
  const [busy, setBusy] = useState<string | null>(null);

  const errorMessage = useCallback(
    (error: unknown): string => {
      if (error instanceof ApiError) {
        const detail = error.detail as unknown;
        if (detail && typeof detail === "object" && "reason" in detail) {
          const reason = String((detail as { reason: unknown }).reason);
          if (f.errors[reason]) return f.errors[reason];
        }
      }
      return friendlyApiError(error);
    },
    [f],
  );

  const load = useCallback(() => {
    listStoredFiles()
      .then(setFiles)
      .catch(() => setFiles([]));
  }, []);

  useEffect(() => {
    load();
    window.addEventListener(STORED_FILES_CHANGED, load);
    return () => window.removeEventListener(STORED_FILES_CHANGED, load);
  }, [load]);

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    setBusy("upload");
    try {
      const kept = await uploadStoredFile(file);
      setFiles((current) => [kept, ...(current ?? [])]);
      toast.success(f.saved);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function handleDownload(file: StoredFile) {
    setBusy(file.id);
    try {
      await downloadStoredFile(file);
    } catch (error) {
      toast.error(errorMessage(error));
      load();
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete(file: StoredFile) {
    setBusy(file.id);
    try {
      await deleteStoredFile(file.id);
      setFiles((current) => (current ?? []).filter((item) => item.id !== file.id));
      toast.success(f.removed);
    } catch (error) {
      toast.error(errorMessage(error));
      load();
    } finally {
      setBusy(null);
    }
  }

  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });

  return (
    <Card id="files" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="text-lg">{f.title}</CardTitle>
        <CardDescription>{f.lead}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <input
          ref={fileInput}
          type="file"
          className="hidden"
          accept=".csv,.json,.xml,.zip,.pdf,.txt"
          onChange={(event) => void handleUpload(event.target.files?.[0])}
        />

        {files === undefined ? null : files.length === 0 ? (
          <p className="text-muted-foreground">{f.none}</p>
        ) : (
          <ul className="divide-y divide-border/60 rounded-lg border border-border/60">
            {files.map((file) => (
              <li key={file.id} className="flex flex-wrap items-center gap-3 p-3">
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium" dir="auto">
                    {file.filename}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {f.size(file.size_bytes)} · {f.deletesOn(date(file.expires_at))}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy !== null}
                    onClick={() => void handleDownload(file)}
                  >
                    <Download className="size-4" />
                    {f.download}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={busy !== null}
                    aria-label={`${f.remove} ${file.filename}`}
                    onClick={() => void handleDelete(file)}
                  >
                    <Trash2 className="size-4" />
                    <span className="sr-only sm:not-sr-only">{f.remove}</span>
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="space-y-1">
          <Button
            type="button"
            variant="outline"
            disabled={busy !== null}
            onClick={() => fileInput.current?.click()}
          >
            <Upload className="size-4" />
            {busy === "upload" ? f.uploading : f.upload}
          </Button>
          <p className="text-xs text-muted-foreground">{f.kinds}</p>
        </div>

        <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
          <Lock className="mt-0.5 size-3.5 shrink-0" />
          <p>{f.privacy}</p>
        </div>
      </CardContent>
    </Card>
  );
}
