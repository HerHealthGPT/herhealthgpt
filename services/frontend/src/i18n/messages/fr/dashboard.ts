import type { ArticleMessages, DashboardMessages } from "../en/dashboard";

export const dashboard: DashboardMessages = {
  oneMoment: "Un instant…",
  toDashboard: "Redirection vers votre tableau de bord…",
  subtitleActive:
    "Vous avez une discussion en cours. Reprenez où vous vous étiez arrêtée, ou recommencez.",
  subtitleCompleted: (count: number) =>
    `Vous avez terminé ${count} consultation${count > 1 ? "s" : ""}. Commencez une nouvelle discussion quand vous voulez.`,
  subtitleSaved: "Vos discussions sont enregistrées ici. Ouvrez-en une ou commencez-en une nouvelle.",
  subtitleNew:
    "Dites-nous comment vous vous sentez — nous poserons quelques questions et vous aiderons à décider quoi faire.",
  yourHome: "Votre accueil",
  greeting: (name: string) => `Bonjour, ${name}`,
  greetingAnonymous: "Bonjour",
  accountSettings: "Paramètres du compte",
  tryAgain: "Réessayer",
  chatTitle: "Discussion santé",
  ready: "Disponible",
  chatContinue: "Reprenez ou commencez une discussion",
  chatMain: "La façon principale d'utiliser HerHealthGPT",
  chatPitch:
    "Quelque chose vous préoccupe ? Décrivez-le avec vos mots. Nous poserons quelques questions si besoin, puis nous vous indiquerons dans quel délai consulter — avec des liens vers des sources fiables. Ce n'est pas un diagnostic.",
  openChat: "Ouvrir la discussion santé",
  startChat: "Commencer une discussion",
  continueChat: "Reprendre votre discussion",
  takesMinutes: "Cela prend généralement quelques minutes.",
  scaleTitle: "Les quatre réponses possibles à la fin d'une discussion",
  scaleLead:
    "Nous ne vous disons jamais ce que vous avez. Chaque consultation se termine en situant ce que vous avez décrit sur cette échelle, avec les sources qui l'appuient.",
  topicsTitle: "Sujets explorés",
  topicsLead:
    "Des situations que nos sources relient aux symptômes dont vous avez parlé — pas un diagnostic.",
  comingLater: "Bientôt",
  healthLog: "Journal de santé",
  healthLogBody: "Suivez votre cycle et vos symptômes dans le temps — nous y travaillons.",
  allSet: "Tout est prêt",
  allSetBody:
    "Votre première discussion santé est enregistrée. Ce tableau de bord affichera vos discussions récentes et des lectures issues de sources fiables.",
  gotIt: "Compris",
  oneStepLeft: "Plus qu'une étape",
  oneStepLeftBody:
    "Commencez une discussion santé quand vous êtes prête. Nous poserons quelques questions et vous aiderons à décider quoi faire.",
  startFirstChat: "Commencer votre première discussion",
  recentChats: "Discussions récentes",
  viewAll: "Tout voir",
  done: "Terminée",
  inProgress: "En cours",
  recommended: "Recommandé pour vous",
  explore: "Explorer des sujets fiables",
  recommendedLead: "Des articles des sources citées dans vos discussions, et des lectures associées.",
  exploreLead: "Sélectionnés dans MedlinePlus, le NICHD et l'Office on Women's Health.",
  articlesDisclaimer:
    "Information uniquement — pas un avis médical. Nous ne posons jamais de diagnostic. Consultez un professionnel si vous êtes inquiète.",
  fromYourChat: "De votre discussion",
  readOn: (source: string) => `Lire sur ${source}`,
  articlesInEnglish: "Les articles s'ouvrent sur le site de la source, en anglais.",
};

export const conditions: Record<string, string> = {
  pcos: "SOPK",
  endometriosis: "Endométriose",
  uterine_fibroids: "Fibromes utérins",
  normal_variation: "Variation normale",
  pelvic_inflammatory_disease: "Infection génitale haute",
  perimenopause: "Périménopause",
  ovarian_cyst: "Kystes ovariens",
  urinary_tract_infection: "Infection urinaire",
  sexually_transmitted_infection: "IST",
  thrush: "Mycose vaginale",
  bacterial_vaginosis: "Vaginose bactérienne",
  adenomyosis: "Adénomyose",
  hypothyroidism: "Maladie de la thyroïde",
  primary_ovarian_insufficiency: "Ménopause précoce",
  inherited_bleeding_disorder: "Troubles de la coagulation",
  bladder_pain: "Douleur de la vessie",
  pelvic_organ_prolapse: "Prolapsus des organes pelviens",
  iron_deficiency_anaemia: "Carence en fer",
  infertility: "Infertilité",
};

/** Curated article titles and summaries; the pages themselves are in English. */
export const articles: ArticleMessages = {
  items: {
  menstruation: { title: "Votre cycle menstruel", excerpt: "À quoi ressemble un cycle normal, les changements fréquents, et quand consulter." },
  endometriosis: { title: "Endométriose", excerpt: "Symptômes, causes, et quand une douleur pelvienne pendant les règles mérite un examen." },
  pcos: { title: "Syndrome des ovaires polykystiques", excerpt: "Règles irrégulières, changements hormonaux, et ce que disent les sources sur le SOPK." },
  fibroids: { title: "Fibromes utérins", excerpt: "Saignements abondants, pression pelvienne, et quand en parler à un professionnel." },
  uti: { title: "Infections urinaires", excerpt: "Brûlures, envies pressantes, et quand les symptômes urinaires nécessitent un traitement." },
  infertility: { title: "Infertilité", excerpt: "Essayer d'avoir un enfant, les causes fréquentes, et quand en parler à un professionnel." },
  thyroid: { title: "Maladies de la thyroïde", excerpt: "Comment les problèmes de thyroïde peuvent affecter les règles, l'énergie et le poids." },
  sti: { title: "Infections sexuellement transmissibles", excerpt: "Symptômes, dépistage, et pourquoi des pertes ou une douleur pelvienne peuvent nécessiter un contrôle." },
} as Record<string, { title: string; excerpt: string }>,
  relatedTo: (label: string) => `En lien avec ${label}, d'après votre discussion`,
  citedRecently: "Cité dans votre discussion récente",
  basedOnTopics: "D'après les sujets de vos discussions",
  fromRecentChat: "De votre discussion récente",
};

/** Source names that read differently in this language; the rest are brand names. */
export const sourceNames: Record<string, string> = {
  womenshealth: "Office on Women's Health (États-Unis)",
};
