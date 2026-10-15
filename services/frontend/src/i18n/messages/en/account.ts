/** First-time onboarding, the profile step, and account settings. */
export const onboarding = {
  steps: {
    welcome: {
      title: "Welcome to HerHealthGPT",
      body: "Not sure what to do about a symptom? Tell us in your own words — we'll help you work out how urgently to seek care.",
    },
    how: {
      title: "How it works",
      body: "Tell us what you're experiencing in your own words. We'll ask a few short follow-up questions — one at a time, and only when your answer would change the advice — then tell you how soon to seek care and why, with links to the pages it's based on. If you describe a warning sign, we skip the questions and tell you straight away.",
    },
    safety: {
      title: "Good to know",
      body: "We tell you how soon to seek care and why — never what you have. We may mention conditions your symptoms are associated with in our sources, but that is a pattern, not a diagnosis; only a clinician can give you one. If you describe something that needs urgent attention we say so straight away, without asking anything further. And if something feels urgent to you, get seen rather than waiting for a reply.",
    },
    sources: {
      title: "Trusted sources",
      body: "Everything we tell you comes from pages published by MedlinePlus, the Office on Women's Health, NICHD, the CDC and the NHS. We quote those pages directly rather than rewording them, and every quote links back to the page it came from so you can read it in full. Where two sources disagree about how urgent something is, we go with the more urgent one.",
    },
  } as Record<string, { title: string; body: string }>,
  aboutYou: "A little about you",
  aboutYouLead: "Two quick things, so we can give you better guidance and ask you fewer questions later.",
  close: "Close",
  about: "About HerHealthGPT",
  back: "Back",
  gotIt: "Got it",
  continue: "Continue",
  goToDashboard: "Go to my dashboard",
  readyToGo: "Ready to go?",
  skipIntro: "Skip intro — go to dashboard",
  readyToChat: "Ready to chat?",
  openChat: "Open health chat",
  yourName: "Your name",
  namePlaceholder: "What should we call you?",
  nameHint: "Just so we can address you properly. A first name or a nickname is plenty.",
  dateOfBirth: "Date of birth",
  dobHint:
    "Needed, because age changes our guidance — some conditions are far more likely at one age than another.",
  anythingToKnow: "Anything we should know?",
  optional: "(optional)",
  notePlaceholder:
    "Conditions you've been told you have, medicines you take, past surgery — anything you'd rather not repeat each time.",
  noteHint: "You can skip this, and change or delete it later in Settings.",
  privacy:
    "Only you see this. It gives us background so we ask fewer questions — we never treat it as a diagnosis, and it never replaces what you tell us about how you feel today.",
  saving: "Saving…",
};

export const account = {
  title: "Account",
  lead: "Update your name or permanently delete your account. Health chats and personal details stay here — not on your dashboard.",
  profileTitle: "Your profile",
  profileLead: "This is how we greet you in the app. Your email stays private here.",
  name: "Name",
  nameHint: "Optional. Up to 80 characters.",
  signInEmail: "Sign-in email",
  signInEmailHint: "Used to sign in. Contact support if you need to change it.",
  save: "Save changes",
  nameUpdated: "Name updated",
  nameRemoved: "Name removed",
  healthTitle: "Your health details",
  healthLead: "Background we use to give better guidance and ask fewer questions. Never a diagnosis.",
  ageRange: (band: string) => `We use the age range ${band}, not your exact date.`,
  ageWhy: "Some conditions are far more likely at one age than another.",
  noteCount: (length: number, max: number) => `${length}/${max}. Clear the box and save to delete it.`,
  healthNotePlaceholder: "Conditions you've been told you have, medicines you take, past surgery.",
  healthPrivacy:
    "Only you see this. We treat it as background, not as symptoms you're reporting now, and it never replaces what you tell us in a chat.",
  healthUpdated: "Health details updated",
  /** "20_to_29" → "20 to 29", "50_plus" → "50+". */
  ageBand: (band: string) => band.replace("_to_", " to ").replace("_plus", "+").replace(/_/g, " "),
  deleteTitle: "Delete account",
  deleteLead: "Permanently remove your account and every health chat. This cannot be undone.",
  deleteOpen: "Delete my account",
  deleteNow:
    "Your account, credentials, sessions, and all conversations are removed from our live database immediately. There is no grace period and no archive.",
  deleteBackups:
    "Automated database backups may still hold copies until they roll off. We keep backup retention as short as our infrastructure allows; deleted data is not recoverable through the app.",
  deleteAccountLabel: "Account:",
  /** The word she types to confirm, in her language. */
  deleteWord: "DELETE",
  deleteConfirm: (word: string) => `Type ${word} to confirm`,
  cancel: "Cancel",
  deleting: "Deleting…",
  deletePermanently: "Delete permanently",
  deleted: "Your account has been deleted.",
};

export type OnboardingMessages = typeof onboarding;
export type AccountMessages = typeof account;
