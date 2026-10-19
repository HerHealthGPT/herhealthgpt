/**
 * The step-by-step guide to preparing a cycle-data file, and the places
 * that point to it. The file's column names and values stay in English in
 * every language: they are what the importer reads (backend
 * `app/accounts/cycle_import.py`, `CSV_TEMPLATE_HEADER`).
 */
export const cycleGuide = {
  pageTitle: "Add your cycle history",
  lead: "If you keep a record of your periods, you can share it with us as a simple spreadsheet. We'll use it as background, so the chat asks you fewer questions about things your record already shows.",
  stepLabel: (n: number) => `Step ${n}`,
  steps: [
    {
      title: "Download the template",
      body: "It's an empty spreadsheet with five columns. Open it in Excel, Google Sheets, Numbers or any spreadsheet app.",
    },
    {
      title: "Add one row for each day you want to record",
      body: "Fill in the date, and anything you noticed that day. Leave a cell empty if there's nothing to say. A row for every period day is the most useful part.",
    },
    {
      title: "Save it as a CSV file",
      body: 'Use "Save as" or "Download" and choose CSV (UTF-8). Keep the first row — the column names — exactly as it is.',
    },
    {
      title: "Upload it and check what we found",
      body: "Go to Account → Cycle data, or tap the paperclip in the chat. We show you what we read before anything is saved, and you choose whether to keep it.",
    },
  ],
  downloadTemplate: "Download the template (CSV)",
  goToUpload: "Upload in Account settings",
  exampleTitle: "What a filled-in sheet looks like",
  exampleNote: "An example only — use your own dates. Don't upload these rows.",
  columnsTitle: "What goes in each column",
  columns: {
    date: "The day, written as year-month-day: 2026-10-05.",
    flow: "How much you bled that day. Leave it empty on days without a period.",
    symptoms: "Anything you noticed. For more than one, separate them with a semicolon: cramps;bloating",
    pain_intensity: "If you had pain, how bad it was.",
    pregnancy_test: "Only if you took a pregnancy test that day.",
  } as Record<string, string>,
  valuesTitle: "Allowed words",
  valuesNote:
    "Type the English word on the left exactly as shown, even if the rest of your sheet is in another language. The meaning is beside it.",
  values: {
    flow: {
      spotting: "spotting",
      light: "light",
      medium: "medium",
      heavy: "heavy",
      none: "no bleeding",
      unspecified: "bled, amount not noted",
    },
    pain_intensity: { mild: "mild", moderate: "moderate", severe: "severe" },
    pregnancy_test: { positive: "positive", negative: "negative" },
    symptoms: {
      cramps: "period cramps",
      pelvic_pain: "pain low in the tummy or pelvis",
      pain_with_sex: "pain during sex",
      lower_back_pain: "lower back pain",
      bloating: "bloating",
      nausea: "feeling sick",
      vomiting: "being sick",
      diarrhoea: "diarrhoea",
      constipation: "constipation",
      fatigue: "tiredness",
      low_mood: "low mood",
      anxiety: "anxiety",
      acne: "spots or acne",
      unusual_discharge: "unusual discharge",
      bleeding_between_periods: "bleeding between periods",
    },
  } as Record<string, Record<string, string>>,
  tipsTitle: "Before you upload",
  tips: [
    "Dates must be year-month-day (2026-10-05). Some spreadsheet apps change dates to another format when you type them; if that happens, format the date column as text first.",
    "One row per day. If you write the same date twice, we keep the heavier flow and the worse pain.",
    "We can only skip questions using recent data: your last entry needs to be within the past 45 days. Older data is still used as background.",
    "Don't add notes or anything else to the sheet. Extra columns are ignored.",
  ],
  privacyTitle: "What we keep",
  privacy:
    "We keep only the dates, flow and symptoms listed above — not the file itself, unless you choose to keep a copy, which is deleted automatically after 30 days. You can see, replace or delete your cycle data in Account settings at any time. What you tell us in a chat always comes first.",
  notDiagnosis:
    "Your cycle data helps us ask better questions. It is never used to tell you what you have.",
  promoTitle: "Bring your cycle history",
  promoBody:
    "Add a record of your periods and the chat skips questions your record already answers.",
  promoCta: "See how",
  dashboardCta: "Add cycle data",
  dashboardHas: (days: number) =>
    `Cycle data added ${days === 0 ? "today" : `${days} ${days === 1 ? "day" : "days"} ago`}.`,
  dashboardNone: "No cycle data yet.",
  chatHint: "Keep a period record? Tap the paperclip to add it.",
  chatHintLink: "How to prepare the file",
  howToPrepare: "How to prepare your file",
};

export type CycleGuideMessages = typeof cycleGuide;
