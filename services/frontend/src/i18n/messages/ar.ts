/** The Arabic dictionary. Typed against the English one: a missing key fails tsc. */
import type { Messages } from "./en";
import { auth, common, nav } from "./ar/auth";

export const ar: Messages = { common, nav, auth };
