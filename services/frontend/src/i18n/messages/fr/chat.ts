import type { ChatMessages } from "../en/chat";

export const chat: ChatMessages = {
  greeting: (name: string | null) =>
    `${name ? `Bonjour ${name}` : "Bonjour"} — je suis là pour vous aider à savoir quoi faire. Dites-moi ce qui se passe, avec vos mots, et je vous poserai quelques questions si besoin.`,
  firstQuestionWait: "Première question — cela prend généralement 15 à 60 secondes",
  followUpWait: (turn: number) => `Question ${turn} — nous vérifions encore les sources`,
  couldNotOpen:
    "Nous n'avons pas pu ouvrir cette discussion. Commencez-en une nouvelle ci-dessous — nous sommes toujours là.",
  chatDeleted: "Discussion supprimée",
  loadingConversation: "Chargement de la discussion…",
  tryAgain: "Réessayer",
  complete: "Cette discussion est terminée. Commencez-en une nouvelle si autre chose se présente.",
  startNewChat: "Commencer une nouvelle discussion",
  placeholderFirst: "Dites-moi ce qui se passe…",
  placeholderReply: "Écrivez votre réponse…",
  footer:
    "HerHealthGPT peut se tromper. Il donne une orientation sur l'urgence, pas un diagnostic.",
  composerLabel: "Décrivez ce qui se passe",
  send: "Envoyer",
  sendLabel: "Envoyer le message",
  waitHint:
    "La première réponse peut prendre jusqu'à une minute — nous affichons l'avancement pendant l'attente.",
  tapSend: "Appuyez sur Envoyer quand vous êtes prête.",
  keyboardHint: "Entrée pour envoyer · Maj+Entrée pour une nouvelle ligne",
  concludedBanner:
    "Cette consultation est terminée. Commencez une nouvelle discussion si autre chose se présente.",
  newChat: "Nouvelle discussion",
  openSidebar: "Ouvrir le panneau",
  closeSidebar: "Fermer le panneau",
  dashboardShort: "Tableau de bord",
  backToDashboard: "Retour au tableau de bord",
  starterIntro: "Vous ne savez pas par où commencer ? Essayez :",
  starters: [
    "Mes règles sont irrégulières depuis quelque temps",
    "Mes saignements sont plus abondants que d'habitude",
    "J'essaie d'avoir un enfant depuis un moment",
    "J'ai une douleur pelvienne qui ne passe pas",
  ],
  basedOn: "D'après",
  sources: "Sources",
  lookedUpLive: "recherché en direct",
  warningSign: "signe d'alerte",
  moreSources: (count: number) => `et ${count} autre${count > 1 ? "s" : ""} source${count > 1 ? "s" : ""}`,
  patterns: "Situations possibles selon nos sources (pas un diagnostic)",
  redFlagNote:
    "Les médecins examinent rapidement cette combinaison de symptômes, car elle a plusieurs causes possibles et certaines doivent être écartées vite.",
  disclaimerTitle: "AVERTISSEMENT",
  disclaimer:
    "Ceci est une orientation sur l'urgence fondée sur des sources citées, pas un diagnostic. Nous sommes un outil d'IA, pas un professionnel de santé, et nous pouvons nous tromper — en cas de doute, consultez un médecin.",
  declineNote: "Aucun niveau d'urgence ni aucune source n'est affiché ici, car rien n'a été évalué.",
  showReasoning: "Voir le raisonnement",
  hideReasoning: "Masquer le raisonnement",
  thinking: [
    "Lecture de votre message…",
    "Recherche dans des sources de santé fiables…",
    "Réflexion sur la prochaine question…",
    "Toujours en cours — certains cas prennent une minute…",
    "Presque fini — merci de patienter…",
  ],
  version: "Version",
  versionLocked: "Commencez une nouvelle discussion pour essayer une autre version",
  compareBanner:
    "Vous nous aidez à comparer des versions. Certaines réponses ne sont pas vérifiées avec nos sources. Ceci est une information, pas un avis médical.",
  unreviewed: (label: string) =>
    `${label} — à des fins de comparaison uniquement. Ce modèle n'est pas validé pour l'orientation et a tendance à conclure trop tôt. Ne vous fiez pas à cette réponse.`,
  groups: {
    today: "Aujourd'hui",
    yesterday: "Hier",
    week: "7 derniers jours",
    older: "Plus ancien",
  },
  closeAccountMenu: "Fermer le menu du compte",
  accountMenu: "Menu du compte",
  yourAccount: "Votre compte",
  manageProfile: "Gérer le profil",
  completed: "Terminée",
  deleteConfirm: "Supprimer définitivement cette discussion ?",
  cancel: "Annuler",
  delete: "Supprimer",
  deleteChat: "Supprimer la discussion",
  deleteChatLabel: (preview: string) => `Supprimer la discussion : ${preview}`,
};
