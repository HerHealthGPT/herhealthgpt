/** The French dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, errors, nav } from "./fr/auth";
import { actions, errorPages, home } from "./fr/site";
import { articles, conditions, dashboard } from "./fr/dashboard";
import { account, onboarding } from "./fr/account";
import { chat } from "./fr/chat";

export const fr: Messages = { common, nav, auth, home, actions, errorPages, dashboard, conditions, onboarding, account, chat, errors, articles };
