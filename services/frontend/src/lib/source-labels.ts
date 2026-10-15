import type { Messages } from "@/i18n/messages/en";

/** Human names for the five sources in knowledge/sources.yaml. */
export const SOURCE_LABELS: Record<string, string> = {
  nhs: "NHS",
  medlineplus: "MedlinePlus",
  womenshealth: "Office on Women's Health",
  nichd: "NICHD",
  cdc: "CDC",
};

/** The source's name, in the interface language when a dictionary is given. */
export function sourceLabel(sourceId: string, m?: Messages): string {
  return m?.sourceNames[sourceId] ?? SOURCE_LABELS[sourceId] ?? sourceId;
}
