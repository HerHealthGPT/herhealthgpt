/** The French dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, nav } from "./fr/auth";

export const fr: Messages = { common, nav, auth };
