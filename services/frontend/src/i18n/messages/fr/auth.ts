import type { AuthMessages, CommonMessages, NavMessages } from "../en/auth";

export const common: CommonMessages = {
  appName: "HerHealthGPT",
  metaDescription:
    "Une discussion santé pour les femmes. Parlez de vos symptômes, voyez à quelles situations ils peuvent correspondre et que faire ensuite. Nous ne sommes pas médecins.",
  loading: "Chargement…",
  email: "E-mail",
  emailPlaceholder: "vous@exemple.com",
  password: "Mot de passe",
  showPassword: "Afficher le mot de passe",
  hidePassword: "Masquer le mot de passe",
  signIn: "Se connecter",
  signUp: "S'inscrire",
  signOut: "Se déconnecter",
  openMenu: "Ouvrir le menu",
  closeMenu: "Fermer le menu",
  language: "Langue",
  sending: "Envoi…",
  resendCode: "Renvoyer le code",
  passwordHint: "Au moins 8 caractères.",
  passwordsDoNotMatch: "Les mots de passe ne correspondent pas.",
  codePlaceholder: "000000",
};

export const nav: NavMessages = {
  healthChat: "Discussion santé",
  dashboard: "Tableau de bord",
  account: "Compte",
  howItWorks: "Comment ça marche",
};

export const auth: AuthMessages = {
  shell: {
    heading: "Vous ne savez pas si vous devez consulter ?",
    pitch:
      "Décrivez ce qui se passe avec vos propres mots. Nous vous poserons quelques questions, puis nous vous dirons dans quel délai consulter — et d'où vient cette information.",
    smallPrint:
      "Une orientation sur l'urgence et des informations de santé, jamais un diagnostic. Posez vos questions en français, en anglais ou en arabe.",
  },
  signIn: {
    title: "Bon retour",
    description: "Connectez-vous pour ouvrir votre discussion santé.",
    noAccount: "Vous n'avez pas de compte ?",
    createOne: "Créez-en un",
    forgotPassword: "Mot de passe oublié ?",
    submitting: "Connexion…",
    submit: "Se connecter avec l'e-mail",
  },
  signUp: {
    title: "Créez votre compte",
    descriptionWithGoogle: "Continuez avec Google, ou inscrivez-vous avec votre e-mail.",
    description: "Gratuit. Nous vous enverrons un code pour confirmer votre e-mail.",
    haveAccount: "Vous avez déjà un compte ?",
    divider: "ou inscrivez-vous avec l'e-mail",
    confirmPassword: "Confirmer le mot de passe",
    submitting: "Création du compte…",
    submit: "Créer un compte avec l'e-mail",
    disclaimer:
      "Cette application donne des informations de santé. Ce n'est pas un diagnostic et nous ne sommes pas médecins. Consultez un médecin si vous êtes inquiète.",
  },
  verify: {
    title: "Vérifiez votre e-mail",
    description: "Nous avons envoyé un code à 6 chiffres à votre e-mail. Saisissez-le ci-dessous.",
    alreadyVerified: "Déjà vérifié ?",
    code: "Code de vérification",
    codeHint:
      "Vérifiez votre boîte de réception et vos courriers indésirables. Les codes expirent rapidement — appuyez sur « Renvoyer le code » si le vôtre a expiré.",
    submitting: "Vérification…",
    submit: "Vérifier l'e-mail",
    verified: "E-mail vérifié. Bienvenue !",
    resent: "Si cette adresse est enregistrée, un nouveau code a été envoyé.",
  },
  forgot: {
    title: "Réinitialiser votre mot de passe",
    descriptionSent:
      "Cherchez dans votre boîte de réception un code de réinitialisation à 6 chiffres, puis continuez pour choisir un nouveau mot de passe.",
    description:
      "Saisissez votre e-mail et nous vous enverrons un code de réinitialisation si un compte existe.",
    remember: "Vous vous souvenez de votre mot de passe ?",
    privacyNote:
      "Nous ne vous dirons pas si un e-mail est enregistré. Si vous avez reçu un code, utilisez le bouton ci-dessous pour le saisir.",
    enterCode: "Saisir le code",
    submit: "Envoyer le code",
    sent: "Si cette adresse est enregistrée, un code de réinitialisation a été envoyé.",
  },
  reset: {
    title: "Choisir un nouveau mot de passe",
    description: "Saisissez le code reçu par e-mail et choisissez un nouveau mot de passe.",
    needCode: "Besoin d'un nouveau code ?",
    requestAnother: "En demander un autre",
    code: "Code de réinitialisation",
    newPassword: "Nouveau mot de passe",
    confirmNewPassword: "Confirmer le nouveau mot de passe",
    submitting: "Mise à jour…",
    submit: "Mettre à jour le mot de passe",
    updated: "Mot de passe mis à jour. Connectez-vous avec votre nouveau mot de passe.",
  },
  google: {
    noCredential: "La connexion Google n'a renvoyé aucun identifiant.",
    cancelled: "La connexion Google a été annulée ou a échoué.",
    signingIn: "Connexion en cours…",
    divider: "ou utilisez l'e-mail",
  },
  errors: {
    passwordRequirements: "Le mot de passe ne respecte pas les règles :",
  },
  guard: {
    loadingAccount: "Chargement de votre compte…",
    almostThere: "Presque fini…",
    oneThingFirst: "Juste une chose d'abord…",
  },
};
