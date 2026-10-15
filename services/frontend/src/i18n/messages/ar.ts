/** The Arabic dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, errors, nav } from "./ar/auth";
import { actions, errorPages, home } from "./ar/site";
import { articles, conditions, dashboard, sourceNames } from "./ar/dashboard";
import { account, onboarding } from "./ar/account";
import { chat } from "./ar/chat";

export const ar: Messages = { common, nav, auth, home, actions, errorPages, dashboard, conditions, onboarding, account, chat, errors, articles, sourceNames };
