export const routes = {
  home: "/",
  signUp: "/sign-up",
  signIn: "/sign-in",
  verifyEmail: "/verify-email",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",
  dashboard: "/dashboard",
  settings: "/settings",
  onboarding: "/onboarding",
  howItWorks: "/how-it-works",
  chat: "/chat",
  cycleImportGuide: "/cycle-import-guide",
} as const;

/** The empty cycle-data template; its header is the importer's columns. */
export const CYCLE_TEMPLATE_URL = "/templates/cycle-log-template.csv";
