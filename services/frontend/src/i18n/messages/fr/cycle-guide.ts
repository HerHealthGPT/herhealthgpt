import type { CycleGuideMessages } from "../en/cycle-guide";

export const cycleGuide: CycleGuideMessages = {
  pageTitle: "Ajoutez l'historique de votre cycle",
  lead: "Si vous notez vos règles, vous pouvez nous les transmettre sous forme de tableau simple. Nous nous en servons comme contexte : la discussion vous pose moins de questions sur ce que votre relevé montre déjà.",
  stepLabel: (n: number) => `Étape ${n}`,
  steps: [
    {
      title: "Téléchargez le modèle",
      body: "C'est un tableau vide à cinq colonnes. Ouvrez-le dans Excel, Google Sheets, Numbers ou tout autre tableur.",
    },
    {
      title: "Ajoutez une ligne par jour à noter",
      body: "Indiquez la date et ce que vous avez remarqué ce jour-là. Laissez une case vide s'il n'y a rien à dire. Une ligne pour chaque jour de règles est le plus utile.",
    },
    {
      title: "Enregistrez-le au format CSV",
      body: "Utilisez « Enregistrer sous » ou « Télécharger » et choisissez CSV (UTF-8). Gardez la première ligne — les noms de colonnes — telle quelle.",
    },
    {
      title: "Importez-le et vérifiez ce que nous avons trouvé",
      body: "Allez dans Compte → Données du cycle, ou appuyez sur le trombone dans la discussion. Nous vous montrons ce que nous avons lu avant d'enregistrer quoi que ce soit, et vous choisissez de le garder ou non.",
    },
  ],
  downloadTemplate: "Télécharger le modèle (CSV)",
  goToUpload: "Importer dans les paramètres du compte",
  exampleTitle: "À quoi ressemble un tableau rempli",
  exampleNote: "Un exemple seulement — utilisez vos propres dates. N'importez pas ces lignes.",
  columnsTitle: "Ce que contient chaque colonne",
  columns: {
    date: "Le jour, écrit année-mois-jour : 2026-10-05.",
    flow: "L'abondance des saignements ce jour-là. Laissez vide les jours sans règles.",
    symptoms: "Ce que vous avez remarqué. S'il y en a plusieurs, séparez-les par un point-virgule : cramps;bloating",
    pain_intensity: "Si vous aviez mal, à quel point.",
    pregnancy_test: "Seulement si vous avez fait un test de grossesse ce jour-là.",
  },
  valuesTitle: "Mots acceptés",
  valuesNote:
    "Tapez le mot anglais exactement comme indiqué, même si le reste de votre tableau est dans une autre langue. Sa signification est à côté.",
  values: {
    flow: {
      spotting: "spotting (petites pertes de sang)",
      light: "léger",
      medium: "moyen",
      heavy: "abondant",
      none: "pas de saignement",
      unspecified: "saignement, quantité non notée",
    },
    pain_intensity: { mild: "légère", moderate: "modérée", severe: "intense" },
    pregnancy_test: { positive: "positif", negative: "négatif" },
    symptoms: {
      cramps: "crampes de règles",
      pelvic_pain: "douleur dans le bas-ventre ou le bassin",
      pain_with_sex: "douleur pendant les rapports",
      lower_back_pain: "douleur dans le bas du dos",
      bloating: "ballonnements",
      nausea: "nausées",
      vomiting: "vomissements",
      diarrhoea: "diarrhée",
      constipation: "constipation",
      fatigue: "fatigue",
      low_mood: "moral bas",
      anxiety: "anxiété",
      acne: "boutons ou acné",
      unusual_discharge: "pertes inhabituelles",
      bleeding_between_periods: "saignements entre les règles",
    },
  },
  tipsTitle: "Avant d'importer",
  tips: [
    "Les dates doivent être au format année-mois-jour (2026-10-05). Certains tableurs changent le format des dates à la saisie ; dans ce cas, mettez d'abord la colonne des dates au format texte.",
    "Une ligne par jour. Si la même date apparaît deux fois, nous gardons les saignements les plus abondants et la douleur la plus forte.",
    "Nous ne pouvons éviter des questions qu'avec des données récentes : votre dernière entrée doit dater de moins de 45 jours. Les données plus anciennes servent quand même de contexte.",
    "N'ajoutez pas de notes ni rien d'autre au tableau. Les colonnes supplémentaires sont ignorées.",
  ],
  privacyTitle: "Ce que nous conservons",
  privacy:
    "Nous ne conservons que les dates, les saignements et les symptômes listés ci-dessus — jamais le fichier lui-même. Vous pouvez consulter, remplacer ou supprimer vos données de cycle dans les paramètres du compte à tout moment. Ce que vous nous dites dans une discussion passe toujours en premier.",
  notDiagnosis:
    "Vos données de cycle nous aident à poser de meilleures questions. Elles ne servent jamais à vous dire ce que vous avez.",
  promoTitle: "Apportez l'historique de votre cycle",
  promoBody:
    "Ajoutez un relevé de vos règles et la discussion évite les questions auxquelles il répond déjà.",
  promoCta: "Voir comment",
  dashboardCta: "Ajouter des données de cycle",
  dashboardHas: (count: number) =>
    `Données de cycle ajoutées ${count === 0 ? "aujourd'hui" : `il y a ${count} jour${count > 1 ? "s" : ""}`}.`,
  dashboardNone: "Pas encore de données de cycle.",
  chatHint: "Vous notez vos règles ? Appuyez sur le trombone pour les ajouter.",
  chatHintLink: "Comment préparer le fichier",
  howToPrepare: "Comment préparer votre fichier",
};
