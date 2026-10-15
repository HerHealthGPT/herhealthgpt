/**
 * The English dictionary, and the shape every other language must match.
 *
 * Split by area so a translator can work on one screen's words at a time.
 * A function value takes the parts that change (a name, a count) so word
 * order can differ between languages.
 */
import { auth, common, errors, nav } from "./en/auth";
import { actions, errorPages, home } from "./en/site";
import { articles, conditions, dashboard, sourceNames } from "./en/dashboard";
import { account, onboarding } from "./en/account";
import { chat } from "./en/chat";

export const en = { common, nav, auth, home, actions, errorPages, dashboard, conditions, onboarding, account, chat, errors, articles, sourceNames };

export type Messages = typeof en;
