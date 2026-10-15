/** The landing page, the urgency scale and labels, and the error pages. */
export const home = {
  title: "Not sure if this needs a doctor?",
  lead:
    "Describe what's going on in your own words. We ask a couple of questions, then tell you how soon to be seen — and show you the source we got that from.",
  startChat: "Start a chat",
  languages: "Ask in English, French or Arabic.",
  scaleTitle: "Every answer lands somewhere on this line",
  scaleLead: "We don't tell you what you have. We tell you how urgent it is, and why we think so.",
  sourcesTitle: "You can check where every answer came from",
  sourcesLead:
    "Answers quote the NHS, MedlinePlus, the Office on Women's Health, NICHD and the CDC — and link straight to the page.",
  disclaimer:
    "HerHealthGPT gives health information and urgency guidance, never a diagnosis, and it can be wrong. It isn't a doctor. If something feels urgent, contact emergency services or go to hospital.",
  preview: {
    label: "Example of a conversation with HerHealthGPT",
    her1: "my periods have been really heavy for a few months and i feel wiped out all the time",
    question: "How many days does the bleeding usually last?",
    her2: "about 8 days",
    resultHeading: "Worth a routine appointment",
    resultBody:
      "Nothing here looks urgent, but bleeding this heavy is worth having looked at — book a non-urgent appointment.",
    quote: "Heavy periods are common and can have a number of causes.",
  },
};

/** One entry per action code. The code is the contract; these are only its words. */
export const actions = {
  SELF_CARE: {
    heading: "Self-care should be enough",
    body: "Based on what you've shared, this looks like something you can manage yourself for now. If it changes or doesn't settle, it's worth checking in with a doctor.",
    scale: "Nothing suggests you need to contact anyone right now.",
  },
  ROUTINE_APPOINTMENT: {
    heading: "Worth a routine appointment",
    body: "Nothing here looks urgent, but it's worth arranging a non-urgent appointment with a healthcare professional to look into it.",
    scale: "Worth looking into, but it doesn't need attention today.",
  },
  URGENT_SAME_DAY: {
    heading: "Please get seen today",
    body: "What you've described should be looked at by a healthcare professional the same day — please arrange to be seen today.",
    scale: "This shouldn't wait for a routine appointment.",
  },
  EMERGENCY: {
    heading: "This needs emergency care now",
    body: "Please seek emergency care right away — go to the nearest emergency department or call your local emergency number now.",
    scale: "Seek emergency care immediately.",
  },
};

export const errorPages = {
  notFoundTitle: "Page not found",
  notFoundHeading: "We can't find that page",
  notFoundBody: "The link may be out of date, or the address may have a typo in it.",
  goToDashboard: "Go to dashboard",
  startChat: "Start a chat",
  errorHeading: "Something went wrong",
  errorBody: "An unexpected error occurred. You can try again, or go back to your dashboard.",
  globalBody: "The app hit an unexpected error. Please try again.",
  tryAgain: "Try again",
  goHome: "Go home",
};

export type HomeMessages = typeof home;
export type ActionMessages = typeof actions;
export type ErrorPageMessages = typeof errorPages;
