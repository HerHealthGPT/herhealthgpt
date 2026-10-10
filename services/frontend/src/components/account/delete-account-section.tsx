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

const CONFIRMATION_WORD = "DELETE";

export function DeleteAccountSection() {
  const router = useRouter();
  const { user, setUser } = useAuth();
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
      toast.success("Your account has been deleted.");
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
          Delete account
        </CardTitle>
        <CardDescription className="text-sm leading-relaxed">
          Permanently remove your account and every health chat. This cannot be
          undone.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!open ? (
          <Button variant="destructive" onClick={() => setOpen(true)}>
            Delete my account
          </Button>
        ) : (
          <div className="space-y-4 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
            <p className="text-sm leading-relaxed text-foreground">
              Your account, credentials, sessions, and all conversations are
              removed from our live database <strong>immediately</strong>. There
              is no grace period and no archive.
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Automated database backups may still hold copies until they roll
              off. We keep backup retention as short as our infrastructure
              allows; deleted data is not recoverable through the app.
            </p>
            {user?.email ? (
              <p className="text-sm text-muted-foreground">
                Account: <span className="font-medium text-foreground">{user.email}</span>
              </p>
            ) : null}
            <div className="space-y-2">
              <label htmlFor="delete-confirm" className="text-sm font-medium">
                Type {CONFIRMATION_WORD} to confirm
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
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={!canDelete || deleting}
                onClick={() => void handleDelete()}
              >
                {deleting ? "Deleting…" : "Delete permanently"}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
