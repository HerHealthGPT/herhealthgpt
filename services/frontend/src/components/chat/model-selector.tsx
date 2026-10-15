"use client";

import type { TriageModelOption } from "@/lib/api/types";
import { useI18n } from "@/i18n/locale-provider";

type ModelSelectorProps = {
  models: TriageModelOption[];
  selectedId: string;
  onSelect: (modelId: string) => void;
  /** Locked once a chat has a message in it: a transcript that mixes
   *  versions cannot be compared with anything. */
  locked: boolean;
};

/**
 * Which version answers this chat, for evaluation sessions.
 *
 * The labels come from the server and say nothing about what each version
 * is, on purpose. Rendered only when the server offers more than one — an
 * ordinary deployment has a single path and no selector. A native `select`
 * so it is a real control on a phone and with a keyboard.
 */
export function ModelSelector({ models, selectedId, onSelect, locked }: ModelSelectorProps) {
  const { m } = useI18n();
  if (models.length < 2) {
    return null;
  }

  return (
    <label className="flex min-w-0 items-center gap-2 text-sm">
      <span className="sr-only sm:not-sr-only sm:text-muted-foreground">{m.chat.version}</span>
      <select
        className="h-9 min-w-0 rounded-md border border-input bg-background px-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60"
        value={selectedId}
        disabled={locked}
        title={locked ? m.chat.versionLocked : undefined}
        onChange={(event) => onSelect(event.target.value)}
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.label}
          </option>
        ))}
      </select>
    </label>
  );
}
