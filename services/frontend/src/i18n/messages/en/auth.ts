/** Shared words, the site header, and every sign-in, sign-up and password screen. */
export const common = {
  appName: "HerHealthGPT",
  metaDescription:
    "A health chat for women. Talk through your symptoms, see what conditions they might match, and work out what to do next. We're not a doctor.",
  loading: "Loading…",
  email: "Email",
  emailPlaceholder: "you@example.com",
  password: "Password",
  showPassword: "Show password",
  hidePassword: "Hide password",
  signIn: "Sign in",
  signUp: "Sign up",
  signOut: "Sign out",
  openMenu: "Open menu",
  closeMenu: "Close menu",
  language: "Language",
  sending: "Sending…",
  resendCode: "Resend code",
  passwordHint: "At least 8 characters.",
  passwordsDoNotMatch: "Passwords do not match.",
  codePlaceholder: "000000",
};

export const nav = {
  healthChat: "Health chat",
  dashboard: "Dashboard",
  account: "Account",
  howItWorks: "How this works",
};

export const auth = {
  shell: {
    heading: "Not sure if you should see someone?",
    pitch:
      "Describe what's going on in your own words. We'll ask a couple of questions, then tell you how soon to be seen — and show you where that came from.",
    smallPrint:
      "Urgency guidance and health information, never a diagnosis. Ask in English, French or Arabic.",
  },
  signIn: {
    title: "Welcome back",
    description: "Sign in to open your health chat.",
    noAccount: "Don't have an account?",
    createOne: "Create one",
    forgotPassword: "Forgot password?",
    submitting: "Signing in…",
    submit: "Sign in with email",
  },
  signUp: {
    title: "Create your account",
    descriptionWithGoogle: "Continue with Google, or sign up with your email.",
    description: "Free to use. We'll send a quick code to confirm your email.",
    haveAccount: "Already have an account?",
    divider: "or sign up with email",
    confirmPassword: "Confirm password",
    submitting: "Creating account…",
    submit: "Create account with email",
    disclaimer:
      "This app shares health information. It isn't a diagnosis and we're not a doctor. See one if you're worried.",
  },
  verify: {
    title: "Verify your email",
    description: "We sent a 6-digit code to your email. Enter it below.",
    alreadyVerified: "Already verified?",
    code: "Verification code",
    codeHint:
      "Check your inbox and spam folder. Codes expire after a short time — tap resend below if yours ran out.",
    submitting: "Verifying…",
    submit: "Verify email",
    verified: "Email verified. Welcome!",
    resent: "If that address is registered, a new code has been sent.",
  },
  forgot: {
    title: "Reset your password",
    descriptionSent:
      "Check your inbox for a 6-digit reset code, then continue to set a new password.",
    description: "Enter your email and we'll send you a reset code if an account exists.",
    remember: "Remember your password?",
    privacyNote:
      "We won't tell you whether an email is registered. If you got a code, use the button below to enter it.",
    enterCode: "Enter reset code",
    submit: "Send reset code",
    sent: "If that address is registered, a reset code has been sent.",
  },
  reset: {
    title: "Set a new password",
    description: "Enter the code from your email and choose a new password.",
    needCode: "Need a new code?",
    requestAnother: "Request another",
    code: "Reset code",
    newPassword: "New password",
    confirmNewPassword: "Confirm new password",
    submitting: "Updating…",
    submit: "Update password",
    updated: "Password updated. Please sign in with your new password.",
  },
  google: {
    noCredential: "Google sign-in did not return a credential.",
    cancelled: "Google sign-in was cancelled or failed.",
    signingIn: "Signing you in…",
    divider: "or use email",
  },
  errors: {
    passwordRequirements: "Password requirements not met:",
  },
  guard: {
    loadingAccount: "Loading your account…",
    almostThere: "Almost there…",
    oneThingFirst: "Just one thing first…",
  },
};

export type CommonMessages = typeof common;
export type NavMessages = typeof nav;
export type AuthMessages = typeof auth;
