/** Human names for the five sources in knowledge/sources.yaml. */
export const SOURCE_LABELS: Record<string, string> = {
  nhs: "NHS",
  medlineplus: "MedlinePlus",
  womenshealth: "Office on Women's Health",
  nichd: "NICHD",
  cdc: "CDC",
};

export function sourceLabel(sourceId: string): string {
  return SOURCE_LABELS[sourceId] ?? sourceId;
}
