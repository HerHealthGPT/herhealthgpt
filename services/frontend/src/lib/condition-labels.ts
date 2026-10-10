/** Short display labels for condition ids from knowledge/conditions.yaml. */
export const CONDITION_LABELS: Record<string, string> = {
  pcos: "PCOS",
  endometriosis: "Endometriosis",
  uterine_fibroids: "Uterine fibroids",
  normal_variation: "Normal variation",
  pelvic_inflammatory_disease: "Pelvic inflammatory disease",
  perimenopause: "Perimenopause",
  ovarian_cyst: "Ovarian cysts",
  urinary_tract_infection: "UTI",
  sexually_transmitted_infection: "STIs",
  thrush: "Yeast infection",
  bacterial_vaginosis: "Bacterial vaginosis",
  adenomyosis: "Adenomyosis",
  hypothyroidism: "Thyroid disease",
  primary_ovarian_insufficiency: "Early menopause",
  inherited_bleeding_disorder: "Bleeding disorders",
  bladder_pain: "Bladder pain",
  pelvic_organ_prolapse: "Pelvic organ prolapse",
  iron_deficiency_anaemia: "Iron deficiency",
  infertility: "Infertility",
};

export function conditionLabel(id: string): string {
  return CONDITION_LABELS[id] ?? id.replaceAll("_", " ");
}
