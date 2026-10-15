/** The dashboard and its sections. */
export const dashboard = {
  oneMoment: "One moment…",
  toDashboard: "Taking you to your dashboard…",
  subtitleActive: "You have a chat in progress. Pick up where you left off, or start fresh.",
  subtitleCompleted: (count: number) =>
    `You've completed ${count} consultation${count === 1 ? "" : "s"}. Start a new chat anytime.`,
  subtitleSaved: "Your chats are saved here. Open one or start something new.",
  subtitleNew:
    "Tell us how you're feeling — we'll ask a few questions and help you decide what to do next.",
  yourHome: "Your home",
  greeting: (name: string) => `Hi, ${name}`,
  greetingAnonymous: "Hi there",
  accountSettings: "Account settings",
  tryAgain: "Try again",
  chatTitle: "Health chat",
  ready: "Ready",
  chatContinue: "Continue or start a new conversation",
  chatMain: "Your main way to use HerHealthGPT",
  chatPitch:
    "Something on your mind? Describe it in your own words. We'll ask a few follow-up questions if needed, then suggest how soon to see someone — with links to trusted sources. This isn't a diagnosis.",
  openChat: "Open health chat",
  startChat: "Start a chat",
  continueChat: "Continue your chat",
  takesMinutes: "Usually takes a few minutes.",
  scaleTitle: "The four answers a chat can end with",
  scaleLead:
    "We never tell you what you have. Every consultation ends by placing what you described on this scale, with the sources behind it.",
  topicsTitle: "Topics you've explored",
  topicsLead: "Patterns our sources connect to symptoms you've discussed — not a diagnosis.",
  comingLater: "Coming later",
  healthLog: "Health log",
  healthLogBody: "Track your cycle and symptoms over time — we're building this next.",
  allSet: "You're all set",
  allSetBody:
    "Your first health chat is saved. This dashboard will show recent conversations and reading from trusted sources as you go.",
  gotIt: "Got it",
  oneStepLeft: "One step left",
  oneStepLeftBody:
    "Start a health chat when you're ready. We'll ask a few questions and help you decide what to do next.",
  startFirstChat: "Start your first chat",
  recentChats: "Recent chats",
  viewAll: "View all",
  done: "Done",
  inProgress: "In progress",
  recommended: "Recommended for you",
  explore: "Explore trusted topics",
  recommendedLead: "Articles from sources we cite in your chats, plus related reading.",
  exploreLead: "Hand-picked from MedlinePlus, NICHD, and Office on Women's Health.",
  articlesDisclaimer:
    "Information only — not medical advice. We never diagnose. Always see a clinician if you're worried.",
  fromYourChat: "From your chat",
  readOn: (source: string) => `Read on ${source}`,
  articlesInEnglish: "Articles open on the source's own site, in English.",
};

/** The authored conditions, keyed by their id in conditions.yaml. */
export const conditions: Record<string, string> = {
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

export type DashboardMessages = typeof dashboard;
