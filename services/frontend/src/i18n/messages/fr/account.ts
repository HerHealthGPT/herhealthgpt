import type { AccountMessages, OnboardingMessages } from "../en/account";

export const onboarding: OnboardingMessages = {
  steps: {
    welcome: {
      title: "Bienvenue sur HerHealthGPT",
      body: "Vous ne savez pas quoi faire face à un symptôme ? Décrivez-le avec vos mots — nous vous aiderons à savoir dans quel délai consulter.",
    },
    how: {
      title: "Comment ça marche",
      body: "Décrivez ce que vous ressentez avec vos propres mots. Nous poserons quelques questions courtes — une à la fois, et seulement quand votre réponse changerait le conseil — puis nous vous dirons dans quel délai consulter et pourquoi, avec des liens vers les pages sur lesquelles nous nous appuyons. Si vous décrivez un signe d'alerte, nous passons les questions et vous le disons immédiatement.",
    },
    safety: {
      title: "Bon à savoir",
      body: "Nous vous disons dans quel délai consulter et pourquoi — jamais ce que vous avez. Nous pouvons mentionner des situations que nos sources associent à vos symptômes, mais c'est une tendance, pas un diagnostic ; seul un professionnel de santé peut en poser un. Si vous décrivez quelque chose qui demande une attention urgente, nous le disons tout de suite, sans autre question. Et si quelque chose vous semble urgent, consultez plutôt que d'attendre une réponse.",
    },
    sources: {
      title: "Des sources fiables",
      body: "Tout ce que nous vous disons provient de pages publiées par MedlinePlus, l'Office on Women's Health, le NICHD, les CDC et le NHS. Nous citons ces pages directement plutôt que de les reformuler, et chaque citation renvoie à sa page pour que vous puissiez la lire en entier. Quand deux sources ne sont pas d'accord sur l'urgence, nous retenons la plus urgente.",
    },
  },
  aboutYou: "Un peu sur vous",
  aboutYouLead:
    "Deux petites choses, pour mieux vous orienter et vous poser moins de questions ensuite.",
  close: "Fermer",
  about: "À propos de HerHealthGPT",
  back: "Retour",
  gotIt: "Compris",
  continue: "Continuer",
  goToDashboard: "Aller à mon tableau de bord",
  readyToGo: "Prête ?",
  skipIntro: "Passer l'introduction — aller au tableau de bord",
  readyToChat: "Prête à discuter ?",
  openChat: "Ouvrir la discussion santé",
  yourName: "Votre prénom",
  namePlaceholder: "Comment devons-nous vous appeler ?",
  nameHint: "Simplement pour bien nous adresser à vous. Un prénom ou un surnom suffit.",
  dateOfBirth: "Date de naissance",
  dobHint:
    "Nécessaire, car l'âge change nos conseils — certaines situations sont bien plus probables à un âge qu'à un autre.",
  anythingToKnow: "Quelque chose que nous devrions savoir ?",
  optional: "(facultatif)",
  notePlaceholder:
    "Des problèmes de santé que l'on vous a diagnostiqués, vos médicaments, une chirurgie passée — ce que vous préférez ne pas répéter à chaque fois.",
  noteHint: "Vous pouvez passer cette étape, et modifier ou supprimer ce texte plus tard dans les paramètres.",
  privacy:
    "Vous seule voyez ceci. Cela nous donne du contexte pour poser moins de questions — nous ne le traitons jamais comme un diagnostic, et cela ne remplace jamais ce que vous nous dites de votre état aujourd'hui.",
  saving: "Enregistrement…",
};

export const account: AccountMessages = {
  title: "Compte",
  lead: "Modifiez votre prénom ou supprimez définitivement votre compte. Les discussions santé et les données personnelles restent ici — pas sur votre tableau de bord.",
  profileTitle: "Votre profil",
  profileLead: "C'est ainsi que nous vous saluons dans l'application. Votre e-mail reste privé.",
  name: "Prénom",
  nameHint: "Facultatif. Jusqu'à 80 caractères.",
  signInEmail: "E-mail de connexion",
  signInEmailHint: "Sert à vous connecter. Contactez l'assistance pour le modifier.",
  save: "Enregistrer",
  nameUpdated: "Prénom mis à jour",
  nameRemoved: "Prénom supprimé",
  healthTitle: "Vos informations de santé",
  healthLead:
    "Un contexte qui nous aide à mieux vous orienter et à poser moins de questions. Jamais un diagnostic.",
  ageRange: (band: string) => `Nous utilisons la tranche d'âge ${band}, pas votre date exacte.`,
  ageWhy: "Certaines situations sont bien plus probables à un âge qu'à un autre.",
  noteCount: (length: number, max: number) =>
    `${length}/${max}. Videz le champ et enregistrez pour le supprimer.`,
  healthNotePlaceholder:
    "Des problèmes de santé que l'on vous a diagnostiqués, vos médicaments, une chirurgie passée.",
  healthPrivacy:
    "Vous seule voyez ceci. Nous le traitons comme un contexte, pas comme des symptômes actuels, et cela ne remplace jamais ce que vous nous dites dans une discussion.",
  healthUpdated: "Informations de santé mises à jour",
  ageBand: (band: string) => band.replace("_to_", " à ").replace("_plus", " et +").replace(/_/g, " "),
  deleteTitle: "Supprimer le compte",
  deleteLead: "Supprimez définitivement votre compte et toutes vos discussions. C'est irréversible.",
  deleteOpen: "Supprimer mon compte",
  deleteNow:
    "Votre compte, vos identifiants, vos sessions et toutes vos discussions sont supprimés immédiatement de notre base de données. Il n'y a ni délai de grâce ni archive.",
  deleteBackups:
    "Les sauvegardes automatiques de la base peuvent encore en contenir des copies jusqu'à leur expiration. Nous gardons ces sauvegardes aussi peu de temps que notre infrastructure le permet ; les données supprimées ne peuvent pas être récupérées via l'application.",
  deleteAccountLabel: "Compte :",
  deleteWord: "SUPPRIMER",
  deleteConfirm: (word: string) => `Tapez ${word} pour confirmer`,
  cancel: "Annuler",
  deleting: "Suppression…",
  deletePermanently: "Supprimer définitivement",
  deleted: "Votre compte a été supprimé.",
};
