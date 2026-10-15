/** The French dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, nav } from "./fr/auth";
import { actions, errorPages, home } from "./fr/site";
import { conditions, dashboard } from "./fr/dashboard";
import { account, onboarding } from "./fr/account";

export const fr: Messages = { common, nav, auth, home, actions, errorPages, dashboard, conditions, onboarding, account };
