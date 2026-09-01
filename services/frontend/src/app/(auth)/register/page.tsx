import { redirect } from "next/navigation";

import { routes } from "@/lib/routes";

export default function RegisterRedirectPage() {
  redirect(routes.signUp);
}
