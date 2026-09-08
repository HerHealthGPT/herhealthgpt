"use client";

import type { ReasoningModelSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ModelSelectorProps = {
  models: ReasoningModelSummary[];
  selectedId: string | null;
  onSelect: (modelId: string) => void;
  /** Locked mid-consultation: switching model halfway would make the
   *  transcript a mix of two models' reasoning with no way to tell which
   *  turn came from which. */
  disabled?: boolean;
};

/**
 * The two models this product can offer, as short tab labels.
 *
 * `GET /triage/models` is the authority on what is actually reachable. A
 * tab whose id is missing from that list is shown but not selectable, so
 * the header still looks like ChatGPT's switcher when the campus server
 * is not connected yet, rather than collapsing to a single pill.
 */
const PRODUCT_TABS = [
  { id: "base", shortLabel: "Base" },
  { id: "fine-tuned", shortLabel: "Fine-tuned" },
] as const;

type Tab = {
  id: string;
  shortLabel: string;
  available: boolean;
  reviewed: boolean;
  description: string;
};

function tabsFor(models: ReasoningModelSummary[]): Tab[] {
  const byId = new Map(models.map((model) => [model.id, model]));
  const tabs: Tab[] = PRODUCT_TABS.map((tab) => {
    const offered = byId.get(tab.id);
    const listed = models.length > 0;
    return {
      id: tab.id,
      shortLabel: tab.shortLabel,
      // Before the list arrives, Base is selectable so a first message
      // still uses the deployment default. Fine-tuned waits for the API
      // to name it — selecting it with no campus server would 400.
      available: offered !== undefined || (!listed && tab.id === "base"),
      reviewed: offered?.reviewed ?? tab.id === "base",
      description:
        offered?.description ??
        (tab.id === "fine-tuned"
          ? "Campus fine-tuned model is not connected."
          : "Qwen3.5-9B as published, with no fine-tuning. The default."),
    };
  });

  for (const model of models) {
    if (PRODUCT_TABS.some((tab) => tab.id === model.id)) {
      continue;
    }
    tabs.push({
      id: model.id,
      shortLabel: model.label,
      available: true,
      reviewed: model.reviewed,
      description: model.description,
    });
  }

  return tabs;
}

/**
 * Which reasoning model decides this consultation.
 *
 * ChatGPT-style segmented tabs, centred in the header as the page title.
 * Always rendered — hiding the switcher until `GET /triage/models` returns
 * made it look like the control was missing. An unreviewed or unconnected
 * tab stays visible and disabled, with the reason on hover.
 */
export function ModelSelector({
  models,
  selectedId,
  onSelect,
  disabled = false,
}: ModelSelectorProps) {
  const tabs = tabsFor(models);
  const selected =
    tabs.find((tab) => tab.id === selectedId) ??
    tabs.find((tab) => tab.available) ??
    tabs[0];

  return (
    <div
      role="tablist"
      aria-label="Reasoning model"
      className="inline-flex rounded-full bg-muted p-1"
    >
      {tabs.map((tab) => {
        const isSelected = tab.id === selected.id;
        const locked = disabled && !isSelected;
        const canSelect = tab.available && !disabled;

        const title = !tab.available
          ? tab.description
          : locked
            ? "Start a new chat to switch model"
            : tab.description;

        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isSelected}
            aria-disabled={!canSelect && !isSelected}
            disabled={!canSelect && !isSelected}
            title={title}
            onClick={() => {
              if (canSelect) {
                onSelect(tab.id);
              }
            }}
            className={cn(
              "min-w-[6.5rem] rounded-full px-4 py-1.5 text-sm font-medium whitespace-nowrap transition-colors sm:min-w-[8.5rem] sm:px-5",
              "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              isSelected
                ? tab.reviewed
                  ? "bg-background text-foreground shadow-sm"
                  : "bg-background text-destructive shadow-sm"
                : "text-muted-foreground hover:text-foreground",
              (!tab.available || locked) &&
                "cursor-not-allowed opacity-50 hover:text-muted-foreground",
            )}
          >
            {tab.shortLabel}
          </button>
        );
      })}
    </div>
  );
}
