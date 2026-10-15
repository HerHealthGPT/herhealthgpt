import type { ActionMessages, ErrorPageMessages, HomeMessages } from "../en/site";

export const home: HomeMessages = {
  title: "Vous ne savez pas s'il faut voir un médecin ?",
  lead:
    "Décrivez ce qui se passe avec vos propres mots. Nous posons quelques questions, puis nous vous disons dans quel délai consulter — et nous vous montrons la source sur laquelle nous nous appuyons.",
  startChat: "Commencer une discussion",
  languages: "Posez vos questions en français, en anglais ou en arabe.",
  scaleTitle: "Chaque réponse se situe quelque part sur cette ligne",
  scaleLead:
    "Nous ne vous disons pas ce que vous avez. Nous vous disons à quel point c'est urgent, et pourquoi nous le pensons.",
  sourcesTitle: "Vous pouvez vérifier d'où vient chaque réponse",
  sourcesLead:
    "Les réponses citent le NHS, MedlinePlus, l'Office on Women's Health, le NICHD et les CDC — avec un lien direct vers la page.",
  disclaimer:
    "HerHealthGPT donne des informations de santé et une orientation sur l'urgence, jamais un diagnostic, et peut se tromper. Ce n'est pas un médecin. Si quelque chose vous semble urgent, contactez les services d'urgence ou rendez-vous à l'hôpital.",
  preview: {
    label: "Exemple de discussion avec HerHealthGPT",
    her1: "mes règles sont très abondantes depuis quelques mois et je suis épuisée tout le temps",
    question: "Combien de jours les saignements durent-ils d'habitude ?",
    her2: "environ 8 jours",
    resultHeading: "Un rendez-vous ordinaire est conseillé",
    resultBody:
      "Rien ici ne semble urgent, mais des saignements aussi abondants méritent d'être examinés — prenez un rendez-vous non urgent.",
    quote: "Les règles abondantes sont fréquentes et peuvent avoir plusieurs causes.",
  },
};

export const actions: ActionMessages = {
  SELF_CARE: {
    heading: "Des soins à la maison devraient suffire",
    body: "D'après ce que vous avez décrit, cela semble pouvoir se gérer vous-même pour l'instant. Si cela change ou ne s'améliore pas, il vaut la peine de consulter un médecin.",
    scale: "Rien n'indique que vous deviez contacter quelqu'un maintenant.",
  },
  ROUTINE_APPOINTMENT: {
    heading: "Un rendez-vous ordinaire est conseillé",
    body: "Rien ici ne semble urgent, mais il vaut la peine de prendre un rendez-vous non urgent avec un professionnel de santé pour examiner la question.",
    scale: "Mérite d'être examiné, mais pas aujourd'hui.",
  },
  URGENT_SAME_DAY: {
    heading: "Consultez aujourd'hui",
    body: "Ce que vous décrivez devrait être examiné par un professionnel de santé le jour même — organisez une consultation aujourd'hui.",
    scale: "Cela ne doit pas attendre un rendez-vous ordinaire.",
  },
  EMERGENCY: {
    heading: "Cela nécessite des soins d'urgence maintenant",
    body: "Demandez des soins d'urgence immédiatement — rendez-vous aux urgences les plus proches ou appelez le numéro d'urgence local maintenant.",
    scale: "Demandez des soins d'urgence immédiatement.",
  },
};

export const errorPages: ErrorPageMessages = {
  notFoundTitle: "Page introuvable",
  notFoundHeading: "Nous ne trouvons pas cette page",
  notFoundBody: "Le lien est peut-être périmé, ou l'adresse contient une faute de frappe.",
  goToDashboard: "Aller au tableau de bord",
  startChat: "Commencer une discussion",
  errorHeading: "Une erreur s'est produite",
  errorBody:
    "Une erreur inattendue s'est produite. Vous pouvez réessayer ou revenir à votre tableau de bord.",
  globalBody: "L'application a rencontré une erreur inattendue. Veuillez réessayer.",
  tryAgain: "Réessayer",
  goHome: "Accueil",
};
