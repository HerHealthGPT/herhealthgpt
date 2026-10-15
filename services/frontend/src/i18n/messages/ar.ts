/** The Arabic dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, nav } from "./ar/auth";
import { actions, errorPages, home } from "./ar/site";

export const ar: Messages = { common, nav, auth, home, actions, errorPages };
