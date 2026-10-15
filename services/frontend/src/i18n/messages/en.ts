/**
 * The English dictionary, and the shape every other language must match.
 *
 * Split by area so a translator can work on one screen's words at a time.
 * A function value takes the parts that change (a name, a count) so word
 * order can differ between languages.
 */
import { auth, common, nav } from "./en/auth";
import { actions, errorPages, home } from "./en/site";
import { conditions, dashboard } from "./en/dashboard";

export const en = { common, nav, auth, home, actions, errorPages, dashboard, conditions };

export type Messages = typeof en;
