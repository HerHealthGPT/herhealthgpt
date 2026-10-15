"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/auth-context";
import { deleteAccount } from "@/lib/api/accounts";
import { friendlyApiError } from "@/lib/api/errors";
import { routes } from "@/lib/routes";
import { useI18n } from "@/i18n/locale-provider";


export function DeleteAccountSection() {
  const router = useRouter();
  const { user, setUser } = useAuth();
  const { m } = useI18n();
  const a = m.account;
  // The word she types, in her language: "DELETE" is no use to someone who
  // reads Arabic.
  const CONFIRMATION_WORD = a.deleteWord;
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);

  const canDelete = confirmation === CONFIRMATION_WORD;

  async function handleDelete() {
    if (!canDelete) return;
    setDeleting(true);
    try {
      await deleteAccount();
      setUser(null);
      toast.success(a.deleted);
      router.replace(routes.home);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setDeleting(false);
    }
  }

  function handleCancel() {
    setOpen(false);
    setConfirmation("");
  }

  return (
    <Card className="border-destructive/30" id="delete-account">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-destructive">
          <AlertTriangle className="size-4" />
          {a.deleteTitle}
        </CardTitle>
        <CardDescription className="text-sm leading-relaxed">
          {a.deleteLead}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!open ? (
          <Button variant="destructive" onClick={() => setOpen(true)}>
            {a.deleteOpen}
          </Button>
        ) : (
          <div className="space-y-4 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
            <p className="text-sm leading-relaxed text-foreground">
              {a.deleteNow}
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {a.deleteBackups}
            </p>
            {user?.email ? (
              <p className="text-sm text-muted-foreground">
                {a.deleteAccountLabel} <span className="font-medium text-foreground">{user.email}</span>
              </p>
            ) : null}
            <div className="space-y-2">
              <label htmlFor="delete-confirm" className="text-sm font-medium">
                {a.deleteConfirm(CONFIRMATION_WORD)}
              </label>
              <Input
                id="delete-confirm"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder={CONFIRMATION_WORD}
                autoComplete="off"
                className="max-w-xs"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={handleCancel} disabled={deleting}>
                {a.cancel}
              </Button>
              <Button
                variant="destructive"
                disabled={!canDelete || deleting}
                onClick={() => void handleDelete()}
              >
                {deleting ? a.deleting : a.deletePermanently}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
